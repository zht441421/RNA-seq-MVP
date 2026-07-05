from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app


def default_config(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "count_matrix_file": "examples/sample_count_matrix.csv",
        "metadata_file": "examples/sample_metadata.csv",
        "sample_id_column": "sample_id",
        "gene_id_column": "gene_id",
        "group_column": "group",
        "reference_group": "control",
        "test_group": "treatment",
        "batch_column": "batch",
        "covariates": ["age"],
        "organism": "human",
        "gene_id_type": "symbol",
        "annotation_version": "mock",
        "fdr_threshold": 0.05,
        "log2fc_threshold": 1.0,
        "validation_methods": ["edgeR", "limma_voom"],
    }


def run_api_project(run_mode: str = "mock", rscript_executable: str = "Rscript") -> Dict[str, Any]:
    settings = get_settings()
    settings.run_mode = run_mode
    settings.rscript_executable = rscript_executable
    client = TestClient(app)
    project = client.post("/projects", json={"name": f"{run_mode} evidence test"}).json()
    project_id = project["project_id"]
    client.post(
        f"/projects/{project_id}/files",
        json={
            "count_matrix_file": "examples/sample_count_matrix.csv",
            "metadata_file": "examples/sample_metadata.csv",
        },
    ).raise_for_status()
    client.post(f"/projects/{project_id}/inspect", json={}).raise_for_status()
    config = default_config(project_id)
    client.post(f"/projects/{project_id}/qc", json=config).raise_for_status()
    plan = client.post(f"/projects/{project_id}/plan", json=config).json()
    client.post(
        f"/projects/{project_id}/confirm-plan",
        json={"plan_id": plan["plan_id"], "confirmed": True},
    ).raise_for_status()
    run_response = client.post(f"/projects/{project_id}/run", json={"plan_id": plan["plan_id"]})
    run_response.raise_for_status()
    manifest = client.get(f"/projects/{project_id}/artifacts").json()
    return {
        "client": client,
        "project_id": project_id,
        "run": run_response.json(),
        "manifest": manifest,
        "artifact_root": Path(manifest["artifact_root"]),
    }


def manifest_entry(manifest: Dict[str, Any], relative_path: str) -> Dict[str, Any]:
    for entry in manifest["files"]:
        if entry["relative_path"] == relative_path:
            return entry
    raise AssertionError(f"Manifest entry not found: {relative_path}")

