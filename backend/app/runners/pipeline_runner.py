from typing import Dict

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.qc_report import QCReport
from backend.app.models.schemas import BulkRNASeqAnalysisConfig


class MockPipelineRunner:
    """MVP runner that produces auditable mock outputs without scientific claims."""

    def run(
        self,
        config: BulkRNASeqAnalysisConfig,
        plan: AnalysisPlan,
        qc_report: QCReport,
    ) -> Dict[str, object]:
        return {
            "mode": "mock",
            "project_id": config.project_id,
            "status": "mock_completed",
            "primary_method": plan.primary_method,
            "primary_result": {
                "status": "mock_completed",
                "differential_expression_table": None,
                "note": "No real DESeq2 result was generated.",
            },
            "validation_status": {
                "mode": "mock",
                "methods": plan.validation_methods,
                "concordant_methods": [],
                "discordant_methods": [],
                "note": "Validation concordance is unavailable in the mock runner.",
            },
            "qc_passed": qc_report.passed,
        }

