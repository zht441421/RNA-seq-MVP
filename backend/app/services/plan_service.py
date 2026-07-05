from typing import List

from backend.app.config import get_settings
from backend.app.models.analysis_plan import AnalysisPlan, LowCountFilteringRule
from backend.app.models.qc_report import QCReport
from backend.app.models.schemas import BulkRNASeqAnalysisConfig


def create_recommended_plan(config: BulkRNASeqAnalysisConfig, qc_report: QCReport = None) -> AnalysisPlan:
    notes: List[str] = [
        "Primary method is a placeholder for future R/Bioconductor DESeq2 execution.",
        "Validation methods are placeholders until real edgeR and limma-voom runners are connected.",
        "User confirmation is required before execution.",
    ]
    if qc_report and not qc_report.passed:
        notes.append("QC contains blocking issues. Analysis should not proceed until they are resolved.")

    design_terms = [config.group_column]
    if config.batch_column:
        design_terms.insert(0, config.batch_column)
    design_terms.extend(config.covariates)
    design_formula = "~ " + " + ".join(dict.fromkeys(design_terms))

    return AnalysisPlan(
        project_id=config.project_id,
        primary_method="DESeq2",
        validation_methods=config.validation_methods or ["edgeR", "limma_voom"],
        normalization="DESeq2_size_factor",
        design_formula=design_formula,
        fdr_threshold=config.fdr_threshold,
        log2fc_threshold=config.log2fc_threshold,
        low_count_filtering=LowCountFilteringRule(
            min_total_count=get_settings().low_count_min_total,
            min_samples=2,
        ),
        enrichment=None,
        requires_user_confirmation=True,
        confirmed=False,
        notes=notes,
    )

