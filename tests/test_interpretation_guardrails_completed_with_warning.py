import json
from pathlib import Path

from backend.app.services.artifact_service import STORE
from backend.app.services.result_interpretation import (
    FORBIDDEN_AUTOINTERPRETATION_TERMS,
    METHOD_WARNING,
    build_result_interpretation,
)
from tests.test_report_includes_real_run_warnings import setup_completed_with_warning_project


def test_completed_with_warning_guardrails_block_strong_interpretation() -> None:
    fixture = setup_completed_with_warning_project()
    project_id = fixture["project_id"]
    artifact_root = Path("artifacts") / project_id
    interpretation = build_result_interpretation(
        project_id=project_id,
        reliability=STORE.reliability[project_id],
        result_summary=STORE.results[project_id],
        artifact_root=artifact_root,
    )

    assert interpretation["strong_conclusion_allowed"] is False
    assert METHOD_WARNING in interpretation["guardrails"]
    assert "Top candidate statistical signals" in (artifact_root / "12_interpretation_summary.md").read_text(encoding="utf-8")

    conclusion_fields = {
        "guardrails": interpretation["guardrails"],
        "top_genes_label": interpretation["top_genes_label"],
        "top_gene_labels": [gene["interpretation_label"] for gene in interpretation["top_genes"]],
    }
    serialized = json.dumps(conclusion_fields, ensure_ascii=False)
    for forbidden in FORBIDDEN_AUTOINTERPRETATION_TERMS:
        assert forbidden not in serialized

