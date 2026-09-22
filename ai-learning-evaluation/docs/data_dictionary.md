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

All included records above are synthetic.

## Real PACE/Qualtrics export mapping

Live course-evaluation exports use generic Qualtrics question codes (`Q2_1`, `Q4_3`, ...) that shift between survey template versions, so `src/ingestion/qualtrics_loader.py::load_qualtrics_export` resolves each column by matching the **question-text header row** (Qualtrics' second header line) against known phrasing, not by fixed column position. Columns with no canonical fit are dropped, never guessed at.

| Real question text (any matching column) | Canonical field | Notes |
|---|---|---|
| "Response ID" | ResponseID | renamed from `ResponseId` |
| "Recorded Date" | RecordedDate | reparsed with `dayfirst=True` (AU export format, e.g. `10/8/2023 16:08`) then stored as ISO 8601 |
| filename, e.g. `8325 - Leadership and Management Essentials - August 2023...csv` | CourseCode, CourseName | no course columns exist in the data itself; the numeric course ID and title are parsed from the export filename |
| "Overall, I was satisfied with the course" | OverallSatisfaction | Likert text mapped 1–5, see below |
| "The course materials provided were useful" | ContentQuality | closest-matching item; other content-adjacent items (learned what expected, presenter subject knowledge) are not mapped |
| "Overall, the presenter(s) were effective" | FacilitatorEffectiveness | closest-matching item; Q&A helpfulness is not mapped |
| "I will apply what I've learnt in this course" | CourseRelevance | |
| "On a scale from 0-10, how likely are you to recommend this short course..." | WouldRecommend | raw 0–10 NPS score thresholded at ≥7 = Yes; the separate Promoter/Passive/Detractor group column is not used |
| "In this course, I really enjoyed:" | MostValuableAspect | not present in every survey version; blank where absent |
| "This course could be improved by:" | WhatCouldImprove | |
| "...feedback or suggestions for the presenters" / "Overall, I would recommend:" (free text) | AdditionalComments | |
| `IPAddress`, `RecipientFirstName`, `RecipientLastName`, `RecipientEmail`, `ExternalReference`, `LocationLatitude`, `LocationLongitude` | *(dropped)* | identifier columns removed at load time, before any analytics run |
| `DeliveryMode`, `ClientType`, `FacilitatorCode` | *(left blank)* | not present anywhere in the real export; no reliable source to derive them from |

Likert text values are mapped to 1–5: `Strongly disagree`=1, `Somewhat disagree`=2, `Neither agree nor disagree`=3, `Somewhat agree`=4, `Strongly agree`=5.

`load_qualtrics_folder(path)` applies this mapping to every CSV in a folder (one file per course) and concatenates the result, which is how `data/client/` is loaded as a single multi-course dataset.

