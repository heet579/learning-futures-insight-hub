import pandas as pd
import pytest
import os
import sys
import tkinter as tk


@pytest.fixture(scope='session')
def tk_runtime():
    """One Tcl interpreter per run; each test creates its own disposable Toplevel."""
    from src.ui.runtime import _setup_environment
    _setup_environment()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        if sys.platform == 'win32' or os.getenv('REQUIRE_DESKTOP_TESTS') == '1':
            raise
        pytest.skip(f'Tk display unavailable: {exc}')
    root.withdraw()
    yield root
    root.destroy()

@pytest.fixture
def golden_df():
    return pd.DataFrame([
        {"ResponseID":"1","RecordedDate":"2026-01-01","CourseCode":"C1","CourseName":"Course","DeliveryMode":"Online","ClientType":"Corporate","FacilitatorCode":"F1","OverallSatisfaction":5,"ContentQuality":4,"FacilitatorEffectiveness":5,"CourseRelevance":4,"WouldRecommend":"Yes","MostValuableAspect":"Clear facilitator","WhatCouldImprove":"More practical exercises","AdditionalComments":""},
        {"ResponseID":"2","RecordedDate":"2026-01-02","CourseCode":"C1","CourseName":"Course","DeliveryMode":"Online","ClientType":"Corporate","FacilitatorCode":"F1","OverallSatisfaction":3,"ContentQuality":4,"FacilitatorEffectiveness":4,"CourseRelevance":2,"WouldRecommend":"No","MostValuableAspect":"Useful examples","WhatCouldImprove":"Pace was too fast","AdditionalComments":"fake@example.com"},
        {"ResponseID":"3","RecordedDate":"2026-01-03","CourseCode":"C1","CourseName":"Course","DeliveryMode":"Online","ClientType":"Corporate","FacilitatorCode":"F1","OverallSatisfaction":4,"ContentQuality":5,"FacilitatorEffectiveness":5,"CourseRelevance":5,"WouldRecommend":"Yes","MostValuableAspect":"Relevant to work","WhatCouldImprove":"","AdditionalComments":None},
    ])


@pytest.fixture(autouse=True)
def isolated_report_library(monkeypatch, tmp_path):
    monkeypatch.setenv('REPORT_LIBRARY_PATH', str(tmp_path / 'reports.sqlite3'))
    # Tests use the local library unless a test starts its own server.
    monkeypatch.delenv('SERVER_URL', raising=False)
