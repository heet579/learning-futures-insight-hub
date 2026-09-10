from src.ai.base_provider import AIProvider
from src.models import AnalysisContext, ReportDraft

REQUIRED_HEADINGS = [
    "Course Information", "Executive Summary", "Participation Overview", "Key Metrics",
    "What Worked Well", "Key Themes", "Areas for Improvement", "Learner Feedback Summary",
    "Recommendations", "Evidence / Supporting Metrics", "AI / Automated Analysis Disclosure",
    "Human Review Status",
]

def _metric_lines(context: AnalysisContext) -> list[str]:
    lines = []
    for value in context.metrics["ratings"].values():
        if value["mean"] is not None:
            lines.append(f"- {value['label']}: {value['mean']:.2f}/5 (n={value['count']})")
    rec = context.metrics.get("recommendation_percent")
    if rec is not None:
        lines.append(f"- Would recommend: {rec:.1f}%")
    return lines

def generate_report(context: AnalysisContext, audience: str, provider: AIProvider) -> ReportDraft:
    if audience not in {"facilitator", "client"}:
        raise ValueError("Audience must be 'facilitator' or 'client'.")
    title = "Facilitator Evaluation Report" if audience == "facilitator" else "Course Evaluation Report for Client Review"
    positives = [t for t in context.themes if t.category == "Positive"]
    improvements = [t for t in context.themes if t.category == "Improvement"]
    theme_lines = [f"- **{t.name}** — {t.frequency} related comment(s); keywords: {', '.join(t.keywords)}" for t in context.themes]
    evidence = []
    for theme in context.themes[:4]:
        evidence.append(f"- {theme.name}: {theme.frequency} matching comment(s).")
        if audience == "facilitator" and theme.evidence:
            evidence.append(f"  - Representative feedback: “{theme.evidence[0]}”")
    recommendations = provider.recommendations(context, audience)
    role_focus = (
        "This internal coaching view focuses on teaching practice, learner engagement and delivery improvement."
        if audience == "facilitator" else
        "This client-facing view focuses on participant outcomes, relevance and value delivered; internal coaching detail is excluded."
    )
    disclosure = (
        "Generated in **Local Demonstration Mode** using calculated metrics, explainable theme rules/NMF and deterministic templates. No data was sent to an external AI service. This is not Microsoft Copilot."
        if provider.name == "Local Demonstration Mode" else
        "Generated using the explicitly selected **Approved External Provider** from minimised calculated metrics and theme metadata. Masked source comments are not included in the provider payload. This Azure OpenAI adapter is not Microsoft Copilot or Copilot Studio. Human verification remains mandatory."
    )
    content = f"""# {title}

**Status: DRAFT — REQUIRES HUMAN REVIEW**

## Course Information

- Course: {context.course_name}
- Source: {context.source_name}
- Audience: {audience.title()}

## Executive Summary

{provider.executive_summary(context, audience)}

## Participation Overview

{context.metrics['response_count']} response(s) were analysed with {context.metrics['response_completeness']:.1f}% field completeness.

## Key Metrics

{chr(10).join(_metric_lines(context)) or '- Insufficient valid rating data.'}

## What Worked Well

{chr(10).join(f'- {t.name}: {t.frequency} related comment(s).' for t in positives) or '- No sufficiently recurring positive theme was identified.'}

## Key Themes

{chr(10).join(theme_lines) or '- Insufficient qualitative evidence for theme extraction.'}

## Areas for Improvement

{chr(10).join(f'- {t.name}: review {t.frequency} related comment(s).' for t in improvements) or '- No recurring improvement theme met the current rule-based threshold.'}

## Learner Feedback Summary

{role_focus} Automated categories are indicators, not ground truth; reviewers should inspect the evidence.

## Recommendations

{chr(10).join(f'- {item}' for item in recommendations)}

## Evidence / Supporting Metrics

{chr(10).join(evidence) or '- Quantitative metrics above are the available supporting evidence.'}

## AI / Automated Analysis Disclosure

{disclosure}

## Human Review Status

**DRAFT — REQUIRES HUMAN REVIEW**. Recommendations are advisory. A staff member must verify, edit and approve this report before it is treated as final.
"""
    return ReportDraft(audience=audience, content=content, mode=provider.name)

def approve_report(report: ReportDraft, content: str | None = None) -> ReportDraft:
    final = content if content is not None else report.content
    final = final.replace("DRAFT — REQUIRES HUMAN REVIEW", "HUMAN REVIEWED")
    return ReportDraft(report.audience, final, "HUMAN REVIEWED", report.mode)
