from src.buffer_model import calculate_available_position, calculate_sigma_lt, calculate_adaptive_z, calculate_pshort


def test_available_position():
    assert calculate_available_position(70, 120, 130) == 60


def test_sigma_lt_positive():
    value = calculate_sigma_lt(40, 4, 5, 0.5)
    assert round(value, 2) == 21.91


def test_adaptive_z():
    value = calculate_adaptive_z(1.65, 0.4, 0.8, 0.10, 0.05)
    assert round(value, 3) == 1.782


def test_pshort_decreases():
    assert calculate_pshort(50, 20) < calculate_pshort(10, 20)
