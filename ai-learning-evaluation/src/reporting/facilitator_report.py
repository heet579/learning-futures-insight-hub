from src.ai.base_provider import AIProvider
from src.models import AnalysisContext, ReportDraft
from .report_generator import generate_report

def create_facilitator_report(context: AnalysisContext, provider: AIProvider) -> ReportDraft:
    return generate_report(context, "facilitator", provider)

