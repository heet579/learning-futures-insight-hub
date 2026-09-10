import pandas as pd
import pytest

@pytest.fixture
def golden_df():
    return pd.DataFrame([
        {"ResponseID":"1","RecordedDate":"2026-01-01","CourseCode":"C1","CourseName":"Course","DeliveryMode":"Online","ClientType":"Corporate","FacilitatorCode":"F1","OverallSatisfaction":5,"ContentQuality":4,"FacilitatorEffectiveness":5,"CourseRelevance":4,"WouldRecommend":"Yes","MostValuableAspect":"Clear facilitator","WhatCouldImprove":"More practical exercises","AdditionalComments":""},
        {"ResponseID":"2","RecordedDate":"2026-01-02","CourseCode":"C1","CourseName":"Course","DeliveryMode":"Online","ClientType":"Corporate","FacilitatorCode":"F1","OverallSatisfaction":3,"ContentQuality":4,"FacilitatorEffectiveness":4,"CourseRelevance":2,"WouldRecommend":"No","MostValuableAspect":"Useful examples","WhatCouldImprove":"Pace was too fast","AdditionalComments":"fake@example.com"},
        {"ResponseID":"3","RecordedDate":"2026-01-03","CourseCode":"C1","CourseName":"Course","DeliveryMode":"Online","ClientType":"Corporate","FacilitatorCode":"F1","OverallSatisfaction":4,"ContentQuality":5,"FacilitatorEffectiveness":5,"CourseRelevance":5,"WouldRecommend":"Yes","MostValuableAspect":"Relevant to work","WhatCouldImprove":"","AdditionalComments":None},
    ])

