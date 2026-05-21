"""Calculation core for ROP buffer control.

The model follows the scientific logic used in the research work:
A -> sigma_LT -> z -> Bstat -> Btar -> Pshort -> Bopt -> reorder point -> Ibuf -> status.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .coefficients import resolve_coefficients, safe_float
from .status_rules import DEFAULT_CRITICAL_THRESHOLD, DEFAULT_NORMAL_THRESHOLD, DEFAULT_SURPLUS_THRESHOLD, define_status

SQRT_2 = math.sqrt(2.0)
SQRT_2PI = math.sqrt(2.0 * math.pi)


def normal_cdf(x: float) -> float:
    """Standard normal CDF using math.erf, without scipy dependency."""
    return 0.5 * (1.0 + math.erf(x / SQRT_2))


def calculate_available_position(O: float, P: float, R: float) -> float:
    """A = O + P - R."""
    return safe_float(O) + safe_float(P) - safe_float(R)


def calculate_sigma_lt(D_avg: float, sigma_D: float, L_avg: float, sigma_L: float) -> float:
    """Standard deviation of demand during lead time.

    sigma_LT = sqrt(L_avg * sigma_D^2 + D_avg^2 * sigma_L^2)
    """
    d_avg = max(safe_float(D_avg), 0.0)
    sig_d = max(safe_float(sigma_D), 0.0)
    l_avg = max(safe_float(L_avg), 0.0)
    sig_l = max(safe_float(sigma_L), 0.0)
    return math.sqrt(l_avg * sig_d**2 + d_avg**2 * sig_l**2)


def calculate_adaptive_z(z0: float, alpha: float, beta: float, p_diag: float, p_rep: float) -> float:
    """z = z0 * (1 + alpha * p_diag + beta * p_rep)."""
    return max(safe_float(z0, 1.65), 0.0) * (
        1.0 + max(safe_float(alpha), 0.0) * max(safe_float(p_diag), 0.0)
        + max(safe_float(beta), 0.0) * max(safe_float(p_rep), 0.0)
    )


def calculate_bstat(z: float, sigma_lt: float) -> float:
    """Bstat = z * sigma_LT."""
    return max(safe_float(z), 0.0) * max(safe_float(sigma_lt), 0.0)


def calculate_btar(bstat: float, kcrit: float, kload: float, kdev: float) -> float:
    """Btar = Bstat * Kcrit * Kload * Kdev."""
    return max(safe_float(bstat), 0.0) * max(safe_float(kcrit, 1.0), 0.0) * max(safe_float(kload, 1.0), 0.0) * max(safe_float(kdev, 1.0), 0.0)


def calculate_pshort(B: float, sigma_lt: float) -> float:
    """Probability of shortage at buffer level B.

    Pshort(B,t) = 1 - Phi(B / sigma_LT).

    If sigma_LT is zero, uncertainty is absent in the simplified model. Any non-negative
    buffer is then treated as sufficient for the stochastic part, and Pshort is set to 0.
    """
    buffer = max(safe_float(B), 0.0)
    sigma = max(safe_float(sigma_lt), 0.0)
    if sigma <= 1e-9:
        return 0.0
    return max(0.0, min(1.0, 1.0 - normal_cdf(buffer / sigma)))


def total_expected_cost(B: float, sigma_lt: float, h: float, cstop: float) -> tuple[float, float, float, float]:
    """Return total cost, Pshort, holding cost, and expected stop loss."""
    buffer = max(safe_float(B), 0.0)
    h_value = max(safe_float(h), 0.0)
    cstop_value = max(safe_float(cstop), 0.0)
    pshort = calculate_pshort(buffer, sigma_lt)
    holding_cost = h_value * buffer
    expected_stop_loss = cstop_value * pshort
    total_cost = holding_cost + expected_stop_loss
    return total_cost, pshort, holding_cost, expected_stop_loss


def optimize_buffer(btar: float, sigma_lt: float, h: float, cstop: float) -> dict[str, float | str]:
    """Optimize B under the constraint B >= Btar.

    Objective: h * B + Cstop * Pshort(B,t), where Pshort is based on sigma_LT.
    The target buffer Btar is used as a technological lower bound that protects ROP.
    """
    lower_bound = max(safe_float(btar), 1.0)
    sigma = max(safe_float(sigma_lt), 0.0)
    h_value = max(safe_float(h), 0.0)
    cstop_value = max(safe_float(cstop), 0.0)

    note = "Стоимостная оптимизация выполнена"

    if h_value <= 0 or cstop_value <= 0 or sigma <= 1e-9:
        total_cost, pshort, holding_cost, expected_stop_loss = total_expected_cost(lower_bound, sigma, h_value, cstop_value)
        if h_value <= 0 or cstop_value <= 0:
            note = "Bopt принят равным Btar: отсутствуют корректные стоимостные параметры h или Cstop"
        else:
            note = "Bopt принят равным Btar: отсутствует вариативность sigma_LT"
        return {
            "Bopt": lower_bound,
            "Pshort": pshort,
            "holding_cost": holding_cost,
            "expected_stop_loss": expected_stop_loss,
            "expected_total_cost": total_cost,
            "optimization_note": note,
        }

    # Closed-form stationary point for h*B + Cstop*(1-Phi(B/sigma)).
    # derivative = h - Cstop * phi(B/sigma) / sigma
    threshold = h_value * sigma / cstop_value
    if threshold > 0 and threshold < (1.0 / SQRT_2PI):
        z_star = math.sqrt(max(0.0, -2.0 * math.log(threshold * SQRT_2PI)))
        unconstrained_b = sigma * z_star
        candidate = max(lower_bound, unconstrained_b)
    else:
        candidate = lower_bound

    # Compare with lower bound to guard against numerical artifacts.
    candidates = [lower_bound, candidate]
    best = min(candidates, key=lambda value: total_expected_cost(value, sigma, h_value, cstop_value)[0])
    total_cost, pshort, holding_cost, expected_stop_loss = total_expected_cost(best, sigma, h_value, cstop_value)

    return {
        "Bopt": best,
        "Pshort": pshort,
        "holding_cost": holding_cost,
        "expected_stop_loss": expected_stop_loss,
        "expected_total_cost": total_cost,
        "optimization_note": note,
    }


def calculate_reorder_point(D_avg: float, L_avg: float, bopt: float) -> float:
    """s = D_avg * L_avg + Bopt."""
    return max(safe_float(D_avg), 0.0) * max(safe_float(L_avg), 0.0) + max(safe_float(bopt), 0.0)


def calculate_ibuf(A: float, bopt: float) -> float:
    """Ibuf = A / Bopt. Bopt has a technological minimum, so infinity is avoided."""
    bopt_value = max(safe_float(bopt), 1.0)
    return safe_float(A) / bopt_value


def calculate_row(
    row: dict[str, Any] | pd.Series,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    normal_threshold: float = DEFAULT_NORMAL_THRESHOLD,
    surplus_threshold: float = DEFAULT_SURPLUS_THRESHOLD,
) -> dict[str, Any]:
    """Calculate all model outputs for one item row."""
    row_dict = dict(row)

    A = calculate_available_position(row_dict.get("O"), row_dict.get("P"), row_dict.get("R"))
    sigma_lt = calculate_sigma_lt(
        row_dict.get("D_avg"),
        row_dict.get("sigma_D"),
        row_dict.get("L_avg"),
        row_dict.get("sigma_L"),
    )
    z = calculate_adaptive_z(
        row_dict.get("z0"),
        row_dict.get("alpha"),
        row_dict.get("beta"),
        row_dict.get("p_diag"),
        row_dict.get("p_rep"),
    )
    kcrit, kload, kdev = resolve_coefficients(row_dict)
    bstat = calculate_bstat(z, sigma_lt)
    btar = calculate_btar(bstat, kcrit, kload, kdev)
    optimization = optimize_buffer(btar, sigma_lt, row_dict.get("h"), row_dict.get("Cstop"))
    bopt = float(optimization["Bopt"])
    reorder_point = calculate_reorder_point(row_dict.get("D_avg"), row_dict.get("L_avg"), bopt)
    ibuf = calculate_ibuf(A, bopt)
    pshort_current = 1.0 if A <= 0 else calculate_pshort(A, sigma_lt)
    status = define_status(ibuf, critical_threshold, normal_threshold, surplus_threshold)

    return {
        "A": A,
        "sigma_LT": sigma_lt,
        "z": z,
        "Kcrit": kcrit,
        "Kload": kload,
        "Kdev": kdev,
        "Bstat": bstat,
        "Btar": btar,
        "Pshort": optimization["Pshort"],
        "Pshort_current": pshort_current,
        "holding_cost": optimization["holding_cost"],
        "expected_stop_loss": optimization["expected_stop_loss"],
        "expected_total_cost": optimization["expected_total_cost"],
        "Bopt": bopt,
        "reorder_point": reorder_point,
        "Ibuf": ibuf,
        "status": status,
        "optimization_note": optimization["optimization_note"],
    }


def calculate_dataset(
    df: pd.DataFrame,
    critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
    normal_threshold: float = DEFAULT_NORMAL_THRESHOLD,
    surplus_threshold: float = DEFAULT_SURPLUS_THRESHOLD,
) -> pd.DataFrame:
    """Calculate model outputs for a whole dataframe."""
    if df.empty:
        return df.copy()
    base = df.copy()
    outputs = base.apply(
        lambda row: calculate_row(row, critical_threshold, normal_threshold, surplus_threshold),
        axis=1,
        result_type="expand",
    )
    result = pd.concat([base.reset_index(drop=True), outputs.reset_index(drop=True)], axis=1)
    # Add rounded human-readable values while preserving raw columns for calculations.
    numeric_cols = [
        "A", "sigma_LT", "z", "Kcrit", "Kload", "Kdev", "Bstat", "Btar",
        "Pshort", "Pshort_current", "holding_cost", "expected_stop_loss", "expected_total_cost",
        "Bopt", "reorder_point", "Ibuf",
    ]
    for col in numeric_cols:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    return result
