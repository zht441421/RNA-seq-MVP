from typing import Dict

from backend.app.models.analysis_plan import AnalysisPlan
from backend.app.models.schemas import BulkRNASeqAnalysisConfig


class RRunner:
    """Placeholder for future R/Bioconductor execution."""

    def run_differential_expression(
        self,
        config: BulkRNASeqAnalysisConfig,
        plan: AnalysisPlan,
    ) -> Dict[str, object]:
        return {
            "mode": "mock",
            "primary_method": plan.primary_method,
            "validation_methods": plan.validation_methods,
            "status": "not_executed",
            "note": "R/Bioconductor execution is not connected in Phase 1.",
        }

