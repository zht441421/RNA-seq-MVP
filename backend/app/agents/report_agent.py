from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.qc_report import QCReport
from backend.app.models.reliability import ReliabilityAssessment
from backend.app.reports.markdown_report import build_markdown_report


class ReportAgent:
    name = "report_agent"

    def build(self, plan: AnalysisPlan, qc_report: QCReport, reliability: ReliabilityAssessment) -> str:
        return build_markdown_report(plan=plan, qc_report=qc_report, reliability=reliability)

