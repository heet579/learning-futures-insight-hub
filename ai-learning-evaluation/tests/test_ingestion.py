from io import StringIO
import pandas as pd
from src.ingestion.qualtrics_loader import load_csv
from src.ingestion.validator import validate_dataframe

def test_csv_successfully_loads(golden_df):
    loaded = load_csv(StringIO(golden_df.to_csv(index=False)))
    assert len(loaded) == 3
    assert validate_dataframe(loaded).valid

def test_missing_required_columns_are_handled(golden_df):
    result = validate_dataframe(golden_df.drop(columns=["CourseCode"]))
    assert not result.valid
    assert "CourseCode" in result.missing_columns

def test_invalid_values_become_warnings_not_crashes(golden_df):
    data = golden_df.copy()
    data.loc[0, "RecordedDate"] = "not-a-date"
    data.loc[1, "OverallSatisfaction"] = 9
    result = validate_dataframe(data)
    assert result.valid
    assert any("invalid date" in warning for warning in result.warnings)
    assert any("out-of-range" in warning for warning in result.warnings)

def test_qualtrics_multi_row_headers_are_stripped(golden_df):
    header_rows = pd.DataFrame([
        {col: col for col in golden_df.columns},
        {"ResponseID": '{"ImportId":"ResponseID"}'},
    ])
    combined = pd.concat([header_rows, golden_df], ignore_index=True)
    loaded = load_csv(StringIO(combined.to_csv(index=False)))
    assert len(loaded) == len(golden_df)
    assert validate_dataframe(loaded).valid

