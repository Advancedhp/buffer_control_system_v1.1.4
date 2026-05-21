"""Excel loading utilities."""
from __future__ import annotations

from io import BytesIO

import pandas as pd

from .schema import REQUIRED_COLUMNS
from .validation import normalize_dataframe


def load_excel_workbook(file) -> pd.DataFrame:
    """Load an Excel file.

    Version 1.0 supports:
    - single sheet `input_data` with all required columns;
    - multi-sheet imitation of ERP/WMS/MES/EAM sources.
    """
    workbook = pd.read_excel(file, sheet_name=None)
    sheet_names = {name.lower(): name for name in workbook.keys()}

    if "input_data" in sheet_names:
        df = workbook[sheet_names["input_data"]]
        return normalize_dataframe(df)

    required_source_sheets = {"items", "stock", "orders", "demand", "leadtime", "production", "equipment", "costs"}
    if required_source_sheets.issubset(set(sheet_names.keys())):
        return _load_multisheet(workbook, sheet_names)

    # Fallback: first sheet as a flat table.
    first_sheet = next(iter(workbook.values()))
    return normalize_dataframe(first_sheet)


def _load_multisheet(workbook: dict[str, pd.DataFrame], sheet_names: dict[str, str]) -> pd.DataFrame:
    def sheet(name: str) -> pd.DataFrame:
        return workbook[sheet_names[name]].copy()

    items = sheet("items")
    stock = sheet("stock")
    orders = sheet("orders")
    demand = sheet("demand")
    leadtime = sheet("leadtime")
    production = sheet("production")
    equipment = sheet("equipment")
    costs = sheet("costs")

    keys = ["item_id", "period"]
    df = stock.merge(orders, on=keys, how="outer")
    for part in [demand, leadtime, production, equipment, costs]:
        df = df.merge(part, on=keys, how="outer")
    df = df.merge(items, on="item_id", how="left")

    # Optional settings sheet. First row values apply to all rows if columns are missing.
    if "settings" in sheet_names:
        settings = sheet("settings")
        if not settings.empty:
            if {"parameter", "value"}.issubset(settings.columns):
                settings_map = dict(zip(settings["parameter"], settings["value"]))
            else:
                settings_map = settings.iloc[0].to_dict()
            for col, default in [("z0", 1.65), ("alpha", 0.40), ("beta", 0.80)]:
                df[col] = settings_map.get(col, default)
    else:
        df["z0"] = 1.65
        df["alpha"] = 0.40
        df["beta"] = 0.80

    for col in ["Kcrit_manual", "Kload_manual", "Kdev_manual"]:
        if col not in df.columns:
            df[col] = 0.0
    if "coeff_mode" not in df.columns:
        df["coeff_mode"] = "auto"
    if "unit" not in df.columns:
        df["unit"] = "ед."
    if "rop_name" not in df.columns:
        df["rop_name"] = "ROP-1"

    return normalize_dataframe(df)


def load_uploaded_data(file, filename: str | None = None) -> pd.DataFrame:
    """Load Excel or CSV input file and normalize it to the flat model schema."""
    name = (filename or getattr(file, "name", "")).lower()
    if name.endswith(".csv"):
        # UTF-8 with BOM is common for Excel exports; fallback to cp1251 for Russian Windows files.
        try:
            return normalize_dataframe(pd.read_csv(file, encoding="utf-8-sig"))
        except UnicodeDecodeError:
            file.seek(0)
            return normalize_dataframe(pd.read_csv(file, encoding="cp1251", sep=None, engine="python"))
    return load_excel_workbook(file)


def create_flat_template_bytes(rows: int = 3) -> bytes:
    """Create a simple Excel template with a single input_data sheet."""
    rows = max(1, int(rows))
    data = []
    for i in range(rows):
        data.append({
            "item_id": f"MAT-{i+1:03d}",
            "item_name": "Пример позиции",
            "unit": "ед.",
            "period": "2026-01",
            "rop_name": "ROP-1",
            "criticality_class": "важная",
            "O": 50,
            "P": 80,
            "R": 70,
            "D_avg": 30,
            "sigma_D": 4,
            "L_avg": 5,
            "sigma_L": 0.5,
            "rop_load": 0.85,
            "planned_flow": 30,
            "actual_flow": 28,
            "p_diag": 0.10,
            "p_rep": 0.05,
            "h": 1.0,
            "Cstop": 5000,
            "z0": 1.65,
            "alpha": 0.40,
            "beta": 0.80,
            "Kcrit_manual": 0.0,
            "Kload_manual": 0.0,
            "Kdev_manual": 0.0,
            "coeff_mode": "auto",
        })
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(data)[REQUIRED_COLUMNS].to_excel(writer, sheet_name="input_data", index=False)
    return output.getvalue()
