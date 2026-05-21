"""Coefficient calculation rules for the ROP buffer model."""
from __future__ import annotations

from typing import Any

import pandas as pd

CRITICALITY_TO_KCRIT = {
    "обычная": 1.00,
    "важная": 1.15,
    "критичная": 1.30,
    "блокирующая": 1.50,
}


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float without raising exceptions and replace NaN/None with default."""
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_kcrit(criticality_class: str) -> float:
    """Return Kcrit from a human-readable criticality class."""
    return CRITICALITY_TO_KCRIT.get(str(criticality_class).strip().lower(), 1.0)


def calculate_kload(rop_load: float) -> float:
    """Return Kload by ROP load.

    rop_load is interpreted as a fraction: 0.85 means 85% load, 1.10 means 110% load.
    Kload is a strengthening coefficient, therefore values below 70% do not reduce the
    statistically justified buffer and are treated as neutral.
    """
    load = safe_float(rop_load, 0.0)
    if load <= 0.70:
        return 1.00
    if load <= 0.85:
        return 1.05
    if load <= 1.00:
        return 1.15
    if load <= 1.15:
        return 1.25
    return 1.35


def calculate_kdev(planned_flow: float, actual_flow: float) -> float:
    """Return Kdev by relative deviation of actual flow from planned flow."""
    planned = safe_float(planned_flow, 0.0)
    actual = safe_float(actual_flow, 0.0)
    if planned <= 0:
        return 1.30
    deviation = abs(actual - planned) / planned
    if deviation <= 0.05:
        return 1.00
    if deviation <= 0.10:
        return 1.05
    if deviation <= 0.20:
        return 1.10
    if deviation <= 0.30:
        return 1.20
    return 1.30


def resolve_coefficients(row: dict[str, Any]) -> tuple[float, float, float]:
    """Resolve Kcrit, Kload and Kdev in automatic or manual mode."""
    coeff_mode = str(row.get("coeff_mode", "auto")).strip().lower()
    if coeff_mode in {"manual", "ручной"}:
        return (
            safe_float(row.get("Kcrit_manual"), 1.0),
            safe_float(row.get("Kload_manual"), 1.0),
            safe_float(row.get("Kdev_manual"), 1.0),
        )
    return (
        calculate_kcrit(row.get("criticality_class", "обычная")),
        calculate_kload(row.get("rop_load", 0.0)),
        calculate_kdev(row.get("planned_flow", 0.0), row.get("actual_flow", 0.0)),
    )


def coefficient_preview(df: pd.DataFrame) -> pd.DataFrame:
    """Return a compact dataframe with actual coefficients used by the model."""
    if df.empty:
        return pd.DataFrame()
    rows = []
    for _, row in df.iterrows():
        row_dict = dict(row)
        kcrit, kload, kdev = resolve_coefficients(row_dict)
        planned = safe_float(row_dict.get("planned_flow"), 0.0)
        actual = safe_float(row_dict.get("actual_flow"), 0.0)
        flow_dev = abs(actual - planned) / planned if planned > 0 else 1.0
        rows.append({
            "item_id": row_dict.get("item_id"),
            "item_name": row_dict.get("item_name"),
            "rop_name": row_dict.get("rop_name"),
            "Режим": "Ручной" if str(row_dict.get("coeff_mode", "auto")).lower() in {"manual", "ручной"} else "Автоматический",
            "Класс критичности": row_dict.get("criticality_class"),
            "rop_load": safe_float(row_dict.get("rop_load"), 0.0),
            "Отклонение потока": flow_dev,
            "Kcrit": kcrit,
            "Kload": kload,
            "Kdev": kdev,
        })
    return pd.DataFrame(rows)
