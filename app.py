import os
import pandas as pd
import requests
import streamlit as st

BACKEND_HOST = os.getenv("BACKEND_HOST", "http://127.0.0.1:8000")
BACKEND_AGENT_URL = f"{BACKEND_HOST}/api/agent/execute"
BACKEND_EXPORT_URL = f"{BACKEND_HOST}/api/export"
BACKEND_QA_INDEX_URL = f"{BACKEND_HOST}/api/qa/index"
BACKEND_QA_ASK_URL = f"{BACKEND_HOST}/api/qa/ask"

TASK_SUMMARY = "Resumen de documento"
TASK_ANALYTICS = "Análisis financiero"
TASK_COMPARE = "Comparación de documentos"
TASK_QA = "QA sobre documento"

ALLOWED_FILE_TYPES = ["pdf", "docx", "txt", "csv", "md"]


def init_state() -> None:
    defaults = {
        "last_result": None,
        "last_task": None,
        "qa_messages": [],
        "qa_file_name": None,
        "qa_document_id": None,
        "qa_index_metadata": None,
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_if_task_changed(task: str) -> None:
    if st.session_state.last_task != task:
        st.session_state.last_result = None
        st.session_state.last_task = task

        if task != TASK_QA:
            reset_qa_state()


def reset_qa_state() -> None:
    st.session_state.qa_messages = []
    st.session_state.qa_file_name = None
    st.session_state.qa_document_id = None
    st.session_state.qa_index_metadata = None


def call_backend(file, second_file, percentage: int, user_request: str) -> dict:
    files = {"file": (file.name, file.getvalue())}

    if second_file:
        files["second_file"] = (second_file.name, second_file.getvalue())

    response = requests.post(
        BACKEND_AGENT_URL,
        files=files,
        data={
            "percentage": str(percentage),
            "user_request": user_request,
        },
        timeout=300,
    )

    if response.status_code != 200:
        try:
            st.error(response.json())
        except Exception:
            st.error(response.text)
        st.stop()

    return response.json()


def index_qa_document(file) -> dict:
    response = requests.post(
        BACKEND_QA_INDEX_URL,
        files={"file": (file.name, file.getvalue())},
        timeout=300,
    )

    if response.status_code != 200:
        try:
            st.error(response.json())
        except Exception:
            st.error(response.text)
        st.stop()

    return response.json()


def ask_qa_document(document_id: str, question: str) -> dict:
    response = requests.post(
        BACKEND_QA_ASK_URL,
        data={
            "document_id": document_id,
            "question": question,
        },
        timeout=300,
    )

    if response.status_code != 200:
        try:
            st.error(response.json())
        except Exception:
            st.error(response.text)
        st.stop()

    return response.json()


def render_general(result: dict) -> None:
    st.success("Procesamiento completado")

    with st.expander("Información general"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Tipo de documento", result.get("document_type", "-"))
        col2.metric("Intención detectada", result.get("user_intent", "-"))
        col3.metric("Estado", result.get("status", "completed"))


def render_items(title: str, items: list[str]) -> None:
    if items:
        st.write(f"### {title}")
        for item in items:
            st.write(f"- {item}")


def render_table(title: str, rows: list[dict]) -> None:
    if rows:
        st.write(f"### {title}")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def render_summary(data: dict) -> None:
    st.subheader("Resumen")

    col1, col2, col3 = st.columns(3)
    col1.metric("Palabras originales", data.get("original_words"))
    col2.metric("Palabras objetivo", data.get("target_words"))
    col3.metric("Palabras reales", data.get("summary_words"))

    if data.get("was_capped"):
        st.warning("El resumen fue limitado a 5000 palabras.")

    summary_text = data.get("summary", "")
    st.text_area("Resumen generado", summary_text, height=350)

    st.write("### Descargar resumen")
    output_format = st.selectbox("Formato", ["txt", "pdf", "docx"])

    response = requests.post(
        BACKEND_EXPORT_URL,
        data={
            "summary": summary_text,
            "output_format": output_format,
        },
        timeout=300,
    )

    mime_map = {
        "txt": "text/plain",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    if response.status_code == 200:
        st.download_button(
            "Descargar",
            response.content,
            f"resumen.{output_format}",
            mime=mime_map[output_format],
        )


def render_charts(charts: list[dict]) -> None:
    if not charts:
        return

    st.write("### Gráficas")

    for index, chart in enumerate(charts, start=1):
        st.write(f"#### {chart.get('title', f'Gráfico {index}')}")

        rows = [
            {
                "x": point.get("x"),
                "series": serie.get("name", "Serie"),
                "y": point.get("y"),
            }
            for serie in chart.get("series", [])
            for point in serie.get("data", [])
        ]

        if not rows:
            st.info("No hay datos para este gráfico.")
            continue

        df = pd.DataFrame(rows)

        try:
            pivot = df.pivot(index="x", columns="series", values="y")
        except Exception as exc:
            st.error(f"No se pudo preparar el gráfico: {exc}")
            continue

        if chart.get("chart_type") == "line":
            st.line_chart(pivot)
        else:
            st.bar_chart(pivot)


def render_analytics(data: dict) -> None:
    st.subheader("Análisis financiero")

    render_items("Insights", data.get("insights", []))
    render_table("Filas financieras estructuradas", data.get("rows", []))
    render_table("Métricas detectadas", data.get("metrics", []))
    render_table("Variaciones porcentuales", data.get("percentages", []))
    render_charts(data.get("chart_specs", []))

    if data.get("warnings"):
        st.warning(data["warnings"])


def render_comparison(data: dict) -> None:
    st.subheader("Comparación de documentos")

    col1, col2 = st.columns(2)

    with col1:
        st.write("### Documento A")
        if data.get("document_a_summary"):
            st.write(data["document_a_summary"])
        if data.get("document_a_keywords"):
            st.write("**Palabras clave:**")
            st.write(", ".join(data["document_a_keywords"]))

    with col2:
        st.write("### Documento B")
        if data.get("document_b_summary"):
            st.write(data["document_b_summary"])
        if data.get("document_b_keywords"):
            st.write("**Palabras clave:**")
            st.write(", ".join(data["document_b_keywords"]))

    render_items("Similitudes", data.get("similarities", []))
    render_items("Diferencias", data.get("differences", []))
    render_items("Ventajas del documento A", data.get("document_a_advantages", []))
    render_items("Desventajas del documento A", data.get("document_a_disadvantages", []))
    render_items("Ventajas del documento B", data.get("document_b_advantages", []))
    render_items("Desventajas del documento B", data.get("document_b_disadvantages", []))

    if data.get("comparison_summary"):
        st.write("### Conclusión")
        st.info(data["comparison_summary"])


def render_qa_chat(uploaded_file) -> None:
    st.subheader("QA sobre documento")

    if not uploaded_file:
        st.info("Sube un documento para preparar el chat.")
        return

    if st.session_state.qa_file_name != uploaded_file.name:
        reset_qa_state()
        st.session_state.qa_file_name = uploaded_file.name

    if not st.session_state.qa_document_id:
        if st.button("Preparar documento para QA"):
            with st.spinner("Indexando documento en base vectorial..."):
                result = index_qa_document(uploaded_file)

            st.session_state.qa_document_id = result.get("document_id")
            st.session_state.qa_index_metadata = result
            st.success("Documento preparado para QA.")

        return

    metadata = st.session_state.qa_index_metadata or {}

    with st.expander("Información QA"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Documento", metadata.get("filename", uploaded_file.name))
        col2.metric("Chunks indexados", metadata.get("chunks_indexed", "-"))
        col3.metric("Reutilizado", "Sí" if metadata.get("already_indexed") else "No")

    for message in st.session_state.qa_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

            chunks = message.get("retrieved_chunks", [])
            if chunks:
                with st.expander("Fragmentos recuperados"):
                    for index, chunk in enumerate(chunks, start=1):
                        st.write(f"Fragmento {index}")
                        st.text(chunk)

    question = st.chat_input("Pregunta algo sobre el documento")

    if not question:
        return

    st.session_state.qa_messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Consultando documento..."):
            result = ask_qa_document(
                document_id=st.session_state.qa_document_id,
                question=question,
            )

        answer = result.get("answer") or "No se pudo generar una respuesta."
        retrieved_chunks = result.get("retrieved_chunks", [])

        st.write(answer)

        if retrieved_chunks:
            with st.expander("Fragmentos recuperados"):
                for index, chunk in enumerate(retrieved_chunks, start=1):
                    st.write(f"Fragmento {index}")
                    st.text(chunk)

        st.session_state.qa_messages.append(
            {
                "role": "assistant",
                "content": answer,
                "retrieved_chunks": retrieved_chunks,
            }
        )


def render_result(result: dict | None) -> None:
    if not result:
        return

    render_general(result)

    if result.get("summary_result"):
        render_summary(result["summary_result"])

    if result.get("analytics_result"):
        render_analytics(result["analytics_result"])

    if result.get("comparison_result"):
        render_comparison(result["comparison_result"])

    if result.get("warnings"):
        st.warning(result["warnings"])

    if result.get("errors"):
        st.error(result["errors"])


def validate_before_submit(task: str, file, second_file) -> None:
    if not file:
        st.error("Sube un documento.")
        st.stop()

    if task == TASK_COMPARE and not second_file:
        st.error("Sube un segundo documento para comparar.")
        st.stop()


def render_task_controls(task: str):
    percentage = 0
    second_file = None
    user_request = ""

    if task == TASK_SUMMARY:


        
        user_request = "Resume este documento"
        percentage = st.slider("Porcentaje de resumen", 10, 80, 30, step=10)

    elif task == TASK_ANALYTICS:
        user_request = "Extrae métricas financieras, insights y gráficas comparativas."
        st.info("Extrae métricas estructuradas, variaciones porcentuales, insights y gráficas.")

    elif task == TASK_COMPARE:
        with st.sidebar:
            second_file = st.file_uploader(
                "Segundo documento (.pdf, .docx, .txt, .csv, .md)",
                type=ALLOWED_FILE_TYPES,
                key="second_file",
            )

        user_request = (
            "Compara estos dos documentos identificando similitudes, diferencias, "
            "ventajas, desventajas y una conclusión breve."
        )

        st.info("Compara dos documentos mediante highlights breves y estructurados.")

    elif task == TASK_QA:
        st.info("Primero prepara el documento; después podrás hacer preguntas continuas.")

    return percentage, user_request, second_file


def main() -> None:
    st.set_page_config(page_title="Procesador de documentos", layout="wide")
    st.title("Procesador de documentos")

    init_state()

    with st.sidebar:
        st.header("Carga de documentos")
        uploaded_file = st.file_uploader(
            "Documento principal (.pdf, .docx, .txt, .csv, .md)",
            type=ALLOWED_FILE_TYPES,
            key="main_file",
        )

    task = st.selectbox(
        "Selecciona la tarea",
        [TASK_SUMMARY, TASK_ANALYTICS, TASK_COMPARE, TASK_QA],
    )

    reset_if_task_changed(task)

    percentage, user_request, second_file = render_task_controls(task)

    if task == TASK_QA:
        render_qa_chat(uploaded_file)
        return

    if st.button("Procesar documento"):
        validate_before_submit(task, uploaded_file, second_file)

        with st.spinner("Procesando..."):
            result = call_backend(
                file=uploaded_file,
                second_file=second_file,
                percentage=percentage,
                user_request=user_request,
            )

            st.session_state.last_result = result

    render_result(st.session_state.last_result)


if __name__ == "__main__":
    main()