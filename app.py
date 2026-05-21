from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from src.buffer_model import calculate_dataset
from src.charts import buffer_comparison, ibuf_bar, metric_bar, pshort_bar, scenario_delta_chart, status_change_bar, status_pie
from src.coefficients import coefficient_preview
from src.data_loader import create_flat_template_bytes, load_uploaded_data
from src.demo_data import empty_input_dataframe, get_demo_dataframe
from src.diagrams import architecture_diagram, process_diagram
from src.export import multi_sheet_export_bytes
from src.recommendations import add_recommendations
from src.schema import COEFF_MODES, CRITICALITY_CLASSES, REQUIRED_COLUMNS
from src.status_rules import DEFAULT_CRITICAL_THRESHOLD, DEFAULT_NORMAL_THRESHOLD, DEFAULT_SURPLUS_THRESHOLD
from src.validation import limit_errors, normalize_dataframe, validate_dataframe

st.set_page_config(
    page_title="Контроль буферных запасов ROP",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "Модуль оценки и непрерывного контроля буферных запасов для ROP"
SCENARIOS = ["Стабильный режим", "Средний режим", "Кризисный режим"]
STATUS_LIST = ["Критическое отклонение", "Предупреждение", "Норма", "Избыточный буфер"]

DISPLAY_NAMES = {
    "Ibuf": "Индекс обеспеченности буфера",
    "Bopt": "Оптимальный буфер",
    "Btar": "Целевой буфер",
    "Bstat": "Статистический буфер",
    "A": "Доступная позиция",
    "Pshort": "Вероятность дефицита при оптимальном буфере",
    "Pshort_current": "Текущая вероятность дефицита",
    "reorder_point": "Точка заказа",
    "sigma_LT": "Неопределённость спроса за срок пополнения",
    "z": "Адаптивный коэффициент надёжности",
    "Kload": "Коэффициент загрузки ROP",
    "holding_cost": "Затраты на хранение",
    "expected_stop_loss": "Ожидаемые потери от простоя",
}


def show_toast(message: str, icon: str = "ℹ️") -> None:
    """Show a short non-blocking Streamlit notification."""
    if hasattr(st, "toast"):
        st.toast(message, icon=icon)
    else:
        st.info(message)


def show_validation_errors(errors: list[str]) -> None:
    """Show validation errors in a modal dialog when available."""
    limited = limit_errors(errors)
    if hasattr(st, "dialog"):
        @st.dialog("Ошибка валидации данных")
        def _dialog():
            st.write("Исправьте ошибки и повторите расчёт:")
            for err in limited:
                st.error(err)
        _dialog()
    else:
        st.error("Ошибка валидации данных")
        for err in limited:
            st.write(f"- {err}")


def current_thresholds() -> tuple[float, float, float]:
    """Return status thresholds from session state."""
    return (
        float(st.session_state.get("critical_threshold", DEFAULT_CRITICAL_THRESHOLD)),
        float(st.session_state.get("normal_threshold", DEFAULT_NORMAL_THRESHOLD)),
        float(st.session_state.get("surplus_threshold", DEFAULT_SURPLUS_THRESHOLD)),
    )


@st.cache_data(show_spinner="Расчёт буфера...")
def cached_calculate(df: pd.DataFrame, critical_threshold: float, normal_threshold: float, surplus_threshold: float) -> pd.DataFrame:
    """Cached wrapper around the model calculation."""
    return calculate_dataset(df, critical_threshold, normal_threshold, surplus_threshold)


def calculate_current(df: pd.DataFrame, silent: bool = False) -> pd.DataFrame:
    """Normalize, validate and calculate the current working dataset."""
    normalized = normalize_dataframe(df)
    errors = validate_dataframe(normalized)
    if errors:
        if not silent:
            show_validation_errors(errors)
        return pd.DataFrame()
    calculated = cached_calculate(normalized, *current_thresholds())
    return add_recommendations(calculated)


def init_state() -> None:
    """Initialize Streamlit session state."""
    defaults = {
        "scenario_name": "Стабильный режим",
        "critical_threshold": DEFAULT_CRITICAL_THRESHOLD,
        "normal_threshold": DEFAULT_NORMAL_THRESHOLD,
        "surplus_threshold": DEFAULT_SURPLUS_THRESHOLD,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if "input_df" not in st.session_state:
        st.session_state.input_df = get_demo_dataframe(st.session_state.scenario_name)
    if "calculated_df" not in st.session_state:
        st.session_state.calculated_df = calculate_current(st.session_state.input_df, silent=True)


def _summary_metrics(df: pd.DataFrame) -> dict[str, str | int | float]:
    """Return compact metrics for sidebar and dashboard."""
    if df.empty:
        return {"total": 0, "avg_ibuf": "н/д", "critical": 0, "warning": 0, "surplus": 0}
    avg_ibuf = df["Ibuf"].replace([float("inf"), -float("inf")], pd.NA).dropna().mean()
    return {
        "total": len(df),
        "avg_ibuf": f"{avg_ibuf:.2f}" if pd.notna(avg_ibuf) else "н/д",
        "critical": int((df["status"] == "Критическое отклонение").sum()),
        "warning": int((df["status"] == "Предупреждение").sum()),
        "surplus": int((df["status"] == "Избыточный буфер").sum()),
    }


def sidebar_controls() -> None:
    """Render sidebar controls for data source, status thresholds and recalculation."""
    st.sidebar.title("⚙️ Управление")
    st.sidebar.caption("Выберите источник данных и режим работы.")

    with st.sidebar.expander("Пороговые значения статусов", expanded=False):
        critical = st.slider("Критический порог Ibuf", 0.10, 0.95, float(st.session_state.critical_threshold), 0.05)
        normal = st.slider("Порог нормы Ibuf", 0.75, 1.30, float(st.session_state.normal_threshold), 0.05)
        surplus = st.slider("Порог избыточности Ibuf", 1.10, 3.00, float(st.session_state.surplus_threshold), 0.05)
        if not (critical < normal < surplus):
            st.error("Пороги статусов пересекаются. Должно выполняться: критический порог < порог нормы < порог избыточности. Пока это условие не выполнено, новые пороги не применяются.")
            st.caption("Например: 0,70 < 1,00 < 1,50. Пересечение порогов делает классификацию статусов неоднозначной.")
        elif (critical, normal, surplus) != current_thresholds():
            st.session_state.critical_threshold = critical
            st.session_state.normal_threshold = normal
            st.session_state.surplus_threshold = surplus
            st.session_state.calculated_df = calculate_current(st.session_state.input_df, silent=True)

    source = st.sidebar.radio(
        "Источник данных",
        ["Встроенные демо-данные", "Ручной ввод", "Загрузка Excel/CSV"],
        index=0,
    )

    if source == "Встроенные демо-данные":
        scenario = st.sidebar.selectbox(
            "Демо-сценарий",
            SCENARIOS,
            index=SCENARIOS.index(st.session_state.scenario_name),
        )
        if st.sidebar.button("Загрузить демо-сценарий", use_container_width=True):
            st.session_state.scenario_name = scenario
            st.session_state.input_df = get_demo_dataframe(scenario)
            st.session_state.calculated_df = calculate_current(st.session_state.input_df)
            show_toast("Демо-сценарий загружен", "✅")
        if st.sidebar.button("Сбросить к исходному демо", use_container_width=True):
            st.session_state.input_df = get_demo_dataframe(st.session_state.scenario_name)
            st.session_state.calculated_df = calculate_current(st.session_state.input_df)
            show_toast("Данные восстановлены", "🔄")

    elif source == "Ручной ввод":
        rows = st.sidebar.number_input("Количество строк", min_value=1, max_value=100, value=5, step=1)
        if st.sidebar.button("Создать пустую таблицу", use_container_width=True):
            st.session_state.input_df = empty_input_dataframe(int(rows))
            st.session_state.calculated_df = calculate_current(st.session_state.input_df)
            show_toast("Пустая таблица создана", "✅")

    else:
        uploaded = st.sidebar.file_uploader("Загрузите Excel- или CSV-файл", type=["xlsx", "xls", "csv"])
        if uploaded is not None:
            try:
                st.session_state.input_df = load_uploaded_data(uploaded, uploaded.name)
                st.session_state.calculated_df = calculate_current(st.session_state.input_df)
                show_toast("Файл загружен", "✅")
            except Exception as exc:
                st.sidebar.error(f"Не удалось загрузить файл: {exc}")
        template_bytes = create_flat_template_bytes(rows=5)
        st.sidebar.download_button(
            "Скачать шаблон Excel",
            data=template_bytes,
            file_name="buffer_input_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_template_excel",
        )

    st.sidebar.divider()
    if st.sidebar.button("Пересчитать текущие данные", use_container_width=True):
        st.session_state.calculated_df = calculate_current(st.session_state.input_df)
        if not st.session_state.calculated_df.empty:
            show_toast("Расчёт выполнен", "✅")

    metrics = _summary_metrics(st.session_state.get("calculated_df", pd.DataFrame()))
    st.sidebar.divider()
    st.sidebar.caption("Краткая статистика")
    st.sidebar.metric("Всего позиций", metrics["total"])
    st.sidebar.metric("Средний индекс обеспеченности буфера", metrics["avg_ibuf"])
    st.sidebar.metric("Критические", metrics["critical"])
    st.sidebar.metric("Предупреждения", metrics["warning"])
    st.sidebar.metric("Избыточные", metrics["surplus"])


def apply_filters(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    """Render common filters and return filtered dataframe."""
    if df.empty:
        return df
    c1, c2, c3 = st.columns(3)
    rops = ["Все"] + sorted(df["rop_name"].dropna().astype(str).unique().tolist())
    selected_rop = c1.selectbox("Ограничивающий ресурс", rops, key=f"{key_prefix}_rop")
    selected_status = c2.multiselect("Статус", STATUS_LIST, default=[], key=f"{key_prefix}_status")
    selected_criticality = c3.multiselect("Класс критичности", CRITICALITY_CLASSES, default=[], key=f"{key_prefix}_crit")
    view = df.copy()
    if selected_rop != "Все":
        view = view[view["rop_name"] == selected_rop]
    if selected_status:
        view = view[view["status"].isin(selected_status)]
    if selected_criticality:
        view = view[view["criticality_class"].isin(selected_criticality)]
    return view


def dashboard_tab(df: pd.DataFrame) -> None:
    """Dashboard with KPI cards, filters and main charts."""
    st.subheader("Главная панель")
    if df.empty:
        st.warning("Нет рассчитанных данных.")
        return
    view = apply_filters(df, "dash")
    metrics = _summary_metrics(view)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Всего позиций", metrics["total"])
    c2.metric("Критические", metrics["critical"])
    c3.metric("Предупреждения", metrics["warning"])
    c4.metric("Избыточные", metrics["surplus"])
    c5.metric("Средний индекс обеспеченности", metrics["avg_ibuf"])

    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(status_pie(view), use_container_width=True, key="dashboard_status_pie")
    with right:
        st.plotly_chart(pshort_bar(view), use_container_width=True, key="dashboard_pshort_bar")

    st.info(
        f"Пороговые значения индекса обеспеченности буфера: критическое отклонение ≤ {st.session_state.critical_threshold:.2f}; "
        f"предупреждение {st.session_state.critical_threshold:.2f}–{st.session_state.normal_threshold:.2f}; "
        f"норма {st.session_state.normal_threshold:.2f}–{st.session_state.surplus_threshold:.2f}; "
        f"избыточный буфер > {st.session_state.surplus_threshold:.2f}."
    )
    st.plotly_chart(ibuf_bar(view, *current_thresholds()), use_container_width=True, key="dashboard_ibuf_bar")

    st.markdown("#### Наиболее проблемные позиции")
    cols = ["item_id", "item_name", "rop_name", "A", "Bopt", "Pshort_current", "Ibuf", "status", "priority"]
    st.dataframe(view.sort_values(["Ibuf", "Pshort_current"], ascending=[True, False])[cols].head(10), use_container_width=True, hide_index=True)


def _editor(df: pd.DataFrame, cols: list[str], key: str) -> pd.DataFrame:
    """Reusable data editor for a subset of columns."""
    existing = [c for c in cols if c in df.columns]
    return st.data_editor(df[existing], use_container_width=True, num_rows="dynamic", hide_index=True, key=key)


def data_tab() -> None:
    """Working data editor and coefficient preview."""
    st.subheader("Данные")
    st.caption("Редактируется рабочая копия данных. Встроенные демо-сценарии остаются неизменными.")

    df = st.session_state.input_df.copy()
    st.info("В режиме auto коэффициенты Kcrit, Kload и Kdev рассчитываются автоматически. В режиме manual используются значения Kcrit_manual, Kload_manual, Kdev_manual.")
    edited = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "criticality_class": st.column_config.SelectboxColumn("Класс критичности", options=CRITICALITY_CLASSES),
            "coeff_mode": st.column_config.SelectboxColumn("Режим расчёта коэффициентов", options=COEFF_MODES),
        },
        key="data_editor",
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Применить изменения", use_container_width=True):
            normalized = normalize_dataframe(edited)
            errors = validate_dataframe(normalized)
            if errors:
                show_validation_errors(errors)
            else:
                st.session_state.input_df = normalized
                st.session_state.calculated_df = calculate_current(normalized)
                show_toast("Изменения применены", "✅")
                st.rerun()
    with col2:
        if st.button("Сбросить к текущему демо-сценарию", use_container_width=True):
            st.session_state.input_df = get_demo_dataframe(st.session_state.scenario_name)
            st.session_state.calculated_df = calculate_current(st.session_state.input_df)
            show_toast("Демо-данные восстановлены", "🔄")
            st.rerun()
    with col3:
        if st.button("Отменить несохранённые изменения", use_container_width=True):
            st.rerun()

    with st.expander("Основные блоки входных данных", expanded=False):
        st.markdown("**Основные данные**")
        st.dataframe(df[[c for c in ["item_id", "item_name", "unit", "period", "O", "P", "R", "D_avg", "sigma_D", "L_avg", "sigma_L"] if c in df.columns]], use_container_width=True, hide_index=True)
        st.markdown("**Производственные и технические параметры**")
        st.dataframe(df[[c for c in ["rop_name", "criticality_class", "rop_load", "planned_flow", "actual_flow", "p_diag", "p_rep", "h", "Cstop"] if c in df.columns]], use_container_width=True, hide_index=True)

    st.markdown("#### Расчёт производственных коэффициентов")
    preview = coefficient_preview(normalize_dataframe(edited))
    if not preview.empty:
        numeric_cols = preview.select_dtypes(include="number").columns
        preview[numeric_cols] = preview[numeric_cols].round(4)
    st.dataframe(preview, use_container_width=True, hide_index=True)

    st.markdown("#### Обязательные поля")
    st.code(", ".join(REQUIRED_COLUMNS), language="text")


def calculation_tab(df: pd.DataFrame) -> None:
    """Detailed calculation table."""
    st.subheader("Расчёт буфера")
    if df.empty:
        st.warning("Нет рассчитанных данных.")
        return
    display_cols = [
        "item_id", "item_name", "rop_name", "criticality_class", "coeff_mode", "O", "P", "R", "D_avg", "sigma_D", "L_avg", "sigma_L",
        "A", "sigma_LT", "z", "Kcrit", "Kload", "Kdev", "Bstat", "Btar", "Pshort", "Pshort_current", "holding_cost", "expected_stop_loss",
        "expected_total_cost", "Bopt", "reorder_point", "Ibuf", "status", "priority", "risk_reasons", "optimization_note",
    ]
    available_cols = [col for col in display_cols if col in df.columns]
    rounded = df[available_cols].copy()
    numeric_cols = rounded.select_dtypes(include="number").columns
    rounded[numeric_cols] = rounded[numeric_cols].round(4)
    st.dataframe(rounded, use_container_width=True, hide_index=True)
    st.plotly_chart(buffer_comparison(df), use_container_width=True, key="calculation_buffer_comparison_all")


def monitoring_tab(df: pd.DataFrame) -> None:
    """ROP monitoring chart and table."""
    st.subheader("Мониторинг ROP")
    if df.empty:
        st.warning("Нет рассчитанных данных.")
        return
    view = apply_filters(df, "mon")
    st.info(
        f"Пороговые значения индекса обеспеченности буфера: критическое отклонение ≤ {st.session_state.critical_threshold:.2f}; "
        f"предупреждение до {st.session_state.normal_threshold:.2f}; норма до {st.session_state.surplus_threshold:.2f}; "
        f"выше — избыточный буфер."
    )
    st.plotly_chart(ibuf_bar(view, *current_thresholds()), use_container_width=True, key="monitoring_ibuf_bar_view")
    st.plotly_chart(buffer_comparison(view), use_container_width=True, key="monitoring_buffer_comparison_view")
    st.dataframe(view[["item_id", "item_name", "rop_name", "A", "Btar", "Bopt", "reorder_point", "Ibuf", "Pshort_current", "status"]].round(3), use_container_width=True, hide_index=True)


def _apply_scenario(base_df: pd.DataFrame, demand_factor: int, sigma_d_factor: int, lead_factor: int, sigma_l_factor: int, stock_factor: int, cstop_factor: int, rop_load_delta: float, p_diag_delta: float, p_rep_delta: float) -> pd.DataFrame:
    """Return a scenario copy of the base dataframe."""
    scenario_df = base_df.copy()
    scenario_df["D_avg"] = scenario_df["D_avg"] * (1 + demand_factor / 100)
    scenario_df["sigma_D"] = scenario_df["sigma_D"] * (1 + sigma_d_factor / 100)
    scenario_df["L_avg"] = scenario_df["L_avg"] * (1 + lead_factor / 100)
    scenario_df["sigma_L"] = scenario_df["sigma_L"] * (1 + sigma_l_factor / 100)
    scenario_df["O"] = scenario_df["O"] * (1 + stock_factor / 100)
    scenario_df["Cstop"] = scenario_df["Cstop"] * (1 + cstop_factor / 100)
    scenario_df["rop_load"] = (scenario_df["rop_load"] + rop_load_delta).clip(0, 1.5)
    scenario_df["p_diag"] = (scenario_df["p_diag"] + p_diag_delta).clip(0, 1)
    scenario_df["p_rep"] = (scenario_df["p_rep"] + p_rep_delta).clip(0, 1)
    return scenario_df


def scenario_tab() -> None:
    """Live scenario analysis on a copy of the current data."""
    st.subheader("Сценарный анализ")
    base_df = st.session_state.input_df.copy()
    if base_df.empty:
        st.warning("Нет исходных данных.")
        return

    st.caption("Сценарный анализ работает на копии текущих данных и не портит исходную рабочую таблицу. Пересчёт выполняется сразу после изменения параметров.")
    col1, col2, col3 = st.columns(3)
    demand_factor = col1.slider("Изменение среднего спроса D_avg, %", -50, 100, 0, 5)
    sigma_d_factor = col2.slider("Изменение вариативности спроса sigma_D, %", -50, 150, 0, 5)
    lead_factor = col3.slider("Изменение срока поставки L_avg, %", -30, 100, 0, 5)
    col4, col5, col6 = st.columns(3)
    sigma_l_factor = col4.slider("Изменение вариативности поставки sigma_L, %", -30, 150, 0, 5)
    stock_factor = col5.slider("Изменение остатков O, %", -80, 100, 0, 5)
    cstop_factor = col6.slider("Изменение стоимости простоя Cstop, %", -50, 200, 0, 5)
    col7, col8, col9 = st.columns(3)
    rop_load_delta = col7.slider("Добавить к загрузке ROP", -0.30, 0.50, 0.00, 0.01)
    p_diag_delta = col8.slider("Добавить к p_diag", -0.20, 0.40, 0.00, 0.01)
    p_rep_delta = col9.slider("Добавить к p_rep", -0.20, 0.40, 0.00, 0.01)

    before = calculate_current(base_df, silent=True)
    scenario_df = _apply_scenario(base_df, demand_factor, sigma_d_factor, lead_factor, sigma_l_factor, stock_factor, cstop_factor, rop_load_delta, p_diag_delta, p_rep_delta)
    after = calculate_current(scenario_df, silent=True)
    if before.empty or after.empty:
        st.error("Сценарий не рассчитан из-за ошибок в данных.")
        return

    metric = st.selectbox(
        "Показатель для диаграммы изменения",
        ["Bopt", "Ibuf", "A", "Pshort_current", "reorder_point"],
        format_func=lambda value: DISPLAY_NAMES.get(value, value),
    )
    st.info("Изменение остатков O влияет на A, Ibuf, Pshort_current и статус, но не обязано менять Bopt. Изменение спроса, поставки, загрузки ROP, ремонта и затрат обычно влияет на расчётный буфер.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Средний оптимальный буфер", f"{before['Bopt'].mean():.2f}", delta=f"{after['Bopt'].mean() - before['Bopt'].mean():.2f}")
    c2.metric("Средний индекс обеспеченности", f"{before['Ibuf'].mean():.2f}", delta=f"{after['Ibuf'].mean() - before['Ibuf'].mean():.2f}")
    c3.metric("Критические после", int((after["status"] == "Критическое отклонение").sum()))
    c4.metric("Предупреждения после", int((after["status"] == "Предупреждение").sum()))

    st.plotly_chart(scenario_delta_chart(before, after, metric=metric), use_container_width=True, key="scenario_delta_chart_live")
    st.plotly_chart(status_change_bar(before, after), use_container_width=True, key="scenario_status_change")
    merged = before[["item_id", "item_name", "A", "Bopt", "Ibuf", "Pshort_current", "status"]].merge(
        after[["item_id", "A", "Bopt", "Ibuf", "Pshort_current", "status"]], on="item_id", suffixes=("_до", "_после")
    )
    st.dataframe(merged.round(3), use_container_width=True, hide_index=True)


def diagrams_tab(df: pd.DataFrame) -> None:
    """Architecture and process diagrams."""
    st.subheader("Схемы")
    st.plotly_chart(architecture_diagram(), use_container_width=True, key="architecture_diagram")
    if df.empty:
        st.warning("Для процессной схемы нужны рассчитанные данные.")
        return
    item_options = (df["item_id"] + " — " + df["item_name"]).tolist()
    selected = st.selectbox("Позиция для процессной схемы", item_options)
    item_id = selected.split(" — ")[0]
    row = df[df["item_id"] == item_id].iloc[0].to_dict()
    st.plotly_chart(process_diagram(row), use_container_width=True, key="process_diagram")


def recommendations_tab(df: pd.DataFrame) -> None:
    """Management recommendations and recommendation export."""
    st.subheader("Управленческое заключение")
    if df.empty:
        st.warning("Нет рассчитанных данных.")
        return
    status_filter = st.multiselect(
        "Фильтр по статусам",
        STATUS_LIST,
        default=["Критическое отклонение", "Предупреждение", "Избыточный буфер"],
    )
    view = df[df["status"].isin(status_filter)] if status_filter else df
    rec_cols = ["item_id", "item_name", "rop_name", "status", "priority", "A", "Bopt", "Ibuf", "Pshort_current", "risk_reasons", "recommendation"]
    csv = view[rec_cols].to_csv(index=False, encoding="utf-8-sig")
    st.download_button("Скачать рекомендации CSV", data=csv, file_name="buffer_recommendations.csv", mime="text/csv", use_container_width=True, key="download_recommendations_tab_csv")
    for _, row in view.sort_values(["priority", "Ibuf"]).iterrows():
        with st.expander(f"{row['item_id']} — {row['item_name']} | {row['status']} | приоритет: {row.get('priority', 'н/д')}", expanded=row["status"] in ["Критическое отклонение", "Предупреждение"]):
            st.write(row["recommendation"])
            st.caption(row.get("optimization_note", ""))


TEST_DEFINITIONS = {
    "Рост спроса": {
        "changes": {"D_avg": 1.30, "sigma_D": 1.30},
        "metrics": ["Bopt", "sigma_LT", "Pshort_current", "Ibuf"],
        "main": "Bopt",
        "text": "Тест увеличивает средний спрос и вариативность спроса. Ожидается рост sigma_LT, Bstat/Btar/Bopt и ухудшение обеспеченности.",
    },
    "Рост срока поставки": {
        "changes": {"L_avg": 1.30, "sigma_L": 1.30},
        "metrics": ["Bopt", "sigma_LT", "Pshort_current"],
        "main": "Bopt",
        "text": "Тест увеличивает средний срок и вариативность поставки. Это должно повысить неопределённость за период пополнения.",
    },
    "Ухудшение оборудования": {
        "changes": {"p_diag_add": 0.20, "p_rep_add": 0.15},
        "metrics": ["z", "Bstat", "Bopt"],
        "main": "z",
        "text": "Тест увеличивает вероятности диагностики и аварийного ремонта. Ожидается рост адаптивного z и буферов.",
    },
    "Рост загрузки ROP": {
        "changes": {"rop_load_add": 0.20},
        "metrics": ["Kload", "Btar", "Bopt"],
        "main": "Kload",
        "text": "Тест повышает загрузку ограничивающего ресурса. Ожидается рост Kload, Btar и при необходимости Bopt.",
    },
    "Снижение остатков": {
        "changes": {"O": 0.50},
        "metrics": ["A", "Ibuf", "Pshort_current"],
        "main": "Ibuf",
        "text": "Тест снижает фактический остаток. Он влияет на A, Ibuf и Pshort_current, но не обязан менять Bopt.",
    },
    "Рост стоимости простоя": {
        "changes": {"Cstop": 2.00},
        "metrics": ["Bopt", "expected_stop_loss"],
        "main": "Bopt",
        "text": "Тест повышает цену простоя ROP. При высокой цене дефицита экономически оправдан больший буфер.",
    },
    "Рост стоимости хранения": {
        "changes": {"h": 2.00},
        "metrics": ["Bopt", "holding_cost"],
        "main": "Bopt",
        "text": "Тест повышает стоимость хранения. Оптимизация должна стать менее агрессивной к увеличению буфера.",
    },
}


def testing_tab() -> None:
    """Built-in tests for logical reaction of the algorithm."""
    st.subheader("Тестирование модели")
    st.caption("Быстрые тесты проверяют направленность реакции алгоритма.")

    selected_test = st.selectbox("Выберите тест", list(TEST_DEFINITIONS.keys()))
    definition = TEST_DEFINITIONS[selected_test]
    st.info(definition["text"])
    metric = st.selectbox(
        "Показатель на графике",
        definition["metrics"],
        index=definition["metrics"].index(definition["main"]),
        format_func=lambda value: DISPLAY_NAMES.get(value, value),
    )

    base = st.session_state.input_df.copy()
    before = calculate_current(base, silent=True)
    test_df = base.copy()
    for col, factor in definition["changes"].items():
        if col.endswith("_add"):
            real_col = col.replace("_add", "")
            test_df[real_col] = (test_df[real_col] + factor).clip(0, 1.5 if real_col == "rop_load" else 1)
        else:
            test_df[col] = test_df[col] * factor
    after = calculate_current(test_df, silent=True)
    if before.empty or after.empty:
        st.error("Тест не выполнен из-за ошибок в исходных данных.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Средний оптимальный буфер до", f"{before['Bopt'].mean():.2f}")
    c2.metric("Средний оптимальный буфер после", f"{after['Bopt'].mean():.2f}", delta=f"{after['Bopt'].mean()-before['Bopt'].mean():.2f}")
    c3.metric("Средний индекс обеспеченности до", f"{before['Ibuf'].mean():.2f}")
    c4.metric("Средний индекс обеспеченности после", f"{after['Ibuf'].mean():.2f}", delta=f"{after['Ibuf'].mean()-before['Ibuf'].mean():.2f}")
    left_chart, right_chart = st.columns(2)
    with left_chart:
        st.plotly_chart(
            metric_bar(before, metric=metric, title=f"{DISPLAY_NAMES.get(metric, metric)} до теста"),
            use_container_width=True,
            key=f"testing_before_chart_{selected_test}_{metric}",
        )
    with right_chart:
        st.plotly_chart(
            metric_bar(after, metric=metric, title=f"{DISPLAY_NAMES.get(metric, metric)} после теста"),
            use_container_width=True,
            key=f"testing_after_chart_{selected_test}_{metric}",
        )
    st.plotly_chart(
        scenario_delta_chart(before, after, metric=metric, title=f"Изменение показателя: {DISPLAY_NAMES.get(metric, metric)} — {selected_test}"),
        use_container_width=True,
        key=f"testing_delta_chart_{selected_test}_{metric}",
    )
    st.plotly_chart(status_change_bar(before, after), use_container_width=True, key=f"testing_status_{selected_test}")
    display_cols = ["item_id", "A", "Bopt", "Ibuf", "Pshort_current", "status"]
    st.dataframe(
        before[display_cols].merge(after[display_cols], on="item_id", suffixes=("_до", "_после")).round(3),
        use_container_width=True,
        hide_index=True,
    )


def documentation_tab() -> None:
    """Built-in documentation for variables, formulas and usage."""
    st.subheader("Документация модели")
    st.markdown(
        """
### Назначение модуля
Модуль предназначен для оценки и непрерывного контроля буферных запасов для ресурса, ограничивающего производство (ROP). Он рассчитывает оптимальный буфер, точку заказа, вероятность дефицита и статус позиции, а также формирует управленческие рекомендации.

### Структура проекта и назначение файлов
| Элемент | Назначение |
|---|---|
| `app.py` | Главный файл приложения. Формирует страницы интерфейса, боковую панель, вкладки, кнопки, фильтры и вызывает расчётные функции. |
| `src/schema.py` | Описывает обязательные входные и выходные поля, текстовые и числовые переменные, допустимые классы критичности и статусы. |
| `src/validation.py` | Нормализует таблицу и проверяет корректность данных: наличие обязательных столбцов, числовой формат и допустимые диапазоны. |
| `src/data_loader.py` | Загружает данные из Excel/CSV. Поддерживает плоскую таблицу `input_data` и имитацию нескольких источников ERP/WMS/MES/ТОиР. |
| `src/demo_data.py` | Содержит встроенные неизменяемые демонстрационные сценарии: стабильный, средний и кризисный режим. |
| `src/coefficients.py` | Рассчитывает коэффициенты `Kcrit`, `Kload`, `Kdev` в автоматическом режиме или принимает ручные значения. |
| `src/buffer_model.py` | Основное расчётное ядро: доступная позиция, неопределённость спроса за lead time, буферы, вероятность дефицита, оптимизация, точка заказа и статус. |
| `src/status_rules.py` | Задаёт пороги и правила отнесения позиции к статусам. |
| `src/recommendations.py` | Формирует текстовые управленческие рекомендации, причины риска и приоритет действий. |
| `src/charts.py` | Создаёт графики для панели мониторинга, сравнения буферов, вероятности дефицита и сценарных изменений. |
| `src/diagrams.py` | Строит схемы архитектуры и процесса контроля буфера. |
| `src/export.py` | Формирует Excel-выгрузку с исходными данными, расчётами, сводкой и рекомендациями. |
| `tests/` | Набор автотестов, проверяющих расчёты, коэффициенты, валидацию, рекомендации, демонстрационные данные и экспорт. |

### Входные данные и экономический смысл
| Поле | Смысл | Пояснение |
|---|---|---|
| `item_id` | Код позиции | Идентификатор материала или комплектующего. |
| `item_name` | Наименование позиции | Понятное название позиции для отображения в таблицах и рекомендациях. |
| `unit` | Единица измерения | Штуки, комплекты, литры, метры и т.п. |
| `period` | Период | Месяц или другой период расчёта. |
| `rop_name` | Ограничивающий ресурс | Линия, станок или участок, для которого контролируется буфер. |
| `criticality_class` | Класс критичности | Показывает, насколько позиция важна для ROP: обычная, важная, критичная, блокирующая. |
| `O` | Фактический остаток | Количество позиции, доступное на складе. |
| `P` | Ожидаемые поступления | Количество по уже размещённым заказам или ожидаемым поставкам. |
| `R` | Подтверждённая потребность | Потребность производства, которую необходимо закрыть. |
| `D_avg` | Средний спрос | Средняя интенсивность расхода позиции. |
| `sigma_D` | Вариативность спроса | Стандартное отклонение спроса. |
| `L_avg` | Средний срок пополнения | Средний lead time поставки или пополнения. |
| `sigma_L` | Вариативность срока поставки | Стандартное отклонение lead time. |
| `rop_load` | Загрузка ROP | Доля загрузки ограничивающего ресурса. |
| `planned_flow` | Плановый поток | Плановая интенсивность прохождения позиции к ROP. |
| `actual_flow` | Фактический поток | Реальная интенсивность, используемая для оценки отклонения от плана. |
| `p_diag` | Вероятность диагностики | Вероятность состояния оборудования, связанного с диагностикой. |
| `p_rep` | Вероятность аварийного ремонта | Вероятность ремонтного состояния, повышающего риск нарушения процесса. |
| `h` | Стоимость хранения | Удельные издержки хранения единицы запаса. |
| `Cstop` | Стоимость простоя | Оценка потерь от простоя ROP при дефиците позиции. |
| `z0` | Базовый сервисный коэффициент | Исходный коэффициент надёжности. |
| `alpha`, `beta` | Вес технических факторов | Параметры влияния диагностики и ремонта на адаптивный `z`. |
| `coeff_mode` | Режим коэффициентов | `auto` — расчёт автоматически; `manual` — используются ручные значения. |

### Последовательность расчётной модели
| Шаг | Показатель | Формула | Смысл |
|---:|---|---|---|
| 1 | Доступная позиция | `A = O + P - R` | Показывает, сколько позиции реально доступно с учётом остатка, ожидаемых поступлений и подтверждённой потребности. |
| 2 | Неопределённость спроса за срок пополнения | `sigma_LT = sqrt(L_avg * sigma_D² + D_avg² * sigma_L²)` | Объединяет неопределённость спроса и неопределённость срока поставки. |
| 3 | Адаптивный коэффициент надёжности | `z = z0 * (1 + alpha * p_diag + beta * p_rep)` | Повышает требуемую надёжность при ухудшении технического состояния оборудования. |
| 4 | Статистический буфер | `Bstat = z * sigma_LT` | Минимальный статистически обоснованный буфер на основе неопределённости. |
| 5 | Целевой буфер | `Btar = Bstat * Kcrit * Kload * Kdev` | Усиливает буфер с учётом критичности позиции, загрузки ROP и отклонения потока. |
| 6 | Вероятность дефицита | `Pshort(B,t) = 1 - Phi(B / sigma_LT)` | Оценивает риск нехватки позиции при заданном уровне буфера. |
| 7 | Оптимальный буфер | `Bopt = argmin{h*B + Cstop*Pshort(B,t)}, B >= Btar` | Ищет экономически целесообразный буфер при условии, что он не ниже технологически необходимого `Btar`. |
| 8 | Точка заказа | `s = D_avg * L_avg + Bopt` | Определяет уровень, при котором нужно инициировать пополнение. |
| 9 | Индекс обеспеченности буфера | `Ibuf = A / Bopt` | Сравнивает фактическую доступную позицию с оптимальным буфером. |
| 10 | Текущая вероятность дефицита | `Pshort_current = 1, если A <= 0; иначе 1 - Phi(A / sigma_LT)` | Показывает текущий риск дефицита по фактической доступной позиции, а не по рекомендуемому буферу. |

### Производственные коэффициенты
`Kcrit` определяется по классу критичности позиции: обычная — 1,00; важная — 1,15; критичная — 1,30; блокирующая — 1,50.

**Коэффициент загрузки ROP `Kload`**
| Условие | `Kload` |
|---|---:|
| `rop_load <= 0.70` | 1.00 |
| `0.70 < rop_load <= 0.85` | 1.05 |
| `0.85 < rop_load <= 1.00` | 1.15 |
| `1.00 < rop_load <= 1.15` | 1.25 |
| `rop_load > 1.15` | 1.35 |

**Коэффициент отклонения потока `Kdev`**
| Условие | `Kdev` |
|---|---:|
| Отклонение <= 5% | 1.00 |
| 5% < отклонение <= 10% | 1.05 |
| 10% < отклонение <= 20% | 1.10 |
| 20% < отклонение <= 30% | 1.20 |
| Отклонение > 30% | 1.30 |
| Плановый поток <= 0 | 1.30 |

### Разница между Pshort и Pshort_current
- `Pshort` — вероятность дефицита при рекомендуемом оптимальном буфере `Bopt`; используется в оптимизации.
- `Pshort_current` — текущая вероятность дефицита при фактической доступной позиции `A`; используется для мониторинга фактического риска.

### Статусы и пороги
- `Ibuf <= критический порог` — критическое отклонение.
- `критический порог < Ibuf <= порог нормы` — предупреждение.
- `порог нормы < Ibuf <= порог избыточности` — норма.
- `Ibuf > порог избыточности` — избыточный буфер.

Пороги не должны пересекаться. В боковой панели используется проверка условия: `критический порог < порог нормы < порог избыточности`. При нарушении этого условия система выводит предупреждение и не применяет некорректные настройки.

### Ограничения модели
В версии 1.0 используется нормальная аппроксимация вероятности дефицита. Для внедрения на предприятии параметры `h`, `Cstop`, `z0`, `alpha`, `beta` и шкалы коэффициентов должны быть откалиброваны на фактических данных. Сценарные данные являются демонстрационными и не заменяют фактическую статистику предприятия.

### Запуск
Windows: `run_app.bat` или `python -m streamlit run app.py`.
macOS: `./run_app.command` после подготовки виртуального окружения.
"""
    )

def export_tab(df: pd.DataFrame) -> None:
    """Export calculated results and recommendations."""
    st.subheader("Экспорт")
    if df.empty:
        st.warning("Нет рассчитанных данных для экспорта.")
        return
    excel_bytes = multi_sheet_export_bytes(st.session_state.input_df, df)
    st.download_button(
        "Скачать результаты расчёта в Excel",
        data=excel_bytes,
        file_name="buffer_calculation_result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="download_calculation_result_excel",
    )
    rec_cols = ["item_id", "item_name", "rop_name", "status", "priority", "recommendation"]
    rec_csv = df[rec_cols].to_csv(index=False, encoding="utf-8-sig")
    st.download_button("Скачать рекомендации CSV", data=rec_csv, file_name="buffer_recommendations.csv", mime="text/csv", use_container_width=True, key="download_export_recommendations_csv")
    st.info("Excel-файл содержит исходные данные, результаты расчёта, сводку и рекомендации.")


def main() -> None:
    """Application entry point."""
    init_state()
    sidebar_controls()
    st.title(APP_TITLE)
    st.caption("Локальный демонстрационный модуль для научной работы. Встроенные демо-сценарии являются неизменяемыми; редактируется только рабочая копия данных.")

    calculated_df = st.session_state.calculated_df

    tabs = st.tabs([
        "Главная панель",
        "Данные",
        "Расчёт буфера",
        "Мониторинг ROP",
        "Сценарный анализ",
        "Схемы",
        "Управленческое заключение",
        "Тестирование модели",
        "Документация",
        "Экспорт",
    ])

    with tabs[0]:
        dashboard_tab(calculated_df)
    with tabs[1]:
        data_tab()
    with tabs[2]:
        calculation_tab(calculated_df)
    with tabs[3]:
        monitoring_tab(calculated_df)
    with tabs[4]:
        scenario_tab()
    with tabs[5]:
        diagrams_tab(calculated_df)
    with tabs[6]:
        recommendations_tab(calculated_df)
    with tabs[7]:
        testing_tab()
    with tabs[8]:
        documentation_tab()
    with tabs[9]:
        export_tab(calculated_df)


if __name__ == "__main__":
    main()
