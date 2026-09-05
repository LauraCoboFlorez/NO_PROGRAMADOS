"""Explorador automático de datos.

Aplicación Streamlit para cargar archivos tabulares y ejecutar un análisis
exploratorio sin almacenar permanentemente los datos.
"""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Explorador automático de datos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATE_HINTS = ("fecha", "date")


@st.cache_data(show_spinner=False)
def read_dataset(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Lee un archivo cargado y normaliza únicamente los nombres de columnas."""
    extension = file_name.rsplit(".", 1)[-1].lower()
    buffer = BytesIO(file_bytes)

    if extension == "csv":
        # Intenta codificaciones y separadores habituales sin imponer un formato.
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                buffer.seek(0)
                dataframe = pd.read_csv(buffer, encoding=encoding, sep=None, engine="python")
                break
            except Exception as error:  # se informa el último error si todos fallan
                last_error = error
        else:
            raise ValueError(f"No fue posible interpretar el CSV: {last_error}")
    elif extension == "xlsx":
        dataframe = pd.read_excel(buffer, engine="openpyxl")
    elif extension == "xls":
        dataframe = pd.read_excel(buffer, engine="xlrd")
    else:
        raise ValueError("Formato no admitido. Use CSV, XLSX o XLS.")

    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    return recognize_date_columns(dataframe)


def recognize_date_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas sugeridas por su nombre cuando la conversión es razonable."""
    result = dataframe.copy()
    for column in result.columns:
        normalized_name = str(column).lower()
        if any(hint in normalized_name for hint in DATE_HINTS) and not pd.api.types.is_datetime64_any_dtype(result[column]):
            non_null_count = int(result[column].notna().sum())
            if non_null_count == 0:
                continue
            try:
                converted = pd.to_datetime(result[column], errors="coerce", dayfirst=True)
                # Evita destruir contenido: solo convierte si al menos el 80 % es reconocible.
                if int(converted.notna().sum()) / non_null_count >= 0.80:
                    result[column] = converted
            except (ValueError, TypeError, OverflowError):
                pass
    return result


def analytical_type(series: pd.Series) -> str:
    """Interpreta el tipo analítico sin modificar la serie."""
    if pd.api.types.is_bool_dtype(series):
        return "Booleana"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "Fecha/hora"
    if pd.api.types.is_numeric_dtype(series):
        return "Numérica"
    non_null = series.dropna()
    unique_count = int(non_null.nunique())
    total_count = len(non_null)
    if pd.api.types.is_categorical_dtype(series.dtype):
        return "Categórica"
    if total_count == 0:
        return "Texto"
    # Criterio documentado para diferenciar etiquetas de texto libre.
    if unique_count <= min(50, max(10, int(total_count * 0.20))):
        return "Categórica"
    return "Texto"


def columns_by_type(dataframe: pd.DataFrame, type_name: str) -> list[str]:
    return [column for column in dataframe.columns if analytical_type(dataframe[column]) == type_name]


def type_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Variable": dataframe.columns,
            "Tipo Pandas": [str(dataframe[column].dtype) for column in dataframe.columns],
            "Tipo analítico": [analytical_type(dataframe[column]) for column in dataframe.columns],
            "Valores no nulos": [int(dataframe[column].notna().sum()) for column in dataframe.columns],
            "Valores únicos": [int(dataframe[column].nunique(dropna=True)) for column in dataframe.columns],
        }
    )


def missing_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    missing = dataframe.isna().sum()
    denominator = len(dataframe)
    percentages = missing.div(denominator).mul(100) if denominator else missing.astype(float)
    return (
        pd.DataFrame(
            {
                "Variable": dataframe.columns,
                "Valores faltantes": missing.values.astype(int),
                "Porcentaje faltante": percentages.values,
            }
        )
        .sort_values(["Valores faltantes", "Variable"], ascending=[False, True])
        .reset_index(drop=True)
    )


def dataframe_to_csv(dataframe: pd.DataFrame) -> bytes:
    """Genera un CSV en memoria con BOM, apropiado para Excel."""
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def safe_numeric_range(series: pd.Series) -> tuple[float, float] | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    minimum, maximum = float(values.min()), float(values.max())
    if not np.isfinite(minimum) or not np.isfinite(maximum):
        return None
    return minimum, maximum


def apply_sidebar_filters(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Construye filtros y conserva valores faltantes según la especificación."""
    filtered = dataframe.copy()
    date_columns = columns_by_type(dataframe, "Fecha/hora")
    categorical_columns = columns_by_type(dataframe, "Categórica") + columns_by_type(dataframe, "Booleana")
    numeric_columns = columns_by_type(dataframe, "Numérica")

    st.sidebar.header("Filtros interactivos")
    st.sidebar.caption("Los valores faltantes se conservan en filtros de fecha y numéricos.")

    with st.sidebar.expander("Filtros por fecha", expanded=False):
        selected_dates = st.multiselect("Variables de fecha", date_columns, key="date_filter_columns")
        for column in selected_dates:
            valid = dataframe[column].dropna()
            if valid.empty:
                st.info(f"{column}: no contiene fechas válidas.")
                continue
            min_date, max_date = valid.min().date(), valid.max().date()
            chosen = st.date_input(
                f"Rango para {column}",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key=f"date_range_{column}",
            )
            if isinstance(chosen, (tuple, list)) and len(chosen) == 2:
                start, end = pd.Timestamp(chosen[0]), pd.Timestamp(chosen[1]) + pd.Timedelta(days=1)
                mask = filtered[column].isna() | ((filtered[column] >= start) & (filtered[column] < end))
                filtered = filtered.loc[mask]

    with st.sidebar.expander("Filtros categóricos", expanded=False):
        selected_categories = st.multiselect(
            "Variables categóricas", categorical_columns, key="category_filter_columns"
        )
        for column in selected_categories:
            available = dataframe[column].dropna().unique().tolist()
            available = sorted(available, key=lambda value: str(value))
            chosen = st.multiselect(
                f"Categorías de {column}", available, default=available, key=f"category_values_{column}"
            )
            if chosen:
                filtered = filtered.loc[filtered[column].isin(chosen)]
            else:
                filtered = filtered.iloc[0:0]

    with st.sidebar.expander("Filtros numéricos", expanded=False):
        selected_numeric = st.multiselect("Variables numéricas", numeric_columns, key="numeric_filter_columns")
        for column in selected_numeric:
            limits = safe_numeric_range(dataframe[column])
            if limits is None:
                st.info(f"{column}: no contiene valores numéricos finitos.")
                continue
            minimum, maximum = limits
            if minimum == maximum:
                st.caption(f"{column}: todos los valores válidos son {minimum:g}.")
                continue
            chosen_min, chosen_max = st.slider(
                f"Rango para {column}",
                min_value=minimum,
                max_value=maximum,
                value=(minimum, maximum),
                key=f"numeric_range_{column}",
            )
            numeric = pd.to_numeric(filtered[column], errors="coerce")
            mask = numeric.isna() | numeric.between(chosen_min, chosen_max, inclusive="both")
            filtered = filtered.loc[mask]

    st.sidebar.metric("Registros resultantes", len(filtered))
    return filtered


def detect_outliers(
    dataframe: pd.DataFrame, selected_columns: Iterable[str], factor: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve detalle por detección y resumen por variable usando IQR."""
    detections: list[pd.DataFrame] = []
    summary_rows: list[dict] = []

    for column in selected_columns:
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        valid = numeric.dropna()
        if valid.empty:
            lower = upper = np.nan
            mask = pd.Series(False, index=dataframe.index)
        else:
            q1, q3 = valid.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower, upper = q1 - factor * iqr, q3 + factor * iqr
            mask = numeric.notna() & ((numeric < lower) | (numeric > upper))

        summary_rows.append({"Variable": column, "Cantidad de atípicos": int(mask.sum())})
        if mask.any():
            detail = dataframe.loc[mask].copy()
            detail.insert(0, "Fila original", dataframe.index[mask])
            detail.insert(1, "Variable atípica", column)
            detail.insert(2, "Valor detectado", numeric.loc[mask].values)
            detail.insert(3, "Límite inferior", lower)
            detail.insert(4, "Límite superior", upper)
            detections.append(detail)

    detail_result = pd.concat(detections, ignore_index=True) if detections else pd.DataFrame()
    return detail_result, pd.DataFrame(summary_rows)


def render_welcome() -> None:
    st.info("Carga un archivo desde la barra lateral para comenzar el análisis.")
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Formatos permitidos")
        st.markdown("- CSV\n- Excel XLSX\n- Excel XLS")
        st.subheader("Etapas de uso")
        st.markdown("1. **Cargar** el archivo.\n2. **Explorar** resultados y aplicar filtros.\n3. **Descargar** los datos filtrados y los atípicos.")
    with right:
        st.subheader("Análisis disponibles")
        st.markdown(
            "- Dimensiones y tipos de variables\n"
            "- Duplicados y valores faltantes\n"
            "- Estadísticas descriptivas\n"
            "- Distribuciones y diagramas de caja\n"
            "- Correlaciones\n"
            "- Detección de valores atípicos por IQR\n"
            "- Tabla interactiva y exportación"
        )
    st.warning("No se generan datos ficticios. El análisis comienza únicamente después de cargar un archivo.")


def descriptive_statistics(dataframe: pd.DataFrame, option: str) -> pd.DataFrame:
    numeric_columns = columns_by_type(dataframe, "Numérica")
    categorical_columns = columns_by_type(dataframe, "Categórica") + columns_by_type(dataframe, "Texto") + columns_by_type(dataframe, "Booleana")
    if option == "Solo variables numéricas":
        if not numeric_columns:
            raise ValueError("El dataset filtrado no contiene variables numéricas.")
        result = dataframe[numeric_columns].describe().T
    elif option == "Solo variables categóricas":
        if not categorical_columns:
            raise ValueError("El dataset filtrado no contiene variables categóricas o de texto.")
        result = dataframe[categorical_columns].describe(include="all").T
    else:
        if dataframe.shape[1] == 0:
            raise ValueError("No hay variables disponibles.")
        result = dataframe.describe(include="all", datetime_is_numeric=True).T
    return result.reset_index(names="Variable")


def main() -> None:
    st.title("📊 Explorador automático de datos")
    st.write(
        "Carga un conjunto de datos y obtén automáticamente un análisis exploratorio, "
        "sin depender de archivos predeterminados ni rutas fijas."
    )

    st.sidebar.title("Carga del dataset")
    uploaded_file = st.sidebar.file_uploader(
        "Selecciona un archivo", type=["csv", "xlsx", "xls"], help="Formatos admitidos: CSV, XLSX y XLS."
    )

    if uploaded_file is None:
        render_welcome()
        st.stop()

    try:
        original_df = read_dataset(uploaded_file.getvalue(), uploaded_file.name)
    except Exception as error:
        st.error(f"No fue posible procesar el archivo. Verifica su formato y contenido. Detalle: {error}")
        st.stop()

    if original_df.empty or len(original_df.columns) == 0:
        st.warning("El archivo está vacío o no contiene una estructura tabular utilizable.")
        st.stop()

    st.sidebar.success(f"Archivo cargado: {uploaded_file.name}")
    filtered_df = apply_sidebar_filters(original_df)

    if filtered_df.empty:
        st.warning("Los filtros no producen registros. Ajusta los filtros de la barra lateral para continuar.")
        st.stop()

    st.caption(
        f"Archivo: **{uploaded_file.name}** | Dimensiones actuales: **{filtered_df.shape[0]} filas × "
        f"{filtered_df.shape[1]} columnas**"
    )

    metric_columns = st.columns(4)
    metric_columns[0].metric("Filas", filtered_df.shape[0])
    metric_columns[1].metric("Columnas", filtered_df.shape[1])
    metric_columns[2].metric("Duplicados completos", int(filtered_df.duplicated().sum()))
    metric_columns[3].metric("Celdas faltantes", int(filtered_df.isna().sum().sum()))

    numeric_columns = columns_by_type(filtered_df, "Numérica")
    categorical_columns = columns_by_type(filtered_df, "Categórica") + columns_by_type(filtered_df, "Booleana")

    tabs = st.tabs(
        [
            "Resumen y tipos",
            "Calidad de datos",
            "Estadísticas",
            "Distribuciones",
            "Correlaciones",
            "Valores atípicos",
            "Tabla ordenable",
        ]
    )

    with tabs[0]:
        st.subheader("Dimensiones del dataset")
        col1, col2, col3 = st.columns(3)
        col1.metric("Cantidad de filas", filtered_df.shape[0])
        col2.metric("Cantidad de columnas", filtered_df.shape[1])
        col3.write("**Nombre del archivo**")
        col3.write(uploaded_file.name)
        st.subheader("Tipos de variables")
        st.dataframe(type_summary(filtered_df), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Registros duplicados")
        duplicated_count = int(filtered_df.duplicated().sum())
        if duplicated_count == 0:
            st.success("No se encontraron filas completamente duplicadas.")
        else:
            st.warning(f"Se encontraron {duplicated_count} duplicados adicionales.")
            st.dataframe(filtered_df.loc[filtered_df.duplicated(keep=False)], use_container_width=True)

        st.subheader("Valores faltantes")
        missing = missing_summary(filtered_df)
        st.dataframe(
            missing.style.format({"Porcentaje faltante": "{:.2f}%"}),
            use_container_width=True,
            hide_index=True,
        )
        chart_data = missing.loc[missing["Valores faltantes"] > 0]
        if chart_data.empty:
            st.success("No se encontraron valores faltantes.")
        else:
            figure = px.bar(
                chart_data,
                x="Variable",
                y="Porcentaje faltante",
                title="Porcentaje de valores faltantes por variable",
                labels={"Porcentaje faltante": "Porcentaje (%)"},
            )
            st.plotly_chart(figure, use_container_width=True)

    with tabs[2]:
        st.subheader("Estadísticas descriptivas")
        stats_option = st.radio(
            "Variables que se incluirán",
            ["Todas las variables", "Solo variables numéricas", "Solo variables categóricas"],
            horizontal=True,
        )
        try:
            st.dataframe(descriptive_statistics(filtered_df, stats_option), use_container_width=True, hide_index=True)
        except (ValueError, TypeError) as error:
            st.info(str(error))

    with tabs[3]:
        st.subheader("Distribuciones")
        selected_variable = st.selectbox("Selecciona una variable", filtered_df.columns)
        variable_kind = analytical_type(filtered_df[selected_variable])

        if variable_kind == "Numérica":
            bins = st.slider("Número de intervalos", 5, 100, 30)
            histogram = px.histogram(
                filtered_df,
                x=selected_variable,
                nbins=bins,
                title=f"Distribución de {selected_variable}",
            )
            st.plotly_chart(histogram, use_container_width=True)

            grouping_options = ["Sin agrupación"] + [column for column in categorical_columns if column != selected_variable]
            group_column = st.selectbox("Agrupar diagrama de caja", grouping_options)
            box_kwargs = {"x": group_column, "y": selected_variable} if group_column != "Sin agrupación" else {"y": selected_variable}
            boxplot = px.box(
                filtered_df,
                **box_kwargs,
                points="outliers",
                title=f"Diagrama de caja de {selected_variable}",
            )
            st.plotly_chart(boxplot, use_container_width=True)
        else:
            values = filtered_df[selected_variable].astype("object").where(filtered_df[selected_variable].notna(), "(Faltante)")
            frequencies = values.astype(str).value_counts(dropna=False).head(30).rename_axis("Categoría").reset_index(name="Frecuencia")
            if filtered_df[selected_variable].nunique(dropna=False) > 30:
                st.info("La visualización se limita a las 30 categorías más frecuentes.")
            bar_chart = px.bar(
                frequencies,
                x="Categoría",
                y="Frecuencia",
                title=f"Frecuencias de {selected_variable}",
            )
            st.plotly_chart(bar_chart, use_container_width=True)
            st.dataframe(frequencies, use_container_width=True, hide_index=True)

    with tabs[4]:
        st.subheader("Correlaciones")
        if len(numeric_columns) < 2:
            st.info("Se necesitan al menos dos variables numéricas para calcular correlaciones.")
        else:
            correlation_columns = st.multiselect(
                "Variables numéricas", numeric_columns, default=numeric_columns
            )
            method_label = st.selectbox("Método", ["Pearson", "Spearman", "Kendall"])
            if len(correlation_columns) < 2:
                st.warning("Selecciona al menos dos variables.")
            else:
                matrix = filtered_df[correlation_columns].corr(method=method_label.lower())
                heatmap = go.Figure(
                    data=go.Heatmap(
                        z=matrix.values,
                        x=matrix.columns,
                        y=matrix.index,
                        zmin=-1,
                        zmax=1,
                        colorscale="RdBu",
                        reversescale=True,
                        text=np.round(matrix.values, 2),
                        texttemplate="%{text}",
                        hovertemplate="%{y} / %{x}: %{z:.3f}<extra></extra>",
                    )
                )
                heatmap.update_layout(title=f"Matriz de correlación de {method_label}")
                st.plotly_chart(heatmap, use_container_width=True)
                st.dataframe(matrix.style.format("{:.3f}"), use_container_width=True)
                st.caption("Una correlación no implica causalidad.")

    with tabs[5]:
        st.subheader("Valores atípicos por rango intercuartílico")
        if not numeric_columns:
            st.info("El dataset filtrado no contiene variables numéricas.")
            outlier_details = pd.DataFrame()
        else:
            selected_outlier_columns = st.multiselect(
                "Variables numéricas", numeric_columns, default=numeric_columns
            )
            factor = st.slider("Factor IQR", 1.0, 3.0, 1.5, 0.1)
            if not selected_outlier_columns:
                st.warning("Selecciona al menos una variable numérica.")
                outlier_details = pd.DataFrame()
            else:
                outlier_details, outlier_summary = detect_outliers(
                    filtered_df, selected_outlier_columns, factor
                )
                st.metric("Número de detecciones", len(outlier_details))
                outlier_chart = px.bar(
                    outlier_summary,
                    x="Variable",
                    y="Cantidad de atípicos",
                    title="Cantidad de valores atípicos por variable",
                )
                st.plotly_chart(outlier_chart, use_container_width=True)
                if outlier_details.empty:
                    st.success("No se detectaron valores atípicos con la configuración actual.")
                else:
                    st.dataframe(outlier_details, use_container_width=True, hide_index=True)
                st.caption("Un valor atípico no necesariamente representa un error.")

        st.download_button(
            "Descargar valores atípicos",
            data=dataframe_to_csv(outlier_details),
            file_name="valores_atipicos.csv",
            mime="text/csv",
            disabled=outlier_details.empty,
        )

    with tabs[6]:
        st.subheader("Tabla interactiva y ordenable")
        visible_columns = st.multiselect(
            "Selecciona las columnas visibles", filtered_df.columns, default=list(filtered_df.columns)
        )
        if not visible_columns:
            st.info("Selecciona al menos una columna para mostrar la tabla.")
        else:
            st.dataframe(
                filtered_df[visible_columns],
                use_container_width=True,
                hide_index=True,
                height=520,
            )
        st.download_button(
            "Descargar datos filtrados",
            data=dataframe_to_csv(filtered_df),
            file_name="datos_filtrados.csv",
            mime="text/csv",
        )

    st.divider()
    st.warning(
        "Tratamiento responsable de los datos: la información se procesa durante la sesión. "
        "Evita cargar información personal, confidencial o sensible. Este análisis exploratorio "
        "no reemplaza la interpretación experta. Una correlación no implica causalidad y un valor "
        "atípico no necesariamente representa un error."
    )


if __name__ == "__main__":
    main()
