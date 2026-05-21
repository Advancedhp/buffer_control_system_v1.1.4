"""Export utilities."""
from __future__ import annotations

from io import BytesIO

import pandas as pd


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "result") -> bytes:
    """Export a dataframe to Excel bytes."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()


def _summary(result_df: pd.DataFrame) -> pd.DataFrame:
    if result_df.empty:
        return pd.DataFrame()
    rows = [
        {"Показатель": "Всего позиций", "Значение": len(result_df)},
        {"Показатель": "Критическое отклонение", "Значение": int((result_df["status"] == "Критическое отклонение").sum())},
        {"Показатель": "Предупреждение", "Значение": int((result_df["status"] == "Предупреждение").sum())},
        {"Показатель": "Норма", "Значение": int((result_df["status"] == "Норма").sum())},
        {"Показатель": "Избыточный буфер", "Значение": int((result_df["status"] == "Избыточный буфер").sum())},
        {"Показатель": "Средний индекс обеспеченности буфера", "Значение": result_df["Ibuf"].replace([float("inf"), -float("inf")], pd.NA).dropna().mean()},
        {"Показатель": "Средний оптимальный буфер", "Значение": result_df["Bopt"].mean()},
    ]
    return pd.DataFrame(rows)


def multi_sheet_export_bytes(input_df: pd.DataFrame, result_df: pd.DataFrame) -> bytes:
    """Export input, results, summary and recommendations to a workbook."""
    output = BytesIO()
    rec_cols = [c for c in ["item_id", "item_name", "rop_name", "status", "priority", "A", "Bopt", "Ibuf", "Pshort_current", "risk_reasons", "recommendation"] if c in result_df.columns]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        input_df.to_excel(writer, sheet_name="input_data", index=False)
        result_df.to_excel(writer, sheet_name="calculation_result", index=False)
        _summary(result_df).to_excel(writer, sheet_name="summary", index=False)
        if rec_cols:
            result_df[rec_cols].to_excel(writer, sheet_name="recommendations", index=False)
    return output.getvalue()
