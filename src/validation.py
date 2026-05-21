"""Input validation for buffer model data."""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .schema import REQUIRED_COLUMNS, NUMERIC_COLUMNS, CRITICALITY_CLASSES, COEFF_MODES


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all required columns exist and numeric columns are numeric."""
    result = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in result.columns:
            if col in NUMERIC_COLUMNS:
                result[col] = 0.0
            elif col == "coeff_mode":
                result[col] = "auto"
            elif col == "criticality_class":
                result[col] = "обычная"
            elif col == "unit":
                result[col] = "ед."
            elif col == "period":
                result[col] = "2026-01"
            elif col == "rop_name":
                result[col] = "ROP-1"
            else:
                result[col] = ""
    for col in NUMERIC_COLUMNS:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    return result[REQUIRED_COLUMNS]


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    """Return a list of validation errors. Empty list means the data are valid."""
    errors: list[str] = []
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        errors.append("Отсутствуют обязательные поля: " + ", ".join(missing))
        return errors

    normalized = normalize_dataframe(df)

    def row_label(index: int) -> str:
        try:
            item_id = normalized.loc[index, "item_id"]
            return f"строка {index + 1} ({item_id})"
        except Exception:
            return f"строка {index + 1}"

    for idx, row in normalized.iterrows():
        for col in NUMERIC_COLUMNS:
            if pd.isna(row[col]):
                errors.append(f"{row_label(idx)}: поле {col} должно быть числом.")

        if str(row["item_id"]).strip() == "":
            errors.append(f"{row_label(idx)}: поле item_id не должно быть пустым.")
        if str(row["item_name"]).strip() == "":
            errors.append(f"{row_label(idx)}: поле item_name не должно быть пустым.")

        non_negative = ["O", "P", "R", "sigma_D", "sigma_L", "actual_flow", "h", "Cstop", "alpha", "beta"]
        for col in non_negative:
            if pd.notna(row[col]) and row[col] < 0:
                errors.append(f"{row_label(idx)}: поле {col} не может быть отрицательным.")

        positive = ["D_avg", "L_avg", "z0", "planned_flow"]
        for col in positive:
            if pd.notna(row[col]) and row[col] <= 0:
                errors.append(f"{row_label(idx)}: поле {col} должно быть больше 0.")

        for col in ["p_diag", "p_rep"]:
            if pd.notna(row[col]) and not (0 <= row[col] <= 1):
                errors.append(f"{row_label(idx)}: поле {col} должно быть в диапазоне от 0 до 1.")

        if pd.notna(row["rop_load"]) and not (0 <= row["rop_load"] <= 1.5):
            errors.append(f"{row_label(idx)}: поле rop_load должно быть в диапазоне от 0 до 1.5.")

        crit = str(row["criticality_class"]).strip().lower()
        if crit not in CRITICALITY_CLASSES:
            errors.append(
                f"{row_label(idx)}: criticality_class должно быть одним из значений: "
                + ", ".join(CRITICALITY_CLASSES)
            )

        mode = str(row["coeff_mode"]).strip().lower()
        if mode not in COEFF_MODES:
            errors.append(f"{row_label(idx)}: coeff_mode должен быть auto или manual.")
        if mode == "manual":
            for col in ["Kcrit_manual", "Kload_manual", "Kdev_manual"]:
                if pd.isna(row[col]) or row[col] <= 0:
                    errors.append(f"{row_label(idx)}: при ручном режиме поле {col} должно быть больше 0.")

    return errors


def limit_errors(errors: Iterable[str], max_count: int = 12) -> list[str]:
    """Limit long error lists for UI display."""
    errors_list = list(errors)
    if len(errors_list) <= max_count:
        return errors_list
    return errors_list[:max_count] + [f"...и ещё {len(errors_list) - max_count} ошибок."]
