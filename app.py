import requests
import streamlit as st
import pandas as pd

BACKEND_AGENT_URL = "http://127.0.0.1:8000/api/agent/execute"
BACKEND_EXPORT_URL = "http://127.0.0.1:8000/api/export"

st.set_page_config(page_title="Agentic Document Processor", layout="wide")

st.title("📄 Agentic Document Processor")

uploaded_file = st.file_uploader(
    "Sube un documento (.pdf, .docx, .txt)",
    type=["pdf", "docx", "txt"]
)

user_request = st.text_input(
    "¿Qué quieres hacer con el documento?",
    value="Resume este documento"
)

percentage = st.slider("Porcentaje de resumen", 10, 80, 30)

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "last_summary_text" not in st.session_state:
    st.session_state.last_summary_text = None

if st.button("Procesar documento"):
    if not uploaded_file:
        st.error("Debes subir un archivo.")
        st.stop()

    with st.spinner("Procesando..."):
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue())
        }

        data = {
            "percentage": str(percentage),
            "user_request": user_request
        }

        try:
            response = requests.post(
                BACKEND_AGENT_URL,
                files=files,
                data=data,
                timeout=300
            )

            if response.status_code != 200:
                try:
                    error_payload = response.json()
                    st.error(error_payload)
                except Exception:
                    st.error(response.text)
                st.stop()

            result = response.json()
            st.session_state.last_result = result

            summary_result = result.get("summary_result")
            if summary_result:
                st.session_state.last_summary_text = summary_result.get("summary")
            else:
                st.session_state.last_summary_text = None

        except requests.exceptions.RequestException as exc:
            st.error(f"Error conectando con el backend: {exc}")
            st.stop()

result = st.session_state.last_result

if result:
    st.success("Procesamiento completado")

    st.subheader("Información general")
    st.write("Tipo de documento:", result.get("document_type"))
    st.write("Intención detectada:", result.get("user_intent"))

    summary = result.get("summary_result")

    if summary:
        st.subheader("Resumen")

        st.write("Palabras originales:", summary.get("original_words"))
        st.write("Palabras objetivo:", summary.get("target_words"))
        st.write("Palabras reales:", summary.get("summary_words"))

        if summary.get("was_capped"):
            st.warning("El resumen fue limitado a 5000 palabras")

        summary_text = summary.get("summary", "")
        st.text_area("Resumen generado", summary_text, height=350)

        st.subheader("⬇️ Descargar resumen")
        output_format = st.selectbox(
            "Formato de exportación",
            ["txt", "pdf", "docx"],
            key="export_format"
        )

        if st.button("Generar archivo descargable"):
            try:
                export_response = requests.post(
                    BACKEND_EXPORT_URL,
                    data={
                        "summary": summary_text,
                        "output_format": output_format
                    },
                    timeout=300
                )

                if export_response.status_code != 200:
                    try:
                        error_payload = export_response.json()
                        st.error(error_payload)
                    except Exception:
                        st.error(export_response.text)
                    st.stop()

                mime_map = {
                    "txt": "text/plain",
                    "pdf": "application/pdf",
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }

                st.download_button(
                    label=f"Descargar resumen en {output_format.upper()}",
                    data=export_response.content,
                    file_name=f"resumen.{output_format}",
                    mime=mime_map[output_format]
                )

            except requests.exceptions.RequestException as exc:
                st.error(f"Error al exportar el resumen: {exc}")

    analytics = result.get("analytics_result")

    if analytics:
        st.subheader("Analytics")

        rows = analytics.get("rows", [])
        metrics = analytics.get("metrics", [])
        percentages = analytics.get("percentages", [])
        charts = analytics.get("chart_specs", [])
        insights = analytics.get("insights", [])

        if insights:
            st.write("### Insights")
            for insight in insights:
                st.write(f"- {insight}")

        if rows:
            st.write("### Filas financieras estructuradas")
            df_rows = pd.DataFrame(rows)
            st.dataframe(df_rows, use_container_width=True)

        if metrics:
            st.write("### Métricas detectadas")
            df_metrics = pd.DataFrame(metrics)
            st.dataframe(df_metrics, use_container_width=True)

        if percentages:
            st.write("### Variaciones porcentuales")
            df_percentages = pd.DataFrame(percentages)
            st.dataframe(df_percentages, use_container_width=True)

        if charts:
            st.write("### Gráficas")

            for idx, chart in enumerate(charts, start=1):
                st.write(f"#### {chart.get('title', f'Gráfico {idx}')}")

                if chart.get("reason"):
                    st.caption(chart["reason"])

                series_list = chart.get("series", [])

                if not series_list:
                    st.info("No hay series de datos para este gráfico.")
                    continue

                rows_for_chart = []

                for serie in series_list:
                    serie_name = serie.get("name", "Serie")

                    for point in serie.get("data", []):
                        rows_for_chart.append(
                            {
                                "x": point.get("x"),
                                "series": serie_name,
                                "y": point.get("y"),
                            }
                        )

                if not rows_for_chart:
                    st.info("No hay puntos de datos para este gráfico.")
                    continue

                df_chart = pd.DataFrame(rows_for_chart)

                if not {"x", "series", "y"}.issubset(df_chart.columns):
                    st.info("Formato de gráfico no válido.")
                    continue

                try:
                    pivot_df = df_chart.pivot(
                        index="x",
                        columns="series",
                        values="y",
                    )
                except Exception as exc:
                    st.error(f"No se pudo preparar el gráfico: {exc}")
                    continue

                chart_type = chart.get("chart_type", "bar")

                if chart_type == "bar":
                    st.bar_chart(pivot_df)
                elif chart_type == "line":
                    st.line_chart(pivot_df)
                else:
                    st.write(f"Tipo de gráfico no soportado todavía: {chart_type}")

        analytics_warnings = analytics.get("warnings", [])
        if analytics_warnings:
            st.warning(analytics_warnings)

    warnings = result.get("warnings", [])
    if warnings:
        st.warning(warnings)

    errors = result.get("errors", [])
    if errors:
        st.error(errors)