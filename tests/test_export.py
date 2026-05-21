from io import BytesIO

import pandas as pd

from src.buffer_model import calculate_dataset
from src.demo_data import get_demo_dataframe
from src.export import multi_sheet_export_bytes
from src.recommendations import add_recommendations


def test_export_contains_expected_sheets():
    input_df = get_demo_dataframe("Стабильный режим")
    result_df = add_recommendations(calculate_dataset(input_df))
    data = multi_sheet_export_bytes(input_df, result_df)
    xls = pd.ExcelFile(BytesIO(data))
    assert {"input_data", "calculation_result", "summary", "recommendations"}.issubset(set(xls.sheet_names))
