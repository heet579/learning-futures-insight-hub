# Demonstration data dictionary

| Field | Type / values | Purpose |
|---|---|---|
| ResponseID | text, unique | response trace within input; not exposed as learner identity |
| RecordedDate | ISO date/time | collection timing and validation |
| CourseCode / CourseName | text | course scope and reporting label |
| DeliveryMode | Online, Hybrid, Face-to-face | delivery context |
| ClientType | synthetic category | audience/context demonstration |
| FacilitatorCode | pseudonymous text | delivery reference without facilitator name |
| OverallSatisfaction | integer 1–5 | overall learner rating |
| ContentQuality | integer 1–5 | content rating |
| FacilitatorEffectiveness | integer 1–5 | facilitator rating |
| CourseRelevance | integer 1–5 | applicability/relevance rating |
| WouldRecommend | Yes/No | recommendation-rate calculation |
| MostValuableAspect | free text | positive/valuable feedback evidence |
| WhatCouldImprove | free text | improvement evidence |
| AdditionalComments | free text | other feedback; PII masking applies |

All included records are synthetic. Production mapping must preserve Qualtrics question identifiers and versions rather than relying only on display labels.

