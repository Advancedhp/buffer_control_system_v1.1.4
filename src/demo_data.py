"""Immutable built-in demonstration scenarios.

The scenarios are stored in the program code and do not depend on external files.
The UI works with a copy of a selected scenario, so the original data cannot be damaged.
"""
from __future__ import annotations

from copy import deepcopy

import pandas as pd

from .buffer_model import calculate_adaptive_z, calculate_bstat, calculate_btar, calculate_sigma_lt, optimize_buffer
from .coefficients import resolve_coefficients
from .schema import REQUIRED_COLUMNS

ITEM_NAMES = [
    "Подшипник опорный", "Ремень приводной", "Комплект крепежа", "Смазочный материал",
    "Датчик температуры", "Фильтр воздушный", "Электродвигатель малый", "Пружина возвратная",
    "Плата управления", "Уплотнитель", "Вал промежуточный", "Редукторный узел",
    "Трубка подачи", "Клапан регулировочный", "Ролик направляющий", "Переходник",
    "Муфта соединительная", "Кабель силовой", "Корпус защитный", "Насос дозирующий",
    "Шестерня", "Сопло технологическое", "Прокладка", "Контроллер линии",
]

UNITS = ["шт.", "шт.", "компл.", "л", "шт.", "шт.", "шт.", "шт.", "шт.", "шт.", "шт.", "шт.", "м", "шт.", "шт.", "шт.", "шт.", "м", "шт.", "шт.", "шт.", "шт.", "шт.", "шт."]
CRITICALITY = [
    "критичная", "важная", "обычная", "важная", "критичная", "важная", "блокирующая", "обычная",
    "блокирующая", "важная", "критичная", "блокирующая", "обычная", "критичная", "важная", "обычная",
    "критичная", "важная", "обычная", "блокирующая", "критичная", "важная", "обычная", "блокирующая",
]
ROP_NAMES = ["Линия фасовки №1", "Станок ЧПУ-3", "Термопресс", "Сборочный пост"]

BASE_ROWS: list[dict[str, object]] = []
for i, name in enumerate(ITEM_NAMES, start=1):
    base_demand = 22 + (i % 6) * 5 + (i // 7) * 3
    base_sigma = 2.0 + (i % 5) * 0.8
    base_l = 4.0 + (i % 4) * 0.6
    base_sigma_l = 0.35 + (i % 3) * 0.12
    BASE_ROWS.append({
        "item_id": f"MAT-{i:03d}",
        "item_name": name,
        "unit": UNITS[i-1],
        "period": "2026-01",
        "rop_name": ROP_NAMES[i % len(ROP_NAMES)],
        "criticality_class": CRITICALITY[i-1],
        "D_avg": round(base_demand, 2),
        "sigma_D": round(base_sigma, 2),
        "L_avg": round(base_l, 2),
        "sigma_L": round(base_sigma_l, 2),
        "planned_flow": round(base_demand * 1.05, 2),
        "actual_flow": round(base_demand * (1.02 if i % 2 == 0 else 0.98), 2),
        "h": round(0.7 + (i % 4) * 0.25, 2),
        "Cstop": round(4500 + (i % 6) * 900, 2),
        "z0": 1.65,
        "alpha": 0.40,
        "beta": 0.80,
        "Kcrit_manual": 0.0,
        "Kload_manual": 0.0,
        "Kdev_manual": 0.0,
        "coeff_mode": "auto",
    })


def _estimate_bopt(row: dict[str, object]) -> float:
    """Estimate Bopt during demo generation to tune visible status distribution."""
    sigma_lt = calculate_sigma_lt(row["D_avg"], row["sigma_D"], row["L_avg"], row["sigma_L"])
    z = calculate_adaptive_z(row["z0"], row["alpha"], row["beta"], row["p_diag"], row["p_rep"])
    kcrit, kload, kdev = resolve_coefficients(row)
    bstat = calculate_bstat(z, sigma_lt)
    btar = calculate_btar(bstat, kcrit, kload, kdev)
    return float(optimize_buffer(btar, sigma_lt, row["h"], row["Cstop"])["Bopt"])


def _tune_availability(row: dict[str, object], target_ibuf: float) -> None:
    """Set O so that A/Bopt is close to a desired demo ratio."""
    bopt = _estimate_bopt(row)
    target_A = target_ibuf * bopt
    P = float(row["P"])
    R = float(row["R"])
    row["O"] = round(max(0.0, target_A - P + R), 2)


def _scenario_rows(kind: str) -> list[dict[str, object]]:
    rows = deepcopy(BASE_ROWS)
    for idx, row in enumerate(rows, start=1):
        d = float(row["D_avg"])
        if kind == "stable":
            row["O"] = round(d * (2.4 + (idx % 4) * 0.15), 2)
            row["P"] = round(d * (2.2 + (idx % 3) * 0.1), 2)
            row["R"] = round(d * (1.6 + (idx % 2) * 0.1), 2)
            row["sigma_D"] = round(float(row["sigma_D"]) * 0.8, 2)
            row["sigma_L"] = round(float(row["sigma_L"]) * 0.8, 2)
            row["rop_load"] = round(0.62 + (idx % 4) * 0.04, 2)
            row["p_diag"] = round(0.05 + (idx % 3) * 0.02, 2)
            row["p_rep"] = round(0.02 + (idx % 2) * 0.01, 2)
            row["actual_flow"] = round(float(row["planned_flow"]) * (1.00 + ((idx % 3) - 1) * 0.02), 2)
        elif kind == "medium":
            row["O"] = round(d * (1.4 + (idx % 5) * 0.08), 2)
            row["P"] = round(d * (1.45 + (idx % 4) * 0.12), 2)
            row["R"] = round(d * (1.9 + (idx % 4) * 0.1), 2)
            row["sigma_D"] = round(float(row["sigma_D"]) * 1.35, 2)
            row["sigma_L"] = round(float(row["sigma_L"]) * 1.35, 2)
            row["L_avg"] = round(float(row["L_avg"]) * 1.12, 2)
            row["rop_load"] = round(0.78 + (idx % 5) * 0.06, 2)
            row["p_diag"] = round(0.10 + (idx % 4) * 0.03, 2)
            row["p_rep"] = round(0.05 + (idx % 3) * 0.02, 2)
            row["actual_flow"] = round(float(row["planned_flow"]) * (0.92 + (idx % 4) * 0.04), 2)
        elif kind == "crisis":
            row["O"] = round(d * (0.75 + (idx % 4) * 0.05), 2)
            row["P"] = round(d * (0.85 + (idx % 5) * 0.07), 2)
            row["R"] = round(d * (2.25 + (idx % 5) * 0.14), 2)
            row["sigma_D"] = round(float(row["sigma_D"]) * 1.9, 2)
            row["sigma_L"] = round(float(row["sigma_L"]) * 1.8, 2)
            row["L_avg"] = round(float(row["L_avg"]) * 1.28, 2)
            row["rop_load"] = round(0.96 + (idx % 5) * 0.08, 2)
            row["p_diag"] = round(0.18 + (idx % 4) * 0.05, 2)
            row["p_rep"] = round(0.10 + (idx % 4) * 0.04, 2)
            row["actual_flow"] = round(float(row["planned_flow"]) * (0.75 + (idx % 5) * 0.06), 2)
            row["Cstop"] = round(float(row["Cstop"]) * 1.35, 2)
        else:
            raise ValueError(f"Unknown scenario: {kind}")

        # Tune demo statuses while keeping the scenario logic intact.
        if kind == "stable":
            ratios = [1.12, 1.25, 1.38, 1.48, 1.62, 1.22]
            _tune_availability(row, ratios[(idx - 1) % len(ratios)])
        elif kind == "medium":
            ratios = [0.58, 0.82, 0.94, 1.12, 1.33, 1.58, 0.72, 1.02]
            _tune_availability(row, ratios[(idx - 1) % len(ratios)])
    return rows


DEMO_SCENARIOS = {
    "Стабильный режим": _scenario_rows("stable"),
    "Средний режим": _scenario_rows("medium"),
    "Кризисный режим": _scenario_rows("crisis"),
}


def get_demo_dataframe(name: str) -> pd.DataFrame:
    """Return a working copy of built-in demo data."""
    if name not in DEMO_SCENARIOS:
        name = "Стабильный режим"
    return pd.DataFrame(deepcopy(DEMO_SCENARIOS[name]))[REQUIRED_COLUMNS]


def empty_input_dataframe(rows: int = 5) -> pd.DataFrame:
    """Create an empty manual input dataframe with safe defaults."""
    rows = max(1, int(rows))
    data = []
    for i in range(rows):
        data.append({
            "item_id": f"NEW-{i+1:03d}",
            "item_name": "Новая позиция",
            "unit": "ед.",
            "period": "2026-01",
            "rop_name": "ROP-1",
            "criticality_class": "важная",
            "O": 0.0,
            "P": 0.0,
            "R": 0.0,
            "D_avg": 1.0,
            "sigma_D": 0.0,
            "L_avg": 1.0,
            "sigma_L": 0.0,
            "rop_load": 0.75,
            "planned_flow": 1.0,
            "actual_flow": 1.0,
            "p_diag": 0.0,
            "p_rep": 0.0,
            "h": 1.0,
            "Cstop": 1000.0,
            "z0": 1.65,
            "alpha": 0.40,
            "beta": 0.80,
            "Kcrit_manual": 0.0,
            "Kload_manual": 0.0,
            "Kdev_manual": 0.0,
            "coeff_mode": "auto",
        })
    return pd.DataFrame(data)[REQUIRED_COLUMNS]
