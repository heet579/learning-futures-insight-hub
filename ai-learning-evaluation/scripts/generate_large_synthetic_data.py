"""Generate comprehensive, high-volume synthetic evaluation data for testing.

Produces both:
1. Canonical Schema datasets (CSV and XLSX) for single-file import, metric cards,
   and dashboard performance testing.
2. Authentic 3-header Qualtrics course exports (CSV and XLSX) matching real PACE /
   Learning Futures formats across 2023, 2024, and 2025.

No real individuals or confidential client feedback are contained herein.
All names, comments, contact details, and scores are wholly synthetic.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from html import escape
import io
from pathlib import Path
import random
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED

import pandas as pd

from src.config import REQUIRED_COLUMNS

# ---------------------------------------------------------------------------
# Authentic Synthetic Text Pools (Adelaide PACE & Learning Futures context)
# ---------------------------------------------------------------------------

POSITIVE_FACILITATOR = [
    "Sonali was an exceptional facilitator who explained complex frameworks with relatable real-world leadership examples.",
    "The presenter was extremely knowledgeable and answered every difficult organizational question with practical clarity.",
    "Mark Priadko's enthusiasm and deep subject matter expertise made the finance concepts genuinely enjoyable and digestible.",
    "Alina was very engaging, energetic, and kept everyone focused throughout both intense workshop days.",
    "Gary Edwards and Mark Priadko delivered seamless presentations with outstanding facilitator interaction.",
    "The facilitator clearly explained the six leadership styles and how to switch between them effectively.",
    "Passionate delivery from the teacher that inspired active participation from the entire cohort.",
    "The facilitators were patient, articulate, and provided individual coaching during the exercises.",
]

IMPROVE_FACILITATOR = [
    "The facilitator moved too quickly through the technical financial statements on Day Two.",
    "Would appreciate the facilitator providing more dedicated time for participant questions during complex policy modules.",
    "The teacher occasionally rushed through the summary slides before everyone finished taking notes.",
]

POSITIVE_PRACTICAL = [
    "The hands-on practical exercises gave me actionable tools to implement immediately with my direct reports.",
    "Interactive breakout activity helped us practice difficult workplace conversations in a supportive environment.",
    "Great practical balance between theory and hands-on simulation of team problem-solving.",
    "Loved the bird personality activity and learning practical ways to adapt communication styles.",
    "The practical exercises around delegation and team reframing were the highlight of the week.",
]

IMPROVE_PRACTICAL = [
    "More hands-on practical activities and workplace exercises rather than lecture slides would improve the learning.",
    "Would like more practical practice on conflict management scenarios rather than just theoretical models.",
    "The practical session was a bit rushed; needed more exercise time to complete the team assignment.",
    "Include more structured workplace simulations with constructive feedback from peers.",
]

POSITIVE_PACING = [
    "Well-paced across both days with adequate breaks to absorb the information and reflect.",
    "Good timing throughout each session, covering every scheduled topic without feeling rushed.",
    "The rhythm of the sessions kept momentum high without causing mental fatigue.",
]

IMPROVE_PACING = [
    "Starting at 9:15am instead of 8:45am would be much more family-friendly for parents managing school drop-offs.",
    "The two-day format felt rushed with so much content; extending this course over three days would be much better.",
    "Pacing on the second afternoon was too fast when covering strategic risk models.",
    "A couple of afternoon topics were too rushed and we didn't complete the workbook content in time.",
    "Needed an extra 30 minutes for the strategy and finance presentations so it would be less rushed.",
]

POSITIVE_RELEVANCE = [
    "Directly relevant to my everyday role as a team leader transitioning from operational delivery.",
    "Highly useful frameworks that I will apply immediately in our departmental quarterly planning.",
    "The most relevant professional development course I have attended in my 10-year career.",
    "Applicable insights that help me reframe conversations with senior stakeholders and executive leadership.",
    "The strategies around influence without formal authority are directly applicable to my project team.",
]

IMPROVE_RELEVANCE = [
    "Would benefit from tailoring the case studies more specifically to my public sector workplace and team needs.",
    "Some introductory modules felt too undergraduate-level; needs higher-level strategic relevance for senior managers.",
    "Include more sector-specific examples that are directly applicable to local government and non-profit roles.",
]

POSITIVE_MATERIALS = [
    "The comprehensive course workbook and reference materials will be a valuable desk guide for our team.",
    "Excellent handouts and structured slide notes that were easy to follow and review.",
    "Course materials provided were useful and included clear step-by-step templates and checklists.",
    "The digital resources and supplementary reading lists are of high quality.",
]

IMPROVE_MATERIALS = [
    "Course materials could include more blank templates and checklist worksheets for team delegation.",
    "Provide optional reading materials and slide deck PDFs prior to the first course day.",
    "More practice questions and self-reflection prompts in the workbook would strengthen retention.",
    "A digital version of the notes to work through on laptops or iPads during the course would be helpful.",
]

POSITIVE_ENGAGEMENT = [
    "Fantastic networking with fellow participants from varied South Australian industries and agencies.",
    "Loved the open discussion and interactive sharing of real challenges across different sectors.",
    "The presenter's engaging storytelling kept energy levels high and stimulated lively group discussion.",
    "Beneficial peer interaction that helped us benchmark our practices against other organizations.",
    "The respectful atmosphere encouraged everyone to share vulnerable management dilemmas.",
]

IMPROVE_ENGAGEMENT = [
    "More structured opportunities for networking and cross-table discussion would be welcome.",
    "A few dominant participants took over discussions; facilitator could encourage broader participation.",
    "Incorporate more small-group interaction instead of large room seminar presentation.",
]

POSITIVE_EXAMPLES = [
    "Real-life examples from the presenter's personal executive experience made the theories come alive.",
    "The strategic scenario case studies provided great context for decision making under pressure.",
    "Loved the industry case studies examining both successful transformations and costly pitfalls.",
    "The case studies from South Australian organizations were realistic and relatable.",
]

IMPROVE_EXAMPLES = [
    "Incorporate a broader variety of case studies across multiple industries, not just one single sector.",
    "More Adelaide and South Australian industry examples would make the strategic concepts even more grounded.",
    "If GenAI examples are discussed, it is important to address accuracy limitations and governance risks.",
]

POSITIVE_FACILITY = [
    "The venue facilities at Adelaide University North Terrace campus were comfortable and conducive to learning.",
    "Catering from Finicky catering was fresh, delicious, and well-organized throughout.",
    "Friendly staff, convenient break areas, and great hospitality throughout the sessions.",
]

IMPROVE_FACILITY = [
    "The online platform had minor audio connectivity issues during the morning session.",
    "General sound quality in the large tutorial room could be improved; the microphone echo was distracting.",
    "Room temperature was quite cold in the morning session before air conditioning adjusted.",
]

NEUTRAL_COMMENTS = [
    "The course covered all expected learning objectives as advertised in the syllabus.",
    "No additional comments; the professional development session was as described.",
    "Completed all modules; satisfactory delivery overall.",
    "Everything ran according to the timetable.",
    "The session met the required standard for our development plan.",
]

# Synthetic PII candidates for testing privacy detection and regex masking
PII_COMMENTS = [
    "Happy to provide further feedback - contact me at sarah.jenkins@adelaide.edu.au or 0412 345 678.",
    "If you need our team case study, email mark.williams@sa.gov.au or call (08) 8313 1234.",
    "My contact is rachel.taylor@company.com.au / 0418 921 445; reference notes at https://pace.adelaide.edu.au/resources.",
    "You can reach Nick Van Holst at nick.vanholst@adelaide.edu.au for the follow-up focus group.",
    "Call David Miller on 0401 223 889 if you hold the future leadership focus session; slides at www.example.org/review.",
    "Please send the certificate to michael.chen@defense.gov.au or call 0422 889 123.",
    "Feedback from Elena Rostova: loved the materials, visit https://learningfutures.adelaide.edu.au/cohort-notes.",
    "Please contact Jessica at jessica.b@health.sa.gov.au or 0433 991 224 for our hospital leadership survey.",
]

CANONICAL_COURSES = [
    ("PACE-8325", "Leadership and Management Essentials", "Face-to-face", "Corporate", "FAC-014"),
    ("PACE-8423", "Finance for Non-Financial Managers", "Face-to-face", "Corporate", "FAC-008"),
    ("PACE-8457", "From Team Member to Team Leader", "Face-to-face", "Government", "FAC-022"),
    ("PACE-8563", "Strategic Thinking", "Face-to-face", "Higher Education", "FAC-031"),
    ("LF-101", "Executive Leadership & Team Performance", "Face-to-face", "Corporate", "FAC-014"),
    ("LF-205", "Applied Project & Stakeholder Communication", "Online", "Government", "FAC-022"),
    ("LF-310", "Digital Transformation Foundations", "Hybrid", "Corporate", "FAC-009"),
    ("LF-420", "AI Literacy & Strategic Technology", "Hybrid", "Higher Education", "FAC-031"),
    ("LF-515", "Strategic Change Leadership", "Online", "Not-for-profit", "FAC-018"),
    ("LF-605", "Healthcare Innovation & Clinical Leadership", "Face-to-face", "Healthcare", "FAC-027"),
    ("LF-710", "Defense Industry Governance & Strategy", "Hybrid", "Defense", "FAC-040"),
]

LIKERT_CHOICES = [
    ("Strongly agree", 5),
    ("Somewhat agree", 4),
    ("Neither agree nor disagree", 3),
    ("Somewhat disagree", 2),
    ("Strongly disagree", 1),
]

# ---------------------------------------------------------------------------
# Pure-Python Streaming XLSX Writer (Zero extra dependencies)
# ---------------------------------------------------------------------------

def write_dataframe_to_xlsx(path: str | Path, df_or_rows: pd.DataFrame | list[list[Any]], sheet_name: str = "Survey") -> Path:
    """Write tabular data into a valid, optimized OOXML (.xlsx) file using standard zipfile."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(df_or_rows, pd.DataFrame):
        rows = [list(df_or_rows.columns), *df_or_rows.fillna("").astype(str).values.tolist()]
    else:
        rows = df_or_rows

    parts = ['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for r_idx, row in enumerate(rows, 1):
        parts.append(f'<row r="{r_idx}">')
        for c_idx, val in enumerate(row, 1):
            col_name, num = "", c_idx
            while num:
                num, remainder = divmod(num - 1, 26)
                col_name = chr(65 + remainder) + col_name
            text = escape(str(val)) if val is not None else ""
            parts.append(f'<c r="{col_name}{r_idx}" t="inlineStr"><is><t>{text}</t></is></c>')
        parts.append('</row>')
    parts.append('</sheetData></worksheet>')
    sheet_xml = "".join(parts)

    with ZipFile(path, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            '[Content_Types].xml',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        )
        archive.writestr(
            '_rels/.rels',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        archive.writestr(
            'xl/workbook.xml',
            f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
        )
        archive.writestr(
            'xl/_rels/workbook.xml.rels',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        )
        archive.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    return path


# ---------------------------------------------------------------------------
# Sampling Helpers
# ---------------------------------------------------------------------------

def _sample_rating(rng: random.Random, mean: float, std: float = 0.72) -> int:
    return max(1, min(5, round(rng.gauss(mean, std))))


def _rating_to_likert(score: int) -> str:
    mapping = {5: "Strongly agree", 4: "Somewhat agree", 3: "Neither agree nor disagree", 2: "Somewhat disagree", 1: "Strongly disagree"}
    return mapping.get(score, "Neither agree nor disagree")


def _sample_nps(rng: random.Random, overall: int) -> tuple[int, str]:
    if overall >= 5:
        score = rng.choices([10, 9, 8], weights=[0.60, 0.32, 0.08])[0]
    elif overall == 4:
        score = rng.choices([9, 8, 7, 6], weights=[0.25, 0.50, 0.20, 0.05])[0]
    elif overall == 3:
        score = rng.choices([7, 6, 5, 4], weights=[0.20, 0.40, 0.30, 0.10])[0]
    else:
        score = rng.choices([5, 4, 3, 2, 1, 0], weights=[0.20, 0.30, 0.25, 0.15, 0.05, 0.05])[0]

    group = "Promoter" if score >= 9 else ("Passive" if score >= 7 else "Detractor")
    return score, group


def _sample_positive_comment(rng: random.Random) -> str:
    pool = (
        POSITIVE_FACILITATOR
        + POSITIVE_PRACTICAL
        + POSITIVE_PACING
        + POSITIVE_RELEVANCE
        + POSITIVE_MATERIALS
        + POSITIVE_ENGAGEMENT
        + POSITIVE_EXAMPLES
        + POSITIVE_FACILITY
    )
    return rng.choice(pool)


def _sample_improvement_comment(rng: random.Random) -> str:
    pool = (
        IMPROVE_FACILITATOR
        + IMPROVE_PRACTICAL
        + IMPROVE_PACING
        + IMPROVE_RELEVANCE
        + IMPROVE_MATERIALS
        + IMPROVE_ENGAGEMENT
        + IMPROVE_EXAMPLES
        + IMPROVE_FACILITY
    )
    return rng.choice(pool)


def _sample_additional_comment(rng: random.Random, overall: int) -> str:
    if rng.random() < 0.04:
        return rng.choice(PII_COMMENTS)
    if overall >= 4:
        if rng.random() < 0.65:
            return rng.choice(POSITIVE_ENGAGEMENT + POSITIVE_EXAMPLES + POSITIVE_FACILITATOR + NEUTRAL_COMMENTS)
        return "I would definitely recommend this course to anyone in a leadership or management role."
    elif overall == 3:
        return rng.choice(NEUTRAL_COMMENTS + IMPROVE_PACING)
    else:
        return rng.choice(IMPROVE_PRACTICAL + IMPROVE_RELEVANCE + IMPROVE_EXAMPLES)


# ---------------------------------------------------------------------------
# Canonical Dataset Generator
# ---------------------------------------------------------------------------

def _require_positive_count(count: int, label: str = "Response count") -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(f"{label} must be a positive integer.")


def generate_canonical_responses(count: int = 5000, seed: int = 2026) -> pd.DataFrame:
    """Generate high-volume canonical dataset matching REQUIRED_COLUMNS."""
    _require_positive_count(count)
    rng = random.Random(seed)
    start_date = datetime(2024, 1, 15)
    rows = []

    # Course rating effects to reflect realistic curriculum variations
    effects = {
        "PACE-8325": 0.18, "PACE-8423": 0.22, "PACE-8457": 0.14, "PACE-8563": 0.10,
        "LF-101": 0.12, "LF-205": -0.16, "LF-310": 0.05, "LF-420": 0.16,
        "LF-515": -0.05, "LF-605": 0.08, "LF-710": 0.06,
    }

    for idx in range(count):
        course = CANONICAL_COURSES[idx % len(CANONICAL_COURSES)]
        code, name, mode, client, facilitator = course
        eff = effects.get(code, 0.0)

        overall = _sample_rating(rng, 4.12 + eff)
        content = _sample_rating(rng, 4.05 + eff)
        facil = _sample_rating(rng, 4.35 + eff)
        relevance = _sample_rating(rng, 4.10 + eff)

        nps_score, _ = _sample_nps(rng, overall)
        would_rec = "Yes" if nps_score >= 7 else "No"

        date = start_date + timedelta(days=rng.randrange(0, 950), hours=rng.randrange(8, 18), minutes=rng.randrange(0, 60))

        # Qualitative comments distribution
        # MostValuableAspect: ~85% populated
        valuable = _sample_positive_comment(rng) if rng.random() < 0.85 else ""
        # WhatCouldImprove: ~70% populated
        improve = _sample_improvement_comment(rng) if rng.random() < 0.70 else ""
        # AdditionalComments: ~50% populated (including PII cases)
        additional = _sample_additional_comment(rng, overall) if rng.random() < 0.50 else ""

        rows.append({
            "ResponseID": f"SYN-{seed}-{idx + 1:06d}",
            "RecordedDate": date.strftime("%Y-%m-%dT%H:%M:%S"),
            "CourseCode": code,
            "CourseName": name,
            "DeliveryMode": mode,
            "ClientType": client,
            "FacilitatorCode": facilitator,
            "OverallSatisfaction": overall,
            "ContentQuality": content,
            "FacilitatorEffectiveness": facil,
            "CourseRelevance": relevance,
            "WouldRecommend": would_rec,
            "MostValuableAspect": valuable,
            "WhatCouldImprove": improve,
            "AdditionalComments": additional,
        })

    # Ensure deterministic PII coverage at known indexes for test assertions
    pii_examples = {
        7: "Please contact me directly: sarah.jenkins@adelaide.edu.au or 0412 345 678.",
        23: "Call David on 0401 223 889 if you hold the future leadership focus session.",
        64: "Reference notes and handouts available at https://pace.adelaide.edu.au/resources.",
    }
    for index, comment in pii_examples.items():
        if index < count:
            rows[index]["AdditionalComments"] = comment

    df = pd.DataFrame(rows)
    return df[REQUIRED_COLUMNS]


# ---------------------------------------------------------------------------
# Authentic Qualtrics Course Export Generators (3-Header rows)
# ---------------------------------------------------------------------------

def _generate_qualtrics_table(
    h1: list[str],
    h2: list[str],
    h3: list[str],
    row_builder: Any,
    count: int,
    seed: int,
) -> list[list[Any]]:
    _require_positive_count(count)
    rng = random.Random(seed)
    table = [h1, h2, h3]
    for idx in range(count):
        table.append(row_builder(idx, rng))
    return table


def generate_qualtrics_8325_rows(count: int = 1000, seed: int = 8325) -> list[list[Any]]:
    """Course 8325: Leadership and Management Essentials (August 2023)."""
    h1 = [
        "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
        "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
        "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
        "DistributionChannel", "UserLanguage",
        "Q2_1", "Q2_2", "Q2_3", "Q2_4", "Q2_5",
        "Q3_NPS_GROUP", "Q3",
        "Q4_1", "Q4_2", "Q4_3", "Q4_4",
        "Q5", "Q7", "Q8", "Q9"
    ]
    h2 = [
        "Start Date", "End Date", "Response Type", "IP Address", "Progress", "Duration (in seconds)",
        "Finished", "Recorded Date", "Response ID", "Recipient Last Name", "Recipient First Name",
        "Recipient Email", "External Data Reference", "Location Latitude", "Location Longitude",
        "Distribution Channel", "User Language",
        "Course Feedback - Overall, I was satisfied with the course",
        "Course Feedback - Enrolling in the course was easy",
        "Course Feedback - The frequency and timing of communication from PACE was appropriate",
        "Course Feedback - I learned what I expected",
        "Course Feedback - I will apply what I've learnt in this course",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague? - Group",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague?",
        "Presenter Feedback - Overall, the presenter(s) were effective",
        "Presenter Feedback - The presenter(s) were knowledgeable of the content being delivered",
        "Presenter Feedback - The presenter(s) were able to provide helpful answers to questions asked",
        "Presenter Feedback - The course materials provided were useful",
        "Do you have any other feedback or suggestions for the presenters? If this is individual feedback, please make clear who you are providing feedback for in the comments.",
        "In this course, I really enjoyed:",
        "This course could be improved by:",
        "Overall, I would recommend:"
    ]
    h3 = [
        '{"ImportId":"startDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"endDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"status"}', '{"ImportId":"ipAddress"}', '{"ImportId":"progress"}',
        '{"ImportId":"duration"}', '{"ImportId":"finished"}',
        '{"ImportId":"recordedDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"_recordId"}', '{"ImportId":"recipientLastName"}',
        '{"ImportId":"recipientFirstName"}', '{"ImportId":"recipientEmail"}',
        '{"ImportId":"externalDataReference"}', '{"ImportId":"locationLatitude"}',
        '{"ImportId":"locationLongitude"}', '{"ImportId":"distributionChannel"}',
        '{"ImportId":"userLanguage"}',
        '{"ImportId":"QID2_13"}', '{"ImportId":"QID2_11"}', '{"ImportId":"QID2_12"}',
        '{"ImportId":"QID2_6"}', '{"ImportId":"QID2_9"}',
        '{"ImportId":"QID5_NPS_GROUP"}', '{"ImportId":"QID5"}',
        '{"ImportId":"QID8_1"}', '{"ImportId":"QID8_3"}', '{"ImportId":"QID8_5"}',
        '{"ImportId":"QID8_8"}',
        '{"ImportId":"QID31_TEXT"}', '{"ImportId":"QID26_TEXT"}', '{"ImportId":"QID28_TEXT"}',
        '{"ImportId":"QID27_TEXT"}'
    ]

    base_time = datetime(2023, 8, 10, 16, 6)

    def build_row(idx: int, rng: random.Random) -> list[Any]:
        is_finished = rng.random() > 0.04
        progress = 100 if is_finished else rng.choice([35, 50, 65, 80])
        dur = rng.randint(65, 450) if is_finished else rng.randint(25, 90)

        dt = base_time + timedelta(minutes=idx * 3 + rng.randint(0, 120))
        start_str = dt.strftime("%d/%m/%Y %H:%M")
        rec_str = (dt + timedelta(seconds=dur)).strftime("%d/%m/%Y %H:%M")

        rid = f"R_8325_{idx + 1:07d}_{rng.randint(100, 999)}"
        lat = round(-34.9281 + rng.uniform(-0.06, 0.06), 4)
        lon = round(138.5999 + rng.uniform(-0.06, 0.06), 4)

        if not is_finished and progress < 50:
            # Drop early incomplete response
            return [
                start_str, rec_str, "IP Address", "", str(progress), str(dur),
                "FALSE", rec_str, rid, "", "", "", "", str(lat), str(lon), "qr", "EN",
                "Strongly agree", "Strongly agree", "", "", "",
                "", "", "", "", "", "", "", "", "", ""
            ]

        overall = _sample_rating(rng, 4.25)
        nps, group = _sample_nps(rng, overall)

        q2_1 = _rating_to_likert(overall)
        q2_2 = _rating_to_likert(_sample_rating(rng, 4.30))
        q2_3 = _rating_to_likert(_sample_rating(rng, 4.20))
        q2_4 = _rating_to_likert(_sample_rating(rng, 4.15))
        q2_5 = _rating_to_likert(_sample_rating(rng, 4.30))

        q4_1 = _rating_to_likert(_sample_rating(rng, 4.45))
        q4_2 = _rating_to_likert(_sample_rating(rng, 4.50))
        q4_3 = _rating_to_likert(_sample_rating(rng, 4.40))
        q4_4 = _rating_to_likert(_sample_rating(rng, 4.10))

        # Qualitative comments
        q5 = rng.choice(POSITIVE_FACILITATOR + [""]) if rng.random() < 0.45 else ""
        q7 = _sample_positive_comment(rng) if rng.random() < 0.80 else ""
        q8 = _sample_improvement_comment(rng) if rng.random() < 0.70 else ""
        q9 = _sample_additional_comment(rng, overall) if rng.random() < 0.55 else ""

        return [
            start_str, rec_str, "IP Address", "", str(progress), str(dur),
            "TRUE" if is_finished else "FALSE", rec_str, rid, "", "", "", "",
            str(lat), str(lon), "qr", "EN",
            q2_1, q2_2, q2_3, q2_4, q2_5,
            group, str(nps),
            q4_1, q4_2, q4_3, q4_4,
            q5, q7, q8, q9
        ]

    return _generate_qualtrics_table(h1, h2, h3, build_row, count, seed)


def generate_qualtrics_8423_rows(count: int = 1000, seed: int = 8423) -> list[list[Any]]:
    """Course 8423: Finance for Non-Financial Managers (Nov 2024)."""
    h1 = [
        "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
        "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
        "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
        "DistributionChannel", "UserLanguage",
        "Q2_1", "Q2_2", "Q2_3", "Q2_4", "Q2_5",
        "Q3_1", "Q3_2", "Q3_3", "Q3_4",
        "Q4_NPS_GROUP", "Q4",
        "Q6", "Q6_11_TEXT", "Q7", "Q8", "Q9", "Q10", "Q11", "Q11_11_TEXT",
        "Q12", "Q12_12_TEXT", "Q13", "Q14", "Q15_4", "Q15_5", "Q16"
    ]
    h2 = [
        "Start Date", "End Date", "Response Type", "IP Address", "Progress", "Duration (in seconds)",
        "Finished", "Recorded Date", "Response ID", "Recipient Last Name", "Recipient First Name",
        "Recipient Email", "External Data Reference", "Location Latitude", "Location Longitude",
        "Distribution Channel", "User Language",
        "Course feedback - Overall, I was satisfied with the course",
        "Course feedback - Enrolling in the course was easy",
        "Course feedback - The frequency and timing of communication from PACE was appropriate",
        "Course feedback - I learned what I expected",
        "Course feedback - I will apply what I've learnt in this course",
        "Presenter feedback - Overall, the presenter(s) were effective",
        "Presenter feedback - The presenter(s) were knowledgeable of the content being delivered",
        "Presenter feedback - The presenter(s) were able to provide helpful answers to questions asked",
        "Presenter feedback - The course materials provided were useful",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague? - Group",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague?",
        "The aspects about studying with PACE that I enjoyed the most were: - Selected Choice",
        "The aspects about studying with PACE that I enjoyed the most were: - Other: - Text",
        "This course could be improved by:",
        "Overall, I would recommend:",
        "If you think others could benefit from learning with Professional and Continuing Education...",
        "We are committed to lifelong learning, and likely, you are too!...",
        "What subject areas would benefit you, and your career, into the future? - Selected Choice",
        "What subject areas would benefit you, and your career, into the future? - Other - Text",
        "What is the ideal course length for your future studies? - Selected Choice",
        "What is the ideal course length for your future studies? - Other - Text",
        "What is your attendance preference?",
        "In the past, we've had a wealth of success in holding informative focus groups...",
        "Name", "Email Address", "Focus groups can be held in person or online, what would be your preferred option?"
    ]
    h3 = [
        '{"ImportId":"startDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"endDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"status"}', '{"ImportId":"ipAddress"}', '{"ImportId":"progress"}',
        '{"ImportId":"duration"}', '{"ImportId":"finished"}',
        '{"ImportId":"recordedDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"_recordId"}', '{"ImportId":"recipientLastName"}',
        '{"ImportId":"recipientFirstName"}', '{"ImportId":"recipientEmail"}',
        '{"ImportId":"externalDataReference"}', '{"ImportId":"locationLatitude"}',
        '{"ImportId":"locationLongitude"}', '{"ImportId":"distributionChannel"}',
        '{"ImportId":"userLanguage"}',
        '{"ImportId":"QID2_13"}', '{"ImportId":"QID2_11"}', '{"ImportId":"QID2_12"}',
        '{"ImportId":"QID2_6"}', '{"ImportId":"QID2_9"}',
        '{"ImportId":"QID8_1"}', '{"ImportId":"QID8_3"}', '{"ImportId":"QID8_5"}', '{"ImportId":"QID8_8"}',
        '{"ImportId":"QID5_NPS_GROUP"}', '{"ImportId":"QID5"}',
        '{"ImportId":"QID12"}', '{"ImportId":"QID12_11_TEXT"}',
        '{"ImportId":"QID31_TEXT"}', '{"ImportId":"QID32_TEXT"}', '{"ImportId":"QID39_TEXT"}',
        '{"ImportId":"QID35"}', '{"ImportId":"QID25"}', '{"ImportId":"QID25_11_TEXT"}',
        '{"ImportId":"QID26"}', '{"ImportId":"QID26_12_TEXT"}', '{"ImportId":"QID27"}',
        '{"ImportId":"QID28"}', '{"ImportId":"QID30_4"}', '{"ImportId":"QID30_5"}', '{"ImportId":"QID37"}'
    ]

    base_time = datetime(2024, 11, 7, 14, 39)

    def build_row(idx: int, rng: random.Random) -> list[Any]:
        is_finished = rng.random() > 0.05
        progress = 100 if is_finished else rng.choice([40, 60, 75])
        dur = rng.randint(70, 380) if is_finished else rng.randint(30, 85)

        dt = base_time + timedelta(minutes=idx * 4 + rng.randint(0, 180))
        start_str = dt.strftime("%d/%m/%Y %H:%M")
        rec_str = (dt + timedelta(seconds=dur)).strftime("%d/%m/%Y %H:%M")

        rid = f"R_8423_{idx + 1:07d}_{rng.randint(100, 999)}"
        lat = round(-34.9281 + rng.uniform(-0.05, 0.05), 4)
        lon = round(138.5999 + rng.uniform(-0.05, 0.05), 4)

        overall = _sample_rating(rng, 4.30)
        nps, group = _sample_nps(rng, overall)

        q2_1 = _rating_to_likert(overall)
        q2_2 = _rating_to_likert(_sample_rating(rng, 4.35))
        q2_3 = _rating_to_likert(_sample_rating(rng, 4.25))
        q2_4 = _rating_to_likert(_sample_rating(rng, 4.20))
        q2_5 = _rating_to_likert(_sample_rating(rng, 4.35))

        q3_1 = _rating_to_likert(_sample_rating(rng, 4.50))
        q3_2 = _rating_to_likert(_sample_rating(rng, 4.55))
        q3_3 = _rating_to_likert(_sample_rating(rng, 4.45))
        q3_4 = _rating_to_likert(_sample_rating(rng, 4.15))

        q6_choices = "Relevance to my workplace and role,Developing my professional skills and capabilities,The {course/program} facilitator(s)"
        q6_other = _sample_positive_comment(rng) if rng.random() < 0.50 else ""
        q7 = _sample_improvement_comment(rng) if rng.random() < 0.70 else ""
        q8 = _sample_additional_comment(rng, overall) if rng.random() < 0.55 else ""

        # Marketing & focus group responses
        q9 = "learner.feedback@adelaide.edu.au" if rng.random() < 0.15 else ""
        q10 = "Yes" if rng.random() < 0.60 else "No"
        q11 = "Business Management,Leadership and Management"
        q12 = "1-2 days,3-5 days"
        q13 = rng.choice(["Face-to-face in Adelaide", "Online", "Any of the above"])
        q14 = rng.choice(["Yes", "Maybe", "No"])

        return [
            start_str, rec_str, "IP Address", "", str(progress), str(dur),
            "TRUE" if is_finished else "FALSE", rec_str, rid, "", "", "", "",
            str(lat), str(lon), "qr", "EN",
            q2_1, q2_2, q2_3, q2_4, q2_5,
            q3_1, q3_2, q3_3, q3_4,
            group, str(nps),
            q6_choices, q6_other, q7, q8, q9, q10, q11, "", q12, "", q13, q14, "", "", ""
        ]

    return _generate_qualtrics_table(h1, h2, h3, build_row, count, seed)


def generate_qualtrics_8457_rows(count: int = 1000, seed: int = 8457) -> list[list[Any]]:
    """Course 8457: From Team Member to Team Leader (July 2024)."""
    h1 = [
        "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
        "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
        "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
        "DistributionChannel", "UserLanguage",
        "Q2_1", "Q2_2", "Q2_3", "Q2_4", "Q2_5",
        "Q3_NPS_GROUP", "Q3",
        "Q4_1", "Q4_2", "Q4_3", "Q4_4",
        "Q6", "Q7", "Q8", "Q9", "Q10", "Q10_11_TEXT", "Q11", "Q11_12_TEXT",
        "Q12", "Q13", "Q14_4", "Q14_5", "Q15"
    ]
    h2 = [
        "Start Date", "End Date", "Response Type", "IP Address", "Progress", "Duration (in seconds)",
        "Finished", "Recorded Date", "Response ID", "Recipient Last Name", "Recipient First Name",
        "Recipient Email", "External Data Reference", "Location Latitude", "Location Longitude",
        "Distribution Channel", "User Language",
        "Course feedback - Overall, I was satisfied with the course",
        "Course feedback - Enrolling in the course was easy",
        "Course feedback - The frequency and timing of communication from PACE was appropriate",
        "Course feedback - I learned what I expected",
        "Course feedback - I will apply what I've learnt in this course",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague? - Group",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague?",
        "Presenter feedback - Overall, the presenter(s) were effective",
        "Presenter feedback - The presenter(s) were knowledgeable of the content being delivered",
        "Presenter feedback - The presenter(s) were able to provide helpful answers to questions asked",
        "Presenter feedback - The course materials provided were useful",
        "In this course, I really enjoyed:",
        "This course could be improved by:",
        "Overall, I would recommend:",
        "We are committed to lifelong learning, and likely, you are too!...",
        "What subject areas would benefit you, and your career, into the future? - Selected Choice",
        "What subject areas would benefit you, and your career, into the future? - Other - Text",
        "What is the ideal course length for your future studies? - Selected Choice",
        "What is the ideal course length for your future studies? - Other - Text",
        "What is your attendance preference?",
        "In the past, we've had a wealth of success in holding informative focus groups...",
        "Name", "Email Address", "Focus groups can be held in person or online, what would be your preferred option?"
    ]
    h3 = [
        '{"ImportId":"startDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"endDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"status"}', '{"ImportId":"ipAddress"}', '{"ImportId":"progress"}',
        '{"ImportId":"duration"}', '{"ImportId":"finished"}',
        '{"ImportId":"recordedDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"_recordId"}', '{"ImportId":"recipientLastName"}',
        '{"ImportId":"recipientFirstName"}', '{"ImportId":"recipientEmail"}',
        '{"ImportId":"externalDataReference"}', '{"ImportId":"locationLatitude"}',
        '{"ImportId":"locationLongitude"}', '{"ImportId":"distributionChannel"}',
        '{"ImportId":"userLanguage"}',
        '{"ImportId":"QID2_13"}', '{"ImportId":"QID2_11"}', '{"ImportId":"QID2_12"}',
        '{"ImportId":"QID2_6"}', '{"ImportId":"QID2_9"}',
        '{"ImportId":"QID5_NPS_GROUP"}', '{"ImportId":"QID5"}',
        '{"ImportId":"QID8_1"}', '{"ImportId":"QID8_3"}', '{"ImportId":"QID8_5"}', '{"ImportId":"QID8_8"}',
        '{"ImportId":"QID12_TEXT"}', '{"ImportId":"QID31_TEXT"}', '{"ImportId":"QID32_TEXT"}',
        '{"ImportId":"QID35"}', '{"ImportId":"QID25"}', '{"ImportId":"QID25_11_TEXT"}',
        '{"ImportId":"QID26"}', '{"ImportId":"QID26_12_TEXT"}', '{"ImportId":"QID27"}',
        '{"ImportId":"QID28"}', '{"ImportId":"QID30_4"}', '{"ImportId":"QID30_5"}', '{"ImportId":"QID37"}'
    ]

    base_time = datetime(2024, 7, 2, 16, 9)

    def build_row(idx: int, rng: random.Random) -> list[Any]:
        is_finished = rng.random() > 0.04
        progress = 100 if is_finished else rng.choice([45, 60, 75])
        dur = rng.randint(60, 320) if is_finished else rng.randint(25, 75)

        dt = base_time + timedelta(minutes=idx * 3 + rng.randint(0, 150))
        start_str = dt.strftime("%d/%m/%Y %H:%M")
        rec_str = (dt + timedelta(seconds=dur)).strftime("%d/%m/%Y %H:%M")

        rid = f"R_8457_{idx + 1:07d}_{rng.randint(100, 999)}"
        lat = round(-34.9281 + rng.uniform(-0.05, 0.05), 4)
        lon = round(138.5999 + rng.uniform(-0.05, 0.05), 4)

        overall = _sample_rating(rng, 4.20)
        nps, group = _sample_nps(rng, overall)

        q2_1 = _rating_to_likert(overall)
        q2_2 = _rating_to_likert(_sample_rating(rng, 4.25))
        q2_3 = _rating_to_likert(_sample_rating(rng, 4.15))
        q2_4 = _rating_to_likert(_sample_rating(rng, 4.20))
        q2_5 = _rating_to_likert(_sample_rating(rng, 4.30))

        q4_1 = _rating_to_likert(_sample_rating(rng, 4.40))
        q4_2 = _rating_to_likert(_sample_rating(rng, 4.45))
        q4_3 = _rating_to_likert(_sample_rating(rng, 4.35))
        q4_4 = _rating_to_likert(_sample_rating(rng, 4.10))

        q6 = _sample_positive_comment(rng) if rng.random() < 0.85 else ""
        q7 = _sample_improvement_comment(rng) if rng.random() < 0.70 else ""
        q8 = _sample_additional_comment(rng, overall) if rng.random() < 0.50 else ""

        q9 = "Yes" if rng.random() < 0.65 else "No"
        q10 = "Communication and Writing,Leadership and Management"
        q11 = "2-4 hours,1-2 days"
        q12 = "Face-to-face in Adelaide"
        q13 = "Maybe"

        return [
            start_str, rec_str, "IP Address", "", str(progress), str(dur),
            "TRUE" if is_finished else "FALSE", rec_str, rid, "", "", "", "",
            str(lat), str(lon), "qr", "EN",
            q2_1, q2_2, q2_3, q2_4, q2_5,
            group, str(nps),
            q4_1, q4_2, q4_3, q4_4,
            q6, q7, q8, q9, q10, "", q11, "", q12, q13, "", "", ""
        ]

    return _generate_qualtrics_table(h1, h2, h3, build_row, count, seed)


def generate_qualtrics_8563_rows(count: int = 1000, seed: int = 8563) -> list[list[Any]]:
    """Course 8563: Strategic Thinking (August 2025)."""
    h1 = [
        "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
        "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
        "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
        "DistributionChannel", "UserLanguage",
        "Q2_1", "Q2_2", "Q2_3", "Q2_4", "Q2_5",
        "Q3_1", "Q3_2", "Q3_3", "Q3_4",
        "Q4_NPS_GROUP", "Q4",
        "Q6", "Q6_11_TEXT", "Q7", "Q8", "Q9", "Q10", "Q11", "Q11_11_TEXT",
        "Q12", "Q12_12_TEXT", "Q13", "Q14", "Q14_4", "Q14_5", "Q15"
    ]
    h2 = [
        "Start Date", "End Date", "Response Type", "IP Address", "Progress", "Duration (in seconds)",
        "Finished", "Recorded Date", "Response ID", "Recipient Last Name", "Recipient First Name",
        "Recipient Email", "External Data Reference", "Location Latitude", "Location Longitude",
        "Distribution Channel", "User Language",
        "Course feedback - Overall, I was satisfied with the course",
        "Course feedback - Enrolling in the course was easy",
        "Course feedback - The frequency and timing of communication from PACE was appropriate",
        "Course feedback - I learned what I expected",
        "Course feedback - I will apply what I've learnt in this course",
        "Presenter feedback - Overall, the presenter(s) were effective",
        "Presenter feedback - The presenter(s) were knowledgeable of the content being delivered",
        "Presenter feedback - The presenter(s) were able to provide helpful answers to questions asked",
        "Presenter feedback - The course materials provided were useful",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague? - Group",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague?",
        "The aspects about studying with PACE that I enjoyed the most were: - Selected Choice",
        "The aspects about studying with PACE that I enjoyed the most were: - Other: - Text",
        "This course could be improved by:",
        "Overall, I would recommend:",
        "If you think others could benefit from learning with Professional and Continuing Education...",
        "We are committed to lifelong learning, and likely, you are too!...",
        "What subject areas would benefit you, and your career, into the future? - Selected Choice",
        "What subject areas would benefit you, and your career, into the future? - Other - Text",
        "What is the ideal course length for your future studies? - Selected Choice",
        "What is the ideal course length for your future studies? - Other - Text",
        "What is your attendance preference?",
        "In the past, we've had a wealth of success in holding informative focus groups...",
        "Name", "Email Address", "Focus groups can be held in person or online, what would be your preferred option?"
    ]
    h3 = [
        '{"ImportId":"startDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"endDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"status"}', '{"ImportId":"ipAddress"}', '{"ImportId":"progress"}',
        '{"ImportId":"duration"}', '{"ImportId":"finished"}',
        '{"ImportId":"recordedDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"_recordId"}', '{"ImportId":"recipientLastName"}',
        '{"ImportId":"recipientFirstName"}', '{"ImportId":"recipientEmail"}',
        '{"ImportId":"externalDataReference"}', '{"ImportId":"locationLatitude"}',
        '{"ImportId":"locationLongitude"}', '{"ImportId":"distributionChannel"}',
        '{"ImportId":"userLanguage"}',
        '{"ImportId":"QID2_13"}', '{"ImportId":"QID2_11"}', '{"ImportId":"QID2_12"}',
        '{"ImportId":"QID2_6"}', '{"ImportId":"QID2_9"}',
        '{"ImportId":"QID8_1"}', '{"ImportId":"QID8_3"}', '{"ImportId":"QID8_5"}', '{"ImportId":"QID8_8"}',
        '{"ImportId":"QID5_NPS_GROUP"}', '{"ImportId":"QID5"}',
        '{"ImportId":"QID12"}', '{"ImportId":"QID12_11_TEXT"}',
        '{"ImportId":"QID31_TEXT"}', '{"ImportId":"QID32_TEXT"}', '{"ImportId":"QID39_TEXT"}',
        '{"ImportId":"QID35"}', '{"ImportId":"QID25"}', '{"ImportId":"QID25_11_TEXT"}',
        '{"ImportId":"QID26"}', '{"ImportId":"QID26_12_TEXT"}', '{"ImportId":"QID27"}',
        '{"ImportId":"QID28"}', '{"ImportId":"QID30_4"}', '{"ImportId":"QID30_5"}', '{"ImportId":"QID37"}'
    ]

    base_time = datetime(2025, 8, 6, 15, 54)

    def build_row(idx: int, rng: random.Random) -> list[Any]:
        is_finished = rng.random() > 0.05
        progress = 100 if is_finished else rng.choice([35, 55, 70])
        dur = rng.randint(70, 360) if is_finished else rng.randint(20, 80)

        dt = base_time + timedelta(minutes=idx * 4 + rng.randint(0, 180))
        start_str = dt.strftime("%d/%m/%Y %H:%M")
        rec_str = (dt + timedelta(seconds=dur)).strftime("%d/%m/%Y %H:%M")

        rid = f"R_8563_{idx + 1:07d}_{rng.randint(100, 999)}"
        lat = round(-34.9282 + rng.uniform(-0.06, 0.06), 4)
        lon = round(138.5999 + rng.uniform(-0.06, 0.06), 4)

        overall = _sample_rating(rng, 4.15)
        nps, group = _sample_nps(rng, overall)

        q2_1 = _rating_to_likert(overall)
        q2_2 = _rating_to_likert(_sample_rating(rng, 4.20))
        q2_3 = _rating_to_likert(_sample_rating(rng, 4.15))
        q2_4 = _rating_to_likert(_sample_rating(rng, 4.15))
        q2_5 = _rating_to_likert(_sample_rating(rng, 4.25))

        q3_1 = _rating_to_likert(_sample_rating(rng, 4.40))
        q3_2 = _rating_to_likert(_sample_rating(rng, 4.45))
        q3_3 = _rating_to_likert(_sample_rating(rng, 4.35))
        q3_4 = _rating_to_likert(_sample_rating(rng, 4.10))

        q6_choices = "Relevance to my workplace and role,Networking with fellow participants,The {course/program} facilitator(s)"
        q6_other = _sample_positive_comment(rng) if rng.random() < 0.55 else ""
        q7 = _sample_improvement_comment(rng) if rng.random() < 0.70 else ""
        q8 = _sample_additional_comment(rng, overall) if rng.random() < 0.50 else ""

        return [
            start_str, rec_str, "IP Address", "", str(progress), str(dur),
            "TRUE" if is_finished else "FALSE", rec_str, rid, "", "", "", "",
            str(lat), str(lon), "qr", "EN",
            q2_1, q2_2, q2_3, q2_4, q2_5,
            q3_1, q3_2, q3_3, q3_4,
            group, str(nps),
            q6_choices, q6_other, q7, q8, "", "Yes", "Business Management", "", "1-2 days", "", "Any of the above", "Maybe", "", "", ""
        ]

    return _generate_qualtrics_table(h1, h2, h3, build_row, count, seed)


def generate_qualtrics_8184_rows(count: int = 1000, seed: int = 8184) -> list[list[Any]]:
    """Course 8184: Strategic Thinking (June 2023)."""
    h1 = [
        "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
        "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
        "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
        "DistributionChannel", "UserLanguage",
        "Q2_1", "Q2_2", "Q2_3", "Q2_4", "Q2_5",
        "Q3_NPS_GROUP", "Q3",
        "Q4_1", "Q4_2", "Q4_3", "Q4_4",
        "Q6", "Q7", "Q8", "Q9", "Q10", "Q10_11_TEXT", "Q11", "Q11_12_TEXT",
        "Q12", "Q13", "Q14_4", "Q14_5", "Q15"
    ]
    h2 = [
        "Start Date", "End Date", "Response Type", "IP Address", "Progress", "Duration (in seconds)",
        "Finished", "Recorded Date", "Response ID", "Recipient Last Name", "Recipient First Name",
        "Recipient Email", "External Data Reference", "Location Latitude", "Location Longitude",
        "Distribution Channel", "User Language",
        "Course feedback - Overall, I was satisfied with the course",
        "Course feedback - Enrolling in the course was easy",
        "Course feedback - The frequency and timing of communication from PACE was appropriate",
        "Course feedback - I learned what I expected",
        "Course feedback - I will apply what I've learnt in this course",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague? - Group",
        "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague?",
        "Presenter feedback - Overall, the presenter(s) were effective",
        "Presenter feedback - The presenter(s) were knowledgeable of the content being delivered",
        "Presenter feedback - The presenter(s) were able to provide helpful answers to questions asked",
        "Presenter feedback - The course materials provided were useful",
        "In this course, I really enjoyed:",
        "This course could be improved by:",
        "Overall, I would recommend:",
        "We are committed to lifelong learning, and likely, you are too!...",
        "What subject areas would benefit you, and your career, into the future? - Selected Choice",
        "What subject areas would benefit you, and your career, into the future? - Other - Text",
        "What is the ideal course length for your future studies? - Selected Choice",
        "What is the ideal course length for your future studies? - Other - Text",
        "What is your attendance preference?",
        "In the past, we've had a wealth of success in holding informative focus groups...",
        "Name", "Email Address", "Focus groups can be held in person or online, what would be your preferred option?"
    ]
    h3 = [
        '{"ImportId":"startDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"endDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"status"}', '{"ImportId":"ipAddress"}', '{"ImportId":"progress"}',
        '{"ImportId":"duration"}', '{"ImportId":"finished"}',
        '{"ImportId":"recordedDate","timeZone":"Australia/Adelaide"}',
        '{"ImportId":"_recordId"}', '{"ImportId":"recipientLastName"}',
        '{"ImportId":"recipientFirstName"}', '{"ImportId":"recipientEmail"}',
        '{"ImportId":"externalDataReference"}', '{"ImportId":"locationLatitude"}',
        '{"ImportId":"locationLongitude"}', '{"ImportId":"distributionChannel"}',
        '{"ImportId":"userLanguage"}',
        '{"ImportId":"QID2_13"}', '{"ImportId":"QID2_11"}', '{"ImportId":"QID2_12"}',
        '{"ImportId":"QID2_6"}', '{"ImportId":"QID2_9"}',
        '{"ImportId":"QID5_NPS_GROUP"}', '{"ImportId":"QID5"}',
        '{"ImportId":"QID8_1"}', '{"ImportId":"QID8_3"}', '{"ImportId":"QID8_5"}', '{"ImportId":"QID8_8"}',
        '{"ImportId":"QID12_TEXT"}', '{"ImportId":"QID31_TEXT"}', '{"ImportId":"QID32_TEXT"}',
        '{"ImportId":"QID35"}', '{"ImportId":"QID25"}', '{"ImportId":"QID25_11_TEXT"}',
        '{"ImportId":"QID26"}', '{"ImportId":"QID26_12_TEXT"}', '{"ImportId":"QID27"}',
        '{"ImportId":"QID28"}', '{"ImportId":"QID30_4"}', '{"ImportId":"QID30_5"}', '{"ImportId":"QID37"}'
    ]

    base_time = datetime(2023, 6, 16, 16, 2)

    def build_row(idx: int, rng: random.Random) -> list[Any]:
        is_finished = rng.random() > 0.04
        progress = 100 if is_finished else rng.choice([40, 60, 75])
        dur = rng.randint(60, 300) if is_finished else rng.randint(20, 80)

        dt = base_time + timedelta(minutes=idx * 3 + rng.randint(0, 160))
        start_str = dt.strftime("%d/%m/%Y %H:%M")
        rec_str = (dt + timedelta(seconds=dur)).strftime("%d/%m/%Y %H:%M")

        rid = f"R_8184_{idx + 1:07d}_{rng.randint(100, 999)}"
        lat = round(-34.9281 + rng.uniform(-0.05, 0.05), 4)
        lon = round(138.5999 + rng.uniform(-0.05, 0.05), 4)

        overall = _sample_rating(rng, 4.25)
        nps, group = _sample_nps(rng, overall)

        q2_1 = _rating_to_likert(overall)
        q2_2 = _rating_to_likert(_sample_rating(rng, 4.30))
        q2_3 = _rating_to_likert(_sample_rating(rng, 4.20))
        q2_4 = _rating_to_likert(_sample_rating(rng, 4.15))
        q2_5 = _rating_to_likert(_sample_rating(rng, 4.35))

        q4_1 = _rating_to_likert(_sample_rating(rng, 4.45))
        q4_2 = _rating_to_likert(_sample_rating(rng, 4.50))
        q4_3 = _rating_to_likert(_sample_rating(rng, 4.40))
        q4_4 = _rating_to_likert(_sample_rating(rng, 4.20))

        q6 = _sample_positive_comment(rng) if rng.random() < 0.85 else ""
        q7 = _sample_improvement_comment(rng) if rng.random() < 0.70 else ""
        q8 = _sample_additional_comment(rng, overall) if rng.random() < 0.50 else ""

        return [
            start_str, rec_str, "IP Address", "", str(progress), str(dur),
            "TRUE" if is_finished else "FALSE", rec_str, rid, "", "", "", "",
            str(lat), str(lon), "qr", "EN",
            q2_1, q2_2, q2_3, q2_4, q2_5,
            group, str(nps),
            q4_1, q4_2, q4_3, q4_4,
            q6, q7, q8, "Yes", "Leadership and Management", "", "1-2 days", "", "Face-to-face in Adelaide", "No", "", "", ""
        ]

    return _generate_qualtrics_table(h1, h2, h3, build_row, count, seed)


def write_qualtrics_table_to_csv(path: str | Path, table: list[list[Any]]) -> Path:
    """Save raw 3-header Qualtrics table to CSV with proper quoting."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_MINIMAL)
        for row in table:
            writer.writerow(row)
    return path


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def generate_all_test_datasets(
    canonical_count: int = 5000,
    qualtrics_course_count: int = 1000,
    seed: int = 2026,
    data_dir: Path | str | None = None,
    include_excel: bool = True,
    populate_client_folder: bool = True,
) -> dict[str, Path]:
    """Generate canonical and authentic Qualtrics datasets for end-to-end testing."""
    _require_positive_count(canonical_count, "Canonical response count")
    _require_positive_count(qualtrics_course_count, "Qualtrics response count")
    root = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data"
    root.mkdir(parents=True, exist_ok=True)

    exports_dir = root / "synthetic_qualtrics_exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    client_dir = root / "client"
    if populate_client_folder:
        client_dir.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}

    print(f"Generating Canonical dataset ({canonical_count:,} responses)...")
    canonical_df = generate_canonical_responses(canonical_count, seed=seed)

    # 1. Primary large canonical CSV
    large_csv = root / "synthetic_qualtrics_evaluation_large.csv"
    canonical_df.to_csv(large_csv, index=False)
    generated["canonical_large_csv"] = large_csv
    print(f"  -> Wrote: {large_csv.name} ({large_csv.stat().st_size / 1024:.1f} KB)")

    if include_excel:
        large_xlsx = root / "synthetic_qualtrics_evaluation_large.xlsx"
        write_dataframe_to_xlsx(large_xlsx, canonical_df)
        generated["canonical_large_xlsx"] = large_xlsx
        print(f"  -> Wrote: {large_xlsx.name} ({large_xlsx.stat().st_size / 1024:.1f} KB)")

    # 2. Standard demo canonical dataset (update/ensure 3,000 rows with high-quality themes & PII)
    demo_df = generate_canonical_responses(3000, seed=seed + 1)
    demo_csv = root / "synthetic_qualtrics_evaluation.csv"
    demo_df.to_csv(demo_csv, index=False)
    generated["canonical_demo_csv"] = demo_csv
    print(f"  -> Updated demo file: {demo_csv.name} (3,000 responses)")

    if include_excel:
        demo_xlsx = root / "synthetic_qualtrics_evaluation.xlsx"
        write_dataframe_to_xlsx(demo_xlsx, demo_df)
        generated["canonical_demo_xlsx"] = demo_xlsx
        print(f"  -> Wrote demo Excel: {demo_xlsx.name}")

    # 3. Authentic Qualtrics Course Exports (5 courses)
    course_factories = [
        ("8325+-+Leadership+and+Management+Essentials+-+August+2023_September+21,+2026_13.22", generate_qualtrics_8325_rows, seed + 10),
        ("8423+-+Finance+for+Non-Financial+Managers+-+Nov+2024_September+21,+2026_13.26", generate_qualtrics_8423_rows, seed + 20),
        ("8457+-+From+Team+Member+to+Team+Leader+-+July+2024_September+21,+2026_13.25", generate_qualtrics_8457_rows, seed + 30),
        ("8563+Strategic+Thinking+5+&+6+August+2025_September+21,+2026_13.31", generate_qualtrics_8563_rows, seed + 40),
        ("Strategic+Thinking+-+8184+-+15+&+16+June+2023_September+21,+2026_13.29", generate_qualtrics_8184_rows, seed + 50),
    ]

    total_qualtrics_responses = 0
    for name_stem, factory, c_seed in course_factories:
        print(f"Generating Qualtrics export: {name_stem} ({qualtrics_course_count:,} responses)...")
        table = factory(qualtrics_course_count, seed=c_seed)
        total_qualtrics_responses += qualtrics_course_count

        # Write to synthetic_qualtrics_exports/
        export_csv = exports_dir / f"{name_stem}.csv"
        write_qualtrics_table_to_csv(export_csv, table)
        generated[f"qualtrics_{name_stem}_csv"] = export_csv

        if include_excel:
            export_xlsx = exports_dir / f"{name_stem}.xlsx"
            write_dataframe_to_xlsx(export_xlsx, table)
            generated[f"qualtrics_{name_stem}_xlsx"] = export_xlsx

        # Also write/copy to data/client/ for folder-drop testing
        if populate_client_folder:
            client_csv = client_dir / f"{name_stem}.csv"
            write_qualtrics_table_to_csv(client_csv, table)
            if include_excel:
                client_xlsx = client_dir / f"{name_stem}.xlsx"
                write_dataframe_to_xlsx(client_xlsx, table)

        print(f"  -> Wrote CSV and XLSX for {name_stem}")

    print("\nSummary of generated synthetic data:")
    print(f"  - Large Canonical responses: {canonical_count:,} rows (CSV & XLSX)")
    print(f"  - Standard Canonical responses: 3,000 rows (CSV & XLSX)")
    print(f"  - Authentic Qualtrics exports: 5 courses, {total_qualtrics_responses:,} rows total")
    print(f"  - Location: {root}")
    print(f"  - Qualtrics folder: {exports_dir}")
    if populate_client_folder:
        print(f"  - Client drop folder: {client_dir}")

    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large synthetic survey datasets.")
    parser.add_argument("--canonical-count", type=int, default=5000, help="Responses for large canonical file (default 5000)")
    parser.add_argument("--qualtrics-count", type=int, default=1000, help="Responses per Qualtrics course file (default 1000)")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed for deterministic generation (default 2026)")
    parser.add_argument("--no-excel", action="store_true", help="Skip generating .xlsx versions")
    parser.add_argument("--no-client", action="store_true", help="Skip copying to data/client/ folder")
    args = parser.parse_args()

    generate_all_test_datasets(
        canonical_count=args.canonical_count,
        qualtrics_course_count=args.qualtrics_count,
        seed=args.seed,
        include_excel=not args.no_excel,
        populate_client_folder=not args.no_client,
    )


if __name__ == "__main__":
    main()
