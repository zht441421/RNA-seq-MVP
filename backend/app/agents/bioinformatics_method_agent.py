from typing import Dict

from backend.app.models.analysis_plan import AnalysisPlan


class BioinformaticsMethodAgent:
    name = "bioinformatics_method_agent"

    def summarize(self, plan: AnalysisPlan) -> Dict[str, object]:
        return {
            "primary_method": plan.primary_method,
            "validation_methods": plan.validation_methods,
            "normalization": plan.normalization,
            "requires_user_confirmation": plan.requires_user_confirmation,
            "note": "Methods are placeholders until real R/Bioconductor runners are connected.",
        }

