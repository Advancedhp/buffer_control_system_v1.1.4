from src.demo_data import get_demo_dataframe
from src.buffer_model import calculate_dataset


def test_demo_has_expected_size_and_statuses():
    df = get_demo_dataframe("Кризисный режим")
    assert len(df) >= 20
    result = calculate_dataset(df)
    assert "Критическое отклонение" in set(result["status"])
