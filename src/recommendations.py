"""Automatic management recommendations for model outputs."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default


def _fmt(value: Any, digits: int = 2) -> str:
    number = _as_float(value, default=float("nan"))
    if math.isfinite(number):
        return f"{number:.{digits}f}"
    return "н/д"


def detect_reasons(row: dict[str, Any]) -> list[str]:
    """Detect the main reasons behind a risky buffer state."""
    reasons: list[str] = []
    A = _as_float(row.get("A"))
    bopt = _as_float(row.get("Bopt"), 1.0)
    sigma_lt = _as_float(row.get("sigma_LT"))
    rop_load = _as_float(row.get("rop_load"))
    p_diag = _as_float(row.get("p_diag"))
    p_rep = _as_float(row.get("p_rep"))
    kdev = _as_float(row.get("Kdev"), 1.0)
    if A <= 0:
        reasons.append("подтверждённая потребность превышает сумму остатка и ожидаемых поступлений")
    elif A < bopt:
        reasons.append("доступная позиция ниже оптимального буфера")
    if sigma_lt > max(bopt * 0.35, 1.0):
        reasons.append("существенная совокупная неопределённость спроса и срока поставки")
    if rop_load >= 0.85:
        reasons.append("высокая загрузка ресурса, ограничивающего производство")
    if p_diag >= 0.20 or p_rep >= 0.12:
        reasons.append("ухудшение технического состояния смежного оборудования")
    if kdev >= 1.10:
        reasons.append("значимое отклонение фактического потока от планового")
    return reasons or ["существенных дополнительных факторов риска не выявлено"]


def priority_by_status(status: str) -> str:
    """Return management priority by status."""
    if status == "Критическое отклонение":
        return "Высокий"
    if status == "Предупреждение":
        return "Средний"
    if status == "Избыточный буфер":
        return "Средний"
    if status == "Норма":
        return "Низкий"
    return "Требует проверки"


def build_recommendation(row: dict[str, Any]) -> str:
    """Return a readable structured recommendation based on row status and key metrics."""
    name = row.get("item_name", "позиция")
    item_id = row.get("item_id", "")
    status = row.get("status", "Не рассчитано")
    A = _fmt(row.get("A"))
    Bopt = _fmt(row.get("Bopt"))
    Ibuf = _fmt(row.get("Ibuf"))
    Pshort = _fmt(_as_float(row.get("Pshort_current", row.get("Pshort", 0.0))) * 100, 2)
    reorder_point = _fmt(row.get("reorder_point"))
    rop_name = row.get("rop_name", "ограничивающий ресурс")
    reasons = "; ".join(detect_reasons(row))
    priority = priority_by_status(status)

    base = (
        f"Позиция {item_id} «{name}».\n\n"
        f"Состояние: {status}. Приоритет: {priority}.\n"
        f"Ключевые значения: A = {A}; Bopt = {Bopt}; Ibuf = {Ibuf}; текущая вероятность дефицита = {Pshort}%; точка заказа s = {reorder_point}.\n"
        f"Причины/факторы: {reasons}.\n"
    )

    if status == "Критическое отклонение":
        action = (
            f"Рекомендация: для ресурса «{rop_name}» требуется срочное управленческое действие: проверить ближайшие поступления, "
            "инициировать пополнение, оценить возможность ускорения поставки и при необходимости скорректировать производственный план."
        )
    elif status == "Предупреждение":
        action = (
            f"Рекомендация: усилить контроль позиции для ресурса «{rop_name}», проверить сроки поставки и не допускать снижения доступной позиции "
            f"ниже точки заказа s = {reorder_point}."
        )
    elif status == "Норма":
        action = "Рекомендация: дополнительных корректирующих действий не требуется; достаточно планового мониторинга."
    elif status == "Избыточный буфер":
        action = (
            "Рекомендация: проверить целесообразность новых закупок и рассмотреть сокращение следующего пополнения, поскольку запас может "
            "избыточно замораживать оборотный капитал."
        )
    else:
        action = "Рекомендация: проверить корректность исходных данных и повторить расчёт."
    return base + action


def add_recommendations(df):
    """Add recommendation, reason and priority columns to a calculated dataframe."""
    result = df.copy()
    if result.empty:
        result["recommendation"] = []
        result["priority"] = []
        result["risk_reasons"] = []
        return result
    result["risk_reasons"] = result.apply(lambda row: "; ".join(detect_reasons(dict(row))), axis=1)
    result["priority"] = result["status"].apply(priority_by_status)
    result["recommendation"] = result.apply(lambda row: build_recommendation(dict(row)), axis=1)
    return result
