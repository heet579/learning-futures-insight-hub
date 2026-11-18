"""Synthetic generation works for small inputs and leaves invalid runs unwritten."""
import pytest

from scripts import generate_large_synthetic_data as generator
from src.config import REQUIRED_COLUMNS


@pytest.mark.parametrize("count", [1, 7, 8, 23, 24, 64, 65])
def test_canonical_generation_supports_small_datasets(count):
    frame = generator.generate_canonical_responses(count)
    assert len(frame) == count
    assert list(frame.columns) == REQUIRED_COLUMNS
    assert frame["ResponseID"].is_unique
    assert frame["OverallSatisfaction"].between(1, 5).all()


@pytest.mark.parametrize("count", [0, -1, 1.5, True])
def test_canonical_generation_rejects_invalid_counts(count):
    with pytest.raises(ValueError, match="positive integer"):
        generator.generate_canonical_responses(count)


@pytest.mark.parametrize("factory", [
    generator.generate_qualtrics_8325_rows,
    generator.generate_qualtrics_8423_rows,
    generator.generate_qualtrics_8457_rows,
    generator.generate_qualtrics_8563_rows,
    generator.generate_qualtrics_8184_rows,
])
@pytest.mark.parametrize("count", [0, -1])
def test_course_generation_rejects_empty_or_negative_counts(factory, count):
    with pytest.raises(ValueError, match="positive integer"):
        factory(count)


@pytest.mark.parametrize("canonical,qualtrics", [(0, 2), (-1, 2), (2, 0), (2, -1)])
def test_invalid_generation_does_not_create_output(tmp_path, canonical, qualtrics):
    output = tmp_path / "generated"
    with pytest.raises(ValueError, match="positive integer"):
        generator.generate_all_test_datasets(canonical, qualtrics, data_dir=output)
    assert not output.exists()
