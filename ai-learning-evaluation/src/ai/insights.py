"""Calculated evidence for insights; no file names, comments or learned keywords."""
from src.analytics.themes import THEME_RULES
from src.models import AnalysisContext


def insight_evidence(context: AnalysisContext) -> dict[str, str]:
    m = context.metrics
    facts = {"responses": f"{m['response_count']} survey responses in the selected scope."}
    for key, rating in m["ratings"].items():
        if rating["mean"] is not None:
            distribution = ", ".join(f"{score}/5: {count}" for score, count in rating['distribution'].items())
            facts[key] = (f"{rating['label']}: mean {rating['mean']:.2f}/5; "
                          f"{rating['count']} valid answers; rating counts ({distribution}).")
    if m.get("recommendation_percent") is not None:
        facts["recommendation"] = (
            f"Recommendation indicator: {m['recommendation_percent']:.1f}% of recognised answers. "
            "For mapped Qualtrics exports, this means a recommendation score of 7 or above, not NPS.")
    for theme in context.themes:
        # Only fixed vocabulary can leave the device. NMF keywords can contain names.
        if theme.name in THEME_RULES and theme.category in {"Positive", "Improvement", "Review"}:
            facts[f"theme:{theme.name}"] = (
                f"{theme.name}: {theme.frequency} matching comments; heuristic category {theme.category}. "
                "Comments and themes may overlap; counts are not unique learners.")
    facts["limitations"] = (
        "Survey answers describe respondent perceptions, not proven learning or business outcomes. "
        "No enrolment denominator is available for a response rate. Missing answers are excluded from rating means. "
        f"There are {len(context.warnings)} source validation warnings; inspect the local data quality panel. "
        "Theme categories are heuristic; inspect local comments before interpreting sentiment. "
        "No causal or statistically significant differences have been established."
    )
    if m["response_count"] < 30:
        facts["small_sample"] = "Fewer than 30 responses: treat patterns as tentative and validate in later cohorts."
    return facts


def local_insights(context: AnalysisContext) -> str:
    facts = insight_evidence(context)
    lines = ["# Local insights", "Calculated locally; no external AI request."]
    lines.extend(["", "## Suggested next steps"])
    ratings = context.metrics["ratings"]
    lowest = context.metrics.get("lowest_area")
    if lowest:
        lines.append(f"- Review {ratings[lowest]['label'].lower()} with the facilitator; it has the lowest mean rating in this scope. Inspect comments before deciding on a change.")
    improvements = [t for t in context.themes if t.category == "Improvement" and t.name in THEME_RULES]
    for theme in improvements[:3]:
        lines.append(f"- Review feedback about {theme.name.lower()}, agree one delivery change and check the same theme after the next cohort.")
    if not lowest and not improvements:
        lines.append("- Collect more rating and comment evidence before choosing a delivery change.")
    lines.extend(["", "## Evidence"])
    lines.extend(f"- {value}" for key, value in facts.items() if key not in {"limitations", "small_sample"})
    lines.extend(["", "## Limitations", facts["limitations"], facts.get("small_sample", ""),
                  "", "Select Generate insights for interpretation and tailored suggestions."])
    return "\n".join(lines)


def render_insights(result: dict, context: AnalysisContext, model: str) -> str:
    facts = insight_evidence(context)
    lines = ["# Insights", "Draft interpretation; human review required.", result["summary"]]
    for item in result["insights"]:
        lines.extend([f"\n## {item['title']}", item["finding"], f"Suggested action: {item['suggestion']}", "Supporting calculated evidence:"])
        lines.extend(f"- {facts[key]}" for key in item["evidence_ids"])
    lines.extend(["\n## Limitations", facts["limitations"], facts.get("small_sample", "")])
    lines.extend(f"- {value}" for value in result["limitations"])
    return "\n".join(lines)
