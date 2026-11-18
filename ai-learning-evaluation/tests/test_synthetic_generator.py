"""Synthetic generation works for small inputs and leaves invalid runs unwritten."""
from pathlib import Path
import subprocess
import sys

import pandas as pd
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


def test_cli_generates_into_a_separate_output_folder(tmp_path):
    app_folder = Path(__file__).resolve().parents[1]
    default_demo = app_folder / "data" / "synthetic_qualtrics_evaluation.csv"
    original_demo = default_demo.read_bytes()
    output = tmp_path / "isolated synthetic data"
    process = subprocess.run([
        sys.executable, "-m", "scripts.generate_large_synthetic_data",
        "--canonical-count", "3", "--qualtrics-count", "2",
        "--output-dir", str(output), "--no-excel", "--no-client",
    ], cwd=app_folder, capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stdout + process.stderr
    assert len(pd.read_csv(output / "synthetic_qualtrics_evaluation_large.csv")) == 3
    assert len(list((output / "synthetic_qualtrics_exports").glob("*.csv"))) == 5
    assert not list(output.rglob("*.xlsx"))
    assert not (output / "client").exists()
    assert default_demo.read_bytes() == original_demo


@pytest.mark.parametrize("option,value", [
    ("--canonical-count", "0"),
    ("--canonical-count", "-2"),
    ("--qualtrics-count", "0"),
    ("--qualtrics-count", "not-a-number"),
])
def test_cli_invalid_counts_show_a_clear_error(tmp_path, capsys, option, value):
    output = tmp_path / "unwritten"
    with pytest.raises(SystemExit) as exc:
        generator.main([option, value, "--output-dir", str(output)])
    assert exc.value.code == 2
    assert "positive integer" in capsys.readouterr().err
    assert not output.exists()
