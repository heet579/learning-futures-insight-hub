from src.analytics.quantitative import calculate_metrics

def test_golden_metrics_are_correct(golden_df):
    metrics = calculate_metrics(golden_df)
    assert metrics["response_count"] == 3
    assert metrics["ratings"]["OverallSatisfaction"]["mean"] == 4.0
    assert metrics["ratings"]["OverallSatisfaction"]["median"] == 4.0
    assert metrics["satisfaction_percent"] == 66.7
    assert metrics["recommendation_percent"] == 66.7
    assert metrics["ratings"]["OverallSatisfaction"]["distribution"] == {"1":0,"2":0,"3":1,"4":1,"5":1}

