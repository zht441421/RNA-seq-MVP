from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.qc_report import QCReport
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.services.plan_service import create_recommended_plan


class PlannerAgent:
    name = "planner_agent"

    def run(self, config: BulkRNASeqAnalysisConfig, qc_report: QCReport = None) -> AnalysisPlan:
        return create_recommended_plan(config=config, qc_report=qc_report)

