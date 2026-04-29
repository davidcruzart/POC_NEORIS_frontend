import pandas as pd
import requests
import streamlit as st

BACKEND_AGENT_URL = "http://127.0.0.1:8000/api/agent/execute"
BACKEND_EXPORT_URL = "http://127.0.0.1:8000/api/export"

TASK_SUMMARY = "Resumen de documento"
TASK_ANALYTICS = "Análisis financiero (gráficas e insights)"
TASK_COMPARE = "Comparación de dos documentos"
TASK_QA = "Preguntas sobre el documento (QA-RAG)"

ALLOWED_FILE_TYPES = ["pdf", "docx", "txt", "csv", "md"]


def init_state() -> None:
    defaults = {
        "last_result": None,
        "last_modo_tarea": None,
        "last_summary_text": None,
        "export_file_bytes": None,
        "export_file_format": None,
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_on_task_change(task: str) -> None:
    if st.session_state.last_modo_tarea is None:
        st.session_state.last_modo_tarea = task
        return

    if st.session_state.last_modo_tarea != task:
        st.session_state.last_result = None
        st.session_state.last_summary_text = None
        st.session_state.export_file_bytes = None
        st.session_state.export_file_format = None
        st.session_state.last_modo_tarea = task
        st.rerun()


def post_agent_request(uploaded_file, second_file, percentage: int, user_request: str) -> dict:
    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}

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


def render_table(title: str, rows: list[dict]) -> None:
    if rows:
        st.write(f"### {title}")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def render_items(title: str, items: list[str]) -> None:
    if items:
        st.write(f"### {title}")
        for item in items:
            st.write(f"- {item}")


def render_general_info(result: dict) -> None:
    st.success("Procesamiento completado")
    st.subheader("Información general")

    col1, col2, col3 = st.columns(3)

    col1.metric("Tipo de documento", str(result.get("document_type", "-")))
    col2.metric("Intención detectada", str(result.get("user_intent", "-")))
    col3.metric("Estado", str(result.get("status", "completed")))


def render_summary_download(summary_text: str) -> None:
    st.write("### Descargar resumen")

    output_format = st.selectbox(
        "Formato de exportación",
        ["txt", "pdf", "docx"],
        key="export_format",
    )

    mime_map = {
        "txt": "text/plain",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    try:
        response = requests.post(
            BACKEND_EXPORT_URL,
            data={
                "summary": summary_text,
                "output_format": output_format,
            },
            timeout=300,
        )

        if response.status_code == 200:
            st.download_button(
                label=f"Descargar resumen en {output_format.upper()}",
                data=response.content,
                file_name=f"resumen.{output_format}",
                mime=mime_map[output_format],
            )
        else:
            try:
                st.error(response.json())
            except Exception:
                st.error(response.text)

    except requests.exceptions.RequestException as exc:
        st.error(f"Error al preparar la descarga: {exc}")


def render_summary(summary: dict) -> None:
    col1, col2, col3 = st.columns(3)

    col1.metric("Palabras originales", summary.get("original_words"))
    col2.metric("Palabras objetivo", summary.get("target_words"))
    col3.metric("Palabras reales", summary.get("summary_words"))

    if summary.get("was_capped"):
        st.warning("El resumen fue limitado a 5000 palabras.")

    summary_text = summary.get("summary", "")
    st.text_area("Resumen generado", summary_text, height=350)
    render_summary_download(summary_text)


def render_charts(charts: list[dict]) -> None:
    if not charts:
        return

    st.write("### Gráficas")

    for index, chart in enumerate(charts, start=1):
        st.write(f"#### {chart.get('title', f'Gráfico {index}')}")

        if chart.get("reason"):
            st.caption(chart["reason"])

        chart_rows = [
            {
                "x": point.get("x"),
                "series": serie.get("name", "Serie"),
                "y": point.get("y"),
            }
            for serie in chart.get("series", [])
            for point in serie.get("data", [])
        ]

        if not chart_rows:
            st.info("No hay puntos de datos para este gráfico.")
            continue

        df = pd.DataFrame(chart_rows)

        try:
            pivot_df = df.pivot(index="x", columns="series", values="y")
        except Exception as exc:
            st.error(f"No se pudo preparar el gráfico: {exc}")
            continue

        chart_type = chart.get("chart_type", "bar")

        if chart_type == "line":
            st.line_chart(pivot_df)
        elif chart_type == "bar":
            st.bar_chart(pivot_df)
        else:
            st.write(f"Tipo de gráfico no soportado todavía: {chart_type}")


def render_analytics(analytics: dict) -> None:
    render_items("Insights", analytics.get("insights", []))
    render_table("Filas financieras estructuradas", analytics.get("rows", []))
    render_table("Métricas detectadas", analytics.get("metrics", []))
    render_table("Variaciones porcentuales", analytics.get("percentages", []))
    render_charts(analytics.get("chart_specs", []))

    if analytics.get("warnings"):
        st.warning(analytics["warnings"])


def render_comparison(comparison: dict) -> None:
    col_a, col_b = st.columns(2)

    with col_a:
        st.write("### Documento A")
        if comparison.get("document_a_summary"):
            st.write(comparison["document_a_summary"])
        if comparison.get("document_a_keywords"):
            st.write("**Palabras clave:**")
            st.write(", ".join(comparison["document_a_keywords"]))

    with col_b:
        st.write("### Documento B")
        if comparison.get("document_b_summary"):
            st.write(comparison["document_b_summary"])
        if comparison.get("document_b_keywords"):
            st.write("**Palabras clave:**")
            st.write(", ".join(comparison["document_b_keywords"]))

    render_items("Similitudes", comparison.get("similarities", []))
    render_items("Diferencias", comparison.get("differences", []))
    render_items("Ventajas del documento A", comparison.get("document_a_advantages", []))
    render_items("Desventajas del documento A", comparison.get("document_a_disadvantages", []))
    render_items("Ventajas del documento B", comparison.get("document_b_advantages", []))
    render_items("Desventajas del documento B", comparison.get("document_b_disadvantages", []))

    if comparison.get("comparison_summary"):
        st.write("### Conclusión comparativa")
        st.info(comparison["comparison_summary"])


def render_qa(qa: dict) -> None:
    st.write("### Pregunta")
    st.write(qa.get("question"))

    st.write("### Respuesta")
    st.write(qa.get("answer"))

    chunks = qa.get("retrieved_chunks", [])
    if chunks:
        with st.expander("Fragmentos recuperados"):
            for index, chunk in enumerate(chunks, start=1):
                st.write(f"#### Fragmento {index}")
                st.text(chunk)


def render_result(result: dict | None) -> None:
    if not result:
        return

    render_general_info(result)

    blocks = [
        ("Resumen", "summary_result", render_summary, "summarize"),
        ("Análisis financiero", "analytics_result", render_analytics, "extract_analytics"),
        ("Comparación de documentos", "comparison_result", render_comparison, "compare_documents"),
        ("Pregunta-Respuesta sobre documento", "qa_result", render_qa, "qa_rag"),
    ]

    current_intent = result.get("user_intent")

    for title, key, renderer, intent in blocks:
        payload = result.get(key)

        if payload:
            with st.expander(title, expanded=current_intent == intent):
                renderer(payload)

    if result.get("warnings"):
        st.warning(result["warnings"])

    if result.get("errors"):
        st.error(result["errors"])


def validate_before_submit(task: str, uploaded_file, second_file, user_request: str) -> None:
    if not uploaded_file:
        st.error("Debes subir un archivo principal.")
        st.stop()

    if task == TASK_COMPARE and not second_file:
        st.error("Para comparar documentos debes subir un segundo archivo.")
        st.stop()

    if task == TASK_QA and not user_request.strip():
        st.error("Debes escribir una pregunta sobre el documento.")
        st.stop()


def render_task_controls(task: str):
    percentage = 0
    second_file = None

    if task == TASK_SUMMARY:
        user_request = "Resume este documento"
        percentage = st.slider("Porcentaje de resumen", 10, 80, 30, step=10)

    elif task == TASK_ANALYTICS:
        user_request = (
            "Extrae métricas clave de estados financieros y genera gráficas "
            "comparativas con insights relevantes."
        )
        st.info(
            "El modo de análisis financiero extrae métricas estructuradas, "
            "variaciones porcentuales, insights y gráficas comparativas."
        )

    elif task == TASK_COMPARE:
        with st.sidebar:
            st.warning("Sube un segundo documento para comparar.")
            second_file = st.file_uploader(
                "Documento comparativo (.pdf, .docx, .txt, .csv, .md)",
                type=ALLOWED_FILE_TYPES,
                key="second_file",
            )

        user_request = (
            "Compara estos dos documentos identificando similitudes, diferencias, "
            "ventajas, desventajas y una conclusión breve."
        )
        st.info(
            "El modo de comparación devuelve highlights breves sobre similitudes, "
            "diferencias, ventajas, desventajas y conclusión."
        )

    else:
        user_request = st.text_input(
            "Pregunta sobre el documento",
            placeholder="Ejemplo: ¿Cuáles son los principales riesgos mencionados?",
        )
        st.info(
            "El modo QA-RAG recupera fragmentos relevantes del documento y responde usando ese contexto."
        )

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
        "Selecciona la tarea a realizar",
        [TASK_SUMMARY, TASK_ANALYTICS, TASK_COMPARE, TASK_QA],
    )

    reset_on_task_change(task)

    percentage, user_request, second_file = render_task_controls(task)

    if st.button("Procesar documento"):
        validate_before_submit(task, uploaded_file, second_file, user_request)

        with st.spinner("Procesando..."):
            try:
                result = post_agent_request(
                    uploaded_file=uploaded_file,
                    second_file=second_file,
                    percentage=percentage,
                    user_request=user_request,
                )

                st.session_state.last_result = result
                st.session_state.last_summary_text = (
                    result.get("summary_result", {}) or {}
                ).get("summary")
                st.session_state.export_file_bytes = None
                st.session_state.export_file_format = None

            except requests.exceptions.RequestException as exc:
                st.error(f"Error conectando con el backend: {exc}")
                st.stop()

    render_result(st.session_state.last_result)


if __name__ == "__main__":
    main()