from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.schemas import BulkRNASeqAnalysisConfig
from backend.app.services.qc_service import run_qc


def issue_codes(report) -> set[str]:
    return {issue.code for issue in report.validation_issues}


def test_qc_reports_structured_input_validation_issues(tmp_path: Path) -> None:
    count_matrix = tmp_path / "counts.csv"
    metadata = tmp_path / "metadata.csv"
    count_matrix.write_text(
        "\n".join(
            [
                "gene_id,S1,S2,S3",
                "GeneA,1,2,3",
                "GeneA,NA,4,5",
                "GeneB,bad,-1,2.5",
                "GeneZero,0,0,0",
                "GeneZero2,0,0,0",
                "GeneZero3,0,0,0",
                "GeneZero4,0,0,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    metadata.write_text(
        "\n".join(
            [
                "sample_id,group",
                "S1,control",
                "S1,control",
                "S4,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = BulkRNASeqAnalysisConfig(
        project_id="proj_validation_issues",
        count_matrix_file=str(count_matrix),
        metadata_file=str(metadata),
        sample_id_column="sample_id",
        gene_id_column="gene_id",
        group_column="group",
        reference_group="control",
        test_group="treatment",
    )

    report = run_qc(config)

    codes = issue_codes(report)
    assert report.passed is False
    assert "SAMPLE_ID_MISMATCH" in codes
    assert "DUPLICATE_SAMPLE_IDS" in codes
    assert "GROUP_VALUES_MISSING" in codes
    assert "GROUP_COUNT_TOO_LOW" in codes
    assert "TEST_GROUP_MISSING" in codes
    assert "COUNT_VALUES_MISSING" in codes
    assert "COUNT_VALUES_NON_NUMERIC" in codes
    assert "COUNT_VALUES_NEGATIVE" in codes
    assert "COUNT_VALUES_NON_INTEGER" in codes
    assert "DUPLICATE_GENE_IDS" in codes
    assert "ALL_ZERO_GENE_FRACTION_HIGH" in codes
    assert all(issue.suggestion for issue in report.validation_issues)


def test_count_matrix_without_sample_columns_is_error(tmp_path: Path) -> None:
    count_matrix = tmp_path / "counts.csv"
    metadata = tmp_path / "metadata.csv"
    count_matrix.write_text("gene_id\nGeneA\n", encoding="utf-8")
    metadata.write_text("sample_id,group\nS1,control\nS2,treatment\n", encoding="utf-8")
    config = BulkRNASeqAnalysisConfig(
        project_id="proj_no_samples",
        count_matrix_file=str(count_matrix),
        metadata_file=str(metadata),
        sample_id_column="sample_id",
        gene_id_column="gene_id",
        group_column="group",
        reference_group="control",
        test_group="treatment",
    )

    report = run_qc(config)

    assert report.passed is False
    assert "COUNT_MATRIX_NO_SAMPLE_COLUMNS" in issue_codes(report)


def test_coze_inspect_returns_structured_issue_for_missing_file() -> None:
    client = TestClient(app)
    project = client.post("/coze/projects", json={"project_name": "missing file test"}).json()

    response = client.post(
        f"/coze/projects/{project['project_id']}/inspect",
        json={
            "count_matrix_path": "examples/does_not_exist.csv",
            "metadata_path": "examples/sample_metadata.csv",
        },
    )

    assert response.status_code == 400
    issues = response.json()["detail"]["validation_issues"]
    assert issues[0]["code"] == "INPUT_FILE_UNREADABLE"
    assert issues[0]["suggestion"]


def test_qc_error_blocks_run(tmp_path: Path) -> None:
    client = TestClient(app)
    project = client.post("/projects", json={"name": "blocked run test"}).json()
    project_id = project["project_id"]
    count_matrix = tmp_path / "counts.csv"
    metadata = tmp_path / "metadata.csv"
    count_matrix.write_text("gene_id,S1\nGeneA,1\n", encoding="utf-8")
    metadata.write_text("sample_id,group\nS2,treatment\n", encoding="utf-8")
    config = {
        "project_id": project_id,
        "count_matrix_file": str(count_matrix),
        "metadata_file": str(metadata),
        "sample_id_column": "sample_id",
        "gene_id_column": "gene_id",
        "group_column": "group",
        "reference_group": "control",
        "test_group": "treatment",
    }

    qc_response = client.post(f"/projects/{project_id}/qc", json=config)
    plan_response = client.post(f"/projects/{project_id}/plan", json=config)
    plan_id = plan_response.json()["plan_id"]
    client.post(f"/projects/{project_id}/confirm-plan", json={"plan_id": plan_id, "confirmed": True})
    run_response = client.post(f"/projects/{project_id}/run", json={"plan_id": plan_id})

    assert qc_response.json()["passed"] is False
    assert qc_response.json()["validation_issues"]
    assert run_response.status_code == 400
    assert "QC has blocking issues" in run_response.json()["detail"]
