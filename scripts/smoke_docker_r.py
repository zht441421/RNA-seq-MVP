import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


def request(base_url: str, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {method} {path}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the docker_r Bulk RNA-seq API smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    env = request(base_url, "GET", "/system/docker-r-env")
    if not env.get("ready_for_docker_r"):
        print("docker_r environment is not ready; smoke test skipped.")
        print(f"Docker available: {env.get('docker_available')}")
        print(f"Image available: {env.get('image_available')}")
        print(f"Image name: {env.get('image_name')}")
        print(f"Missing required: {env.get('missing_required', [])}")
        print(f"Errors: {env.get('errors', [])}")
        return 0

    project = request(base_url, "POST", "/projects", {"name": "docker_r small smoke test"})
    project_id = project["project_id"]
    print(f"Project: {project_id}")

    files = {
        "count_matrix_file": "examples/real_small_count_matrix.csv",
        "metadata_file": "examples/real_small_metadata.csv",
    }
    request(base_url, "POST", f"/projects/{project_id}/files", files)
    request(base_url, "POST", f"/projects/{project_id}/inspect", {})

    config = {
        "project_id": project_id,
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "count_matrix_file": "examples/real_small_count_matrix.csv",
        "metadata_file": "examples/real_small_metadata.csv",
        "sample_id_column": "sample_id",
        "gene_id_column": "gene_id",
        "group_column": "condition",
        "reference_group": "control",
        "test_group": "treatment",
        "batch_column": None,
        "covariates": [],
        "organism": "simulated",
        "gene_id_type": "symbol",
        "annotation_version": "simulated",
        "fdr_threshold": 0.05,
        "log2fc_threshold": 1.0,
        "validation_methods": ["edgeR", "limma_voom"],
    }

    qc = request(base_url, "POST", f"/projects/{project_id}/qc", config)
    if not qc.get("passed"):
        raise RuntimeError(f"QC failed unexpectedly: {qc}")

    plan = request(base_url, "POST", f"/projects/{project_id}/plan", config)
    request(base_url, "POST", f"/projects/{project_id}/confirm-plan", {"plan_id": plan["plan_id"], "confirmed": True})
    run = request(base_url, "POST", f"/projects/{project_id}/run", {"plan_id": plan["plan_id"]})
    status = request(base_url, "GET", f"/projects/{project_id}/status")
    results = request(base_url, "GET", f"/projects/{project_id}/results")
    manifest = request(base_url, "GET", f"/projects/{project_id}/artifacts")

    execution_mode = results.get("result_summary", {}).get("execution_mode")
    if execution_mode != "docker_r":
        raise RuntimeError(
            f"Backend did not run docker_r mode. Got execution_mode={execution_mode!r}. "
            "Restart the API with RUN_MODE=docker_r."
        )

    statuses = {entry["relative_path"]: entry["status"] for entry in manifest.get("files", [])}
    for relative_path in [
        "09_environment/run_status.json",
        "04_main_results/deseq2_results.csv",
        "09_environment/r_session_info.txt",
        "10_audit_log.json",
        "11_reliability_report.md",
        "manifest.json",
    ]:
        if statuses.get(relative_path) != "present":
            raise RuntimeError(f"Expected artifact is not present: {relative_path}")

    print(f"Final status: {status.get('status')}")
    print(f"Reliability grade: {results.get('reliability', {}).get('grade')}")
    print(f"Manifest: {Path(manifest['artifact_root']) / 'manifest.json'}")
    print("Artifacts:")
    for entry in manifest.get("files", []):
        if entry.get("status") == "present":
            print(f"- {entry['relative_path']}")

    return 0 if run.get("status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())

