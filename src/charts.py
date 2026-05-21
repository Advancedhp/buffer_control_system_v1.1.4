"""Plotly charts for the Streamlit app."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .status_rules import DEFAULT_CRITICAL_THRESHOLD, DEFAULT_NORMAL_THRESHOLD, DEFAULT_SURPLUS_THRESHOLD, STATUS_HEX, STATUS_ORDER

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


def label(metric: str) -> str:
    return DISPLAY_NAMES.get(metric, metric)


def _clean_numeric(data: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = data.copy()
    result = result.replace([float("inf"), -float("inf")], pd.NA)
    for col in cols:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result.dropna(subset=[c for c in cols if c in result.columns])


def status_pie(df: pd.DataFrame):
    counts = df["status"].value_counts().reset_index()
    counts.columns = ["status", "count"]
    counts["color"] = counts["status"].map(STATUS_HEX)
    fig = px.pie(
        counts,
        values="count",
        names="status",
        title="Структура статусов позиций",
        color="status",
        color_discrete_map=STATUS_HEX,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def ibuf_bar(
    df: pd.DataFrame,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    normal_threshold: float = DEFAULT_NORMAL_THRESHOLD,
    surplus_threshold: float = DEFAULT_SURPLUS_THRESHOLD,
):
    data = _clean_numeric(df, ["Ibuf"])
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="Индекс обеспеченности буфера по позициям", height=460)
        return fig
    status_rank = {status: idx for idx, status in enumerate(STATUS_ORDER)}
    data["status_rank"] = data["status"].map(status_rank).fillna(99)
    data = data.sort_values(["status_rank", "Ibuf"], ascending=[True, True])

    fig = go.Figure()
    for status in STATUS_ORDER:
        part = data[data["status"] == status]
        if part.empty:
            continue
        fig.add_trace(go.Bar(
            name=status,
            x=part["item_id"],
            y=part["Ibuf"],
            marker_color=STATUS_HEX.get(status, "#94a3b8"),
            text=[f"{v:.2f}" for v in part["Ibuf"]],
            textposition="outside",
            customdata=part[["item_name", "status", "A", "Bopt", "Pshort_current"]] if {"item_name", "status", "A", "Bopt", "Pshort_current"}.issubset(part.columns) else None,
            hovertemplate=(
                "Позиция: %{x}<br>"
                "Наименование: %{customdata[0]}<br>"
                "Статус: %{customdata[1]}<br>"
                "Ibuf: %{y:.3f}<br>"
                "A: %{customdata[2]:.2f}<br>"
                "Bopt: %{customdata[3]:.2f}<br>"
                "Текущая вероятность дефицита: %{customdata[4]:.2%}<extra></extra>"
            ) if {"item_name", "status", "A", "Bopt", "Pshort_current"}.issubset(part.columns) else None,
        ))
    fig.add_hline(y=critical_threshold, line_dash="dash", line_color="rgba(248,113,113,0.8)")
    fig.add_hline(y=normal_threshold, line_dash="dash", line_color="rgba(251,191,36,0.8)")
    fig.add_hline(y=surplus_threshold, line_dash="dash", line_color="rgba(96,165,250,0.8)")
    max_y = max(float(data["Ibuf"].max()) * 1.15, surplus_threshold * 1.25, 1.0)
    fig.update_layout(
        title="Индекс обеспеченности буфера по позициям",
        xaxis_title="Позиция",
        yaxis_title="Индекс обеспеченности буфера",
        barmode="group",
        showlegend=True,
        height=520,
        yaxis=dict(range=[min(0, float(data["Ibuf"].min()) * 1.15), max_y]),
        legend_title="Статус",
    )
    return fig


def buffer_comparison(df: pd.DataFrame):
    """Grouped horizontal chart with all positions for A, Btar and Bopt."""
    data = _clean_numeric(df, ["Bopt", "A", "Btar"]).copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title="Сравнение доступной позиции, целевого и оптимального буфера", height=460)
        return fig
    data = data.sort_values("Bopt", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Доступная позиция", y=data["item_id"], x=data["A"], orientation="h"))
    fig.add_trace(go.Bar(name="Целевой буфер", y=data["item_id"], x=data["Btar"], orientation="h"))
    fig.add_trace(go.Bar(name="Оптимальный буфер", y=data["item_id"], x=data["Bopt"], orientation="h"))
    height = max(640, min(1300, 340 + int(len(data)) * 24))
    fig.update_layout(
        barmode="group",
        title="Сравнение доступной позиции, целевого и оптимального буфера по всем позициям",
        xaxis_title="Единицы запаса",
        yaxis_title="Позиция",
        height=height,
        legend_title="Показатель",
        margin=dict(l=90, r=30, t=70, b=70),
        yaxis=dict(automargin=True),
    )
    return fig

def pshort_bar(df: pd.DataFrame):
    """Current shortage probability chart for all positions."""
    risk_col = "Pshort_current" if "Pshort_current" in df.columns else "Pshort"
    data = _clean_numeric(df, [risk_col]).sort_values(risk_col, ascending=False).copy()
    colors = [STATUS_HEX.get(status, "#94a3b8") for status in data.get("status", [])]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=data["item_id"],
        y=data[risk_col] * 100,
        marker_color=colors if colors else None,
        customdata=data[["item_name", "status"]] if {"item_name", "status"}.issubset(data.columns) else None,
        hovertemplate="Позиция: %{x}<br>Наименование: %{customdata[0]}<br>Статус: %{customdata[1]}<br>Риск: %{y:.2f}%<extra></extra>" if {"item_name", "status"}.issubset(data.columns) else None,
    ))
    height = max(470, min(950, 360 + int(len(data)) * 8))
    fig.update_layout(
        title="Текущая вероятность дефицита по всем позициям",
        xaxis_title="Позиция",
        yaxis_title="Вероятность дефицита, %",
        height=height,
        xaxis=dict(tickangle=-45, automargin=True),
        margin=dict(b=120),
    )
    return fig


def metric_bar(df: pd.DataFrame, metric: str = "Bopt", title: str | None = None, top_n: int | None = None):
    """Bar chart for a single metric. By default it shows all positions."""
    if metric not in df.columns:
        metric = "Bopt"
    data = _clean_numeric(df, [metric]).copy()
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=title or f"{label(metric)} по позициям", height=420)
        return fig
    data["abs_metric"] = data[metric].abs()
    data = data.sort_values("abs_metric", ascending=False)
    if top_n is not None:
        data = data.head(top_n)
    colors = [STATUS_HEX.get(status, "#94a3b8") for status in data.get("status", [])]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=data["item_id"],
        y=data[metric],
        marker_color=colors if colors else "#60a5fa",
        customdata=data[["item_name", "status"]] if {"item_name", "status"}.issubset(data.columns) else None,
        hovertemplate=(
            "Позиция: %{x}<br>"
            "Наименование: %{customdata[0]}<br>"
            "Статус: %{customdata[1]}<br>"
            f"{label(metric)}: " + "%{y:.3f}<extra></extra>"
        ) if {"item_name", "status"}.issubset(data.columns) else None,
    ))
    height = max(470, min(950, 360 + int(len(data)) * 8))
    fig.update_layout(
        title=title or f"{label(metric)} по всем позициям",
        xaxis_title="Позиция",
        yaxis_title=label(metric),
        height=height,
        showlegend=False,
        xaxis=dict(tickangle=-45, automargin=True),
        margin=dict(b=120),
    )
    return fig

def scenario_delta_chart(before: pd.DataFrame, after: pd.DataFrame, metric: str = "Bopt", title: str | None = None):
    if metric not in before.columns or metric not in after.columns:
        metric = "Bopt"
    before_clean = before[["item_id", metric]].replace([float("inf"), -float("inf")], pd.NA).dropna()
    after_clean = after[["item_id", metric]].replace([float("inf"), -float("inf")], pd.NA).dropna()
    merged = before_clean.merge(after_clean, on="item_id", suffixes=("_before", "_after"))
    merged[f"delta_{metric}"] = pd.to_numeric(merged[f"{metric}_after"], errors="coerce") - pd.to_numeric(merged[f"{metric}_before"], errors="coerce")
    data = merged.dropna(subset=[f"delta_{metric}"]).copy()
    data["abs_delta"] = data[f"delta_{metric}"].abs()
    data = data.sort_values("abs_delta", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=data["item_id"], y=data[f"delta_{metric}"], marker_color="#60a5fa"))
    height = max(500, min(950, 380 + int(len(data)) * 8))
    fig.update_layout(
        title=title or f"Изменение показателя: {label(metric)}",
        xaxis_title="Позиция",
        yaxis_title=f"Изменение: {label(metric)}",
        height=height,
        xaxis=dict(tickangle=-45, automargin=True),
        margin=dict(b=120),
    )
    return fig


def status_change_bar(before: pd.DataFrame, after: pd.DataFrame):
    merged = before[["item_id", "status"]].merge(after[["item_id", "status"]], on="item_id", suffixes=("_до", "_после"))
    counts = merged.groupby(["status_до", "status_после"]).size().reset_index(name="count")
    counts["transition"] = counts["status_до"] + " → " + counts["status_после"]
    fig = px.bar(counts, x="transition", y="count", title="Изменение статусов после воздействия")
    fig.update_layout(xaxis_title="Переход статуса", yaxis_title="Количество позиций", height=430)
    return fig
