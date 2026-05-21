from src.demo_data import get_demo_dataframe
from src.buffer_model import calculate_dataset
from src.recommendations import add_recommendations


def test_recommendations_created():
    df = calculate_dataset(get_demo_dataframe("Стабильный режим"))
    df = add_recommendations(df)
    assert "recommendation" in df.columns
    assert df["recommendation"].str.len().min() > 10
