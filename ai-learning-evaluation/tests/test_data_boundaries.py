"""Regression checks for incomplete surveys and contact details entering analysis."""
from io import BytesIO

import pandas as pd
import pytest

from src.analytics.quantitative import calculate_metrics
from src.config import RATING_COLUMNS, TEXT_COLUMNS
from src.ingestion.qualtrics_loader import load_csv
from src.ingestion.validator import validate_dataframe
from src.privacy.pii_masker import detect_pii_counts, mask_dataframe, mask_text
from src import workspace


def test_invalid_ratings_do_not_inflate_satisfaction_or_its_denominator(golden_df):
    frame = pd.concat([golden_df, golden_df], ignore_index=True)
    frame['OverallSatisfaction'] = ['5', '4', None, '0', '6', 'broken']
    metrics = calculate_metrics(frame)
    assert metrics['response_count'] == 6
    assert metrics['ratings']['OverallSatisfaction']['count'] == 2
    assert metrics['ratings']['OverallSatisfaction']['mean'] == 4.5
    assert metrics['satisfaction_count'] == 2 and metrics['satisfaction_percent'] == 100.0


def test_unknown_recommendations_are_excluded_from_the_denominator(golden_df):
    frame = pd.concat([golden_df, golden_df], ignore_index=True)
    frame['WouldRecommend'] = ['Yes', 'No', 'unknown', None, 'true', '']
    metrics = calculate_metrics(frame)
    assert metrics['recommendation_count'] == 2
    assert metrics['recommendation_total'] == 3
    assert metrics['recommendation_percent'] == 66.7


def test_no_valid_ratings_produce_missing_values_instead_of_zero_scores(golden_df):
    for column in RATING_COLUMNS:
        golden_df[column] = None
    golden_df['WouldRecommend'] = None
    metrics = calculate_metrics(golden_df)
    assert metrics['satisfaction_percent'] is None
    assert metrics['recommendation_percent'] is None
    assert metrics['strongest_area'] is None and metrics['lowest_area'] is None
    assert all(value['count'] == 0 and value['mean'] is None for value in metrics['ratings'].values())


def test_uncollected_fields_do_not_lower_completeness(golden_df):
    golden_df['DeliveryMode'] = None
    with_field = calculate_metrics(golden_df)
    without_field = calculate_metrics(golden_df.drop(columns=['DeliveryMode']))
    assert 'DeliveryMode' in with_field['fields_not_in_source']
    assert with_field['response_completeness'] == without_field['response_completeness']


def test_empty_survey_and_missing_columns_block_workspace_creation(golden_df):
    for invalid in (golden_df.iloc[:0], golden_df.drop(columns=['ResponseID'])):
        result = validate_dataframe(invalid)
        assert not result.valid and result.errors
        with pytest.raises(ValueError):
            workspace.new_state(invalid, ['survey.csv'])


def test_duplicate_and_blank_response_ids_remain_visible_as_warnings(golden_df):
    golden_df['ResponseID'] = ['same', 'same', ' ']
    result = validate_dataframe(golden_df)
    assert result.valid
    assert any('duplicate ResponseID' in warning for warning in result.warnings)
    assert any('blank value' in warning for warning in result.warnings)


def test_masking_is_idempotent_and_does_not_modify_source_data(golden_df):
    golden_df.loc[0, 'AdditionalComments'] = 'Contact learner@example.invalid or 0412 345 678; https://example.invalid/a'
    original = golden_df.copy(deep=True)
    masked, changed = mask_dataframe(golden_df)
    again, second_changes = mask_dataframe(masked)
    pd.testing.assert_frame_equal(golden_df, original)
    pd.testing.assert_frame_equal(masked, again)
    assert changed > 0 and second_changes == 0
    assert detect_pii_counts(masked) == {'emails': 0, 'phones': 0, 'urls': 0}
    assert masked['ResponseID'].equals(original['ResponseID'])


@pytest.mark.parametrize('value', [None, float('nan'), pd.NA])
def test_missing_feedback_is_not_turned_into_a_comment(value):
    assert pd.isna(mask_text(value))


def test_workspace_context_uses_masked_comments_and_keeps_input_unchanged(golden_df):
    for column in TEXT_COLUMNS:
        golden_df[column] = 'Useful examples. Contact learner@example.invalid'
    original = golden_df.copy(deep=True)
    state = workspace.new_state(golden_df, ['survey.csv'])
    assert state['masked_count'] == len(golden_df) * len(TEXT_COLUMNS)
    assert 'learner@example.invalid' not in state['frame'][TEXT_COLUMNS].to_json()
    assert state['context'].metrics['response_count'] == len(golden_df)
    pd.testing.assert_frame_equal(golden_df, original)


def test_latin1_csv_preserves_non_ascii_feedback(golden_df):
    golden_df.loc[0, 'AdditionalComments'] = 'Helpful café discussion'
    loaded = load_csv(BytesIO(golden_df.to_csv(index=False).encode('latin-1')))
    assert loaded.loc[0, 'AdditionalComments'] == 'Helpful café discussion'


def test_no_file_selection_returns_an_actionable_error():
    with pytest.raises(ValueError, match='Choose at least one survey file'):
        workspace.load_files([])
