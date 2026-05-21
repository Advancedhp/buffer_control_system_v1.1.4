import pandas as pd

from src.demo_data import get_demo_dataframe
from src.validation import normalize_dataframe, validate_dataframe


def test_manual_coefficients_must_be_positive():
    df = get_demo_dataframe("Стабильный режим").head(1).copy()
    df["coeff_mode"] = "manual"
    df["Kcrit_manual"] = 0
    df["Kload_manual"] = 0
    df["Kdev_manual"] = 0
    errors = validate_dataframe(normalize_dataframe(df))
    assert any("Kcrit_manual" in err for err in errors)
    assert any("Kload_manual" in err for err in errors)
    assert any("Kdev_manual" in err for err in errors)


def test_nan_numeric_is_validation_error():
    df = get_demo_dataframe("Стабильный режим").head(1).copy()
    df["D_avg"] = pd.NA
    errors = validate_dataframe(normalize_dataframe(df))
    assert any("D_avg" in err for err in errors)
