from src.coefficients import resolve_coefficients, safe_float


def test_safe_float_handles_nan():
    assert safe_float(float('nan'), 3.0) == 3.0
    assert safe_float(None, 2.0) == 2.0


def test_manual_coefficients_are_used():
    row = {
        "coeff_mode": "manual",
        "Kcrit_manual": 1.5,
        "Kload_manual": 1.25,
        "Kdev_manual": 1.1,
        "criticality_class": "обычная",
        "rop_load": 0.1,
        "planned_flow": 100,
        "actual_flow": 100,
    }
    assert resolve_coefficients(row) == (1.5, 1.25, 1.1)
