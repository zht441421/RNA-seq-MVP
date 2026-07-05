import json

from tests.evidence_helpers import run_api_project


def test_audit_log_contains_inputs_methods_qc_run_status_and_reliability() -> None:
    result = run_api_project(run_mode="mock")
    audit_path = result["artifact_root"] / "10_audit_log.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    assert audit["project_id"] == result["project_id"]
    assert audit["omics_type"] == "bulk_rnaseq"
    assert audit["input_level"] == "count_matrix"
    assert audit["input_files"]["count_matrix"]["hash"]
    assert audit["input_files"]["count_matrix"]["rows"] > 0
    assert "gene_id" in audit["input_files"]["count_matrix"]["columns"]
    assert audit["input_files"]["metadata"]["hash"]
    assert audit["schema_mapping"]["gene_id_column"] == "gene_id"
    assert audit["methods"]["primary_method"] == "DESeq2"
    assert audit["qc"]["status"] == "pass"
    assert audit["run_status"]["status"] == "mock_completed"
    assert audit["reliability"]["grade"] == "C"
    assert audit["reliability"]["allowed_conclusion_level"] == "Exploratory findings only."

