import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REQUIRED_REPORT_KEYS = [
    "timestamp",
    "git_commit",
    "base_url",
    "run_modes_tested",
    "pytest_summary",
    "docker_r_availability",
    "docker_image",
    "smoke_project_ids",
    "final_statuses",
    "reliability_grades",
    "key_artifacts_present",
    "validation_issues_smoke_result",
    "replay_dry_run_result",
    "export_package",
    "ui_route",
    "warnings",
    "failures",
    "overall_status",
]

DOCKER_KEY_ARTIFACTS = [
    "04_main_results/deseq2_results.csv",
    "05_validation_results/validation_comparison.csv",
    "08_reproducible_code/README_REPRODUCE.md",
    "08_reproducible_code/analysis_config.json",
    "08_reproducible_code/input_hashes.json",
    "08_reproducible_code/software_versions.json",
    "09_environment/run_status.json",
    "09_environment/r_session_info.txt",
    "10_audit_log.json",
    "11_reliability_report.md",
    "12_interpretation_summary.md",
    "manifest.json",
]

EXPORT_KEY_FILES = [
    "EXPORT_MANIFEST.json",
    "manifest.json",
    "12_interpretation_summary.md",
    "08_reproducible_code/README_REPRODUCE.md",
    "08_reproducible_code/analysis_config.json",
    "08_reproducible_code/input_hashes.json",
    "08_reproducible_code/software_versions.json",
]


class AcceptanceHttpError(RuntimeError):
    def __init__(self, status_code: int, method: str, path: str, body: str) -> None:
        super().__init__(f"HTTP {status_code} for {method} {path}: {body}")
        self.status_code = status_code
        self.method = method
        self.path = path
        self.body = body

    def json_body(self) -> Dict[str, Any]:
        try:
            return json.loads(self.body)
        except json.JSONDecodeError:
            return {"raw": self.body}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 1 end-to-end acceptance checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    base_url = args.base_url.rstrip("/")
    timestamp = utc_timestamp()
    report = new_acceptance_report(base_url=base_url, timestamp=timestamp, git_commit=git_commit(repo_root))

    run_acceptance(base_url=base_url, repo_root=repo_root, timestamp=timestamp, report=report)
    finalize_report_status(report)
    json_path, md_path = write_acceptance_reports(repo_root, timestamp, report)

    print(f"Acceptance JSON: {json_path}")
    print(f"Acceptance Markdown: {md_path}")
    print(f"Overall status: {report['overall_status']}")
    if report["failures"]:
        print("Failures:")
        for failure in report["failures"]:
            print(f"- {failure}")
    if report["warnings"]:
        print("Warnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")
    return 1 if report["overall_status"] == "failed" else 0


def run_acceptance(base_url: str, repo_root: Path, timestamp: str, report: Dict[str, Any]) -> None:
    health_check(base_url, report)
    docker_ready = docker_env_check(base_url, report)
    mock_smoke(base_url, report)
    docker_project_id = docker_r_smoke(base_url, report) if docker_ready else None
    bad_input_smoke(base_url, repo_root, timestamp, report)
    ui_route_check(base_url, report)

    if docker_project_id:
        report_results_check(base_url, docker_project_id, report)
        reproducibility_bundle_check(base_url, docker_project_id, report)
        replay_dry_run_check(repo_root, docker_project_id, report)
        export_package_check(base_url, docker_project_id, report)
    else:
        report["warnings"].append("docker_r dependent checks were skipped because docker_r is not ready.")
        report["replay_dry_run_result"] = {"status": "skipped", "reason": "docker_r smoke skipped"}
        report["export_package"] = {"status": "skipped", "reason": "docker_r smoke skipped"}


def new_acceptance_report(base_url: str, timestamp: str, git_commit: Optional[str]) -> Dict[str, Any]:
    return {
        "timestamp": timestamp,
        "git_commit": git_commit,
        "base_url": base_url,
        "run_modes_tested": [],
        "pytest_summary": "not_run",
        "docker_r_availability": {},
        "docker_image": None,
        "smoke_project_ids": {},
        "final_statuses": {},
        "reliability_grades": {},
        "key_artifacts_present": {},
        "validation_issues_smoke_result": {},
        "replay_dry_run_result": {},
        "export_package": {},
        "ui_route": {},
        "steps": [],
        "warnings": [],
        "failures": [],
        "overall_status": "not_run",
    }


def validate_acceptance_report_schema(report: Dict[str, Any]) -> List[str]:
    return [key for key in REQUIRED_REPORT_KEYS if key not in report]


def health_check(base_url: str, report: Dict[str, Any]) -> None:
    try:
        payload = request_json(base_url, "GET", "/health")
        ok = payload.get("status") == "ok"
        add_step(report, "system_health", "passed" if ok else "failed", payload)
        if not ok:
            report["failures"].append(f"System health returned unexpected payload: {payload}")
    except Exception as exc:
        add_step(report, "system_health", "failed", {"error": str(exc)})
        report["failures"].append(f"System health check failed: {exc}")


def docker_env_check(base_url: str, report: Dict[str, Any]) -> bool:
    try:
        env = request_json(base_url, "GET", "/system/docker-r-env")
        ready = bool(env.get("ready_for_docker_r"))
        report["docker_r_availability"] = env
        report["docker_image"] = env.get("image_name")
        add_step(report, "docker_r_environment", "passed" if ready else "skipped", env)
        if not ready:
            report["warnings"].append(
                "docker_r environment is not ready; docker_r smoke, replay, and export checks are skipped."
            )
        return ready
    except Exception as exc:
        report["docker_r_availability"] = {"ready_for_docker_r": False, "error": str(exc)}
        add_step(report, "docker_r_environment", "skipped", {"error": str(exc)})
        report["warnings"].append(f"docker_r environment check failed and was skipped: {exc}")
        return False


def mock_smoke(base_url: str, report: Dict[str, Any]) -> None:
    try:
        result = run_coze_project(base_url, run_mode="mock", name="Phase 1 acceptance mock smoke")
        project_id = result["project_id"]
        report["run_modes_tested"].append("mock")
        report["smoke_project_ids"]["mock"] = project_id
        report["final_statuses"]["mock"] = result["status"].get("status")
        report["reliability_grades"]["mock"] = result["run"].get("reliability_grade")
        add_step(report, "mock_smoke", "passed", _smoke_step_details(result))
    except Exception as exc:
        add_step(report, "mock_smoke", "failed", {"error": str(exc)})
        report["failures"].append(f"mock smoke failed: {exc}")


def docker_r_smoke(base_url: str, report: Dict[str, Any]) -> Optional[str]:
    try:
        result = run_coze_project(base_url, run_mode="docker_r", name="Phase 1 acceptance docker_r smoke")
        project_id = result["project_id"]
        manifest_statuses = artifact_statuses(result["manifest"])
        missing = [path for path in DOCKER_KEY_ARTIFACTS if manifest_statuses.get(path) != "present"]
        report["run_modes_tested"].append("docker_r")
        report["smoke_project_ids"]["docker_r"] = project_id
        report["final_statuses"]["docker_r"] = result["status"].get("status")
        report["reliability_grades"]["docker_r"] = result["run"].get("reliability_grade")
        report["key_artifacts_present"][project_id] = {
            path: manifest_statuses.get(path) == "present" for path in DOCKER_KEY_ARTIFACTS
        }
        if missing:
            raise RuntimeError(f"docker_r key artifacts missing: {missing}")
        if result["run"].get("run_status") != "completed":
            raise RuntimeError(f"docker_r run did not complete: {result['run']}")
        add_step(report, "docker_r_smoke", "passed", _smoke_step_details(result))
        return project_id
    except Exception as exc:
        add_step(report, "docker_r_smoke", "failed", {"error": str(exc)})
        report["failures"].append(f"docker_r smoke failed: {exc}")
        return None


def bad_input_smoke(base_url: str, repo_root: Path, timestamp: str, report: Dict[str, Any]) -> None:
    try:
        bad_dir = repo_root / "acceptance_reports" / f"bad_inputs_{timestamp}"
        count_matrix, metadata = build_bad_input_files(bad_dir)
        project = request_json(base_url, "POST", "/projects", {"name": "Phase 1 acceptance bad input smoke"})
        project_id = project["project_id"]
        report["smoke_project_ids"]["bad_input"] = project_id
        request_json(
            base_url,
            "POST",
            f"/projects/{project_id}/files",
            {"count_matrix_file": str(count_matrix), "metadata_file": str(metadata)},
        )
        request_json(base_url, "POST", f"/projects/{project_id}/inspect", {})
        config = bad_input_config(project_id, count_matrix, metadata)
        qc = request_json(base_url, "POST", f"/projects/{project_id}/qc", config)
        plan = request_json(base_url, "POST", f"/projects/{project_id}/plan", config)
        request_json(base_url, "POST", f"/projects/{project_id}/confirm-plan", {"plan_id": plan["plan_id"], "confirmed": True})
        run_error = None
        try:
            request_json(base_url, "POST", f"/projects/{project_id}/run", {"plan_id": plan["plan_id"]})
        except AcceptanceHttpError as exc:
            run_error = exc
        results = request_json(base_url, "GET", f"/projects/{project_id}/results")
        smoke_result = summarize_bad_input_smoke(qc=qc, run_error=run_error, results=results)
        report["validation_issues_smoke_result"] = smoke_result
        if not bad_input_smoke_passed(smoke_result):
            raise RuntimeError(f"Bad input smoke did not satisfy acceptance criteria: {smoke_result}")
        add_step(report, "bad_input_validation_smoke", "passed", smoke_result)
    except Exception as exc:
        add_step(report, "bad_input_validation_smoke", "failed", {"error": str(exc)})
        report["failures"].append(f"bad input smoke failed: {exc}")


def report_results_check(base_url: str, project_id: str, report: Dict[str, Any]) -> None:
    try:
        results = request_json(base_url, "GET", f"/projects/{project_id}/results")
        coze_report = request_json(base_url, "GET", f"/coze/projects/{project_id}/report")
        ok = bool(results.get("interpretation_summary")) and bool(coze_report.get("interpretation_summary"))
        details = {
            "results_reliability_grade": results.get("reliability_grade"),
            "coze_reliability_grade": coze_report.get("reliability_grade"),
            "primary_method_status": results.get("primary_method_status"),
            "strong_conclusion_allowed": results.get("strong_conclusion_allowed"),
            "interpretation_summary_present": ok,
        }
        add_step(report, "report_results_check", "passed" if ok else "failed", details)
        if not ok:
            report["failures"].append("results/report interpretation summary is missing.")
    except Exception as exc:
        add_step(report, "report_results_check", "failed", {"error": str(exc)})
        report["failures"].append(f"report/results check failed: {exc}")


def reproducibility_bundle_check(base_url: str, project_id: str, report: Dict[str, Any]) -> None:
    try:
        manifest = request_json(base_url, "GET", f"/projects/{project_id}/artifacts")
        statuses = artifact_statuses(manifest)
        repro_files = [
            "08_reproducible_code/README_REPRODUCE.md",
            "08_reproducible_code/analysis_config.json",
            "08_reproducible_code/run_command.txt",
            "08_reproducible_code/docker_command.txt",
            "08_reproducible_code/input_hashes.json",
            "08_reproducible_code/software_versions.json",
        ]
        present = {path: statuses.get(path) == "present" for path in repro_files}
        ok = all(present.values())
        add_step(report, "reproducibility_bundle_check", "passed" if ok else "failed", present)
        if not ok:
            report["failures"].append(f"Reproducibility bundle files missing: {[k for k, v in present.items() if not v]}")
    except Exception as exc:
        add_step(report, "reproducibility_bundle_check", "failed", {"error": str(exc)})
        report["failures"].append(f"reproducibility bundle check failed: {exc}")


def replay_dry_run_check(repo_root: Path, project_id: str, report: Dict[str, Any]) -> None:
    artifact_arg = str(repo_root / "artifacts" / project_id)
    command = [sys.executable, "scripts/replay_from_artifact.py", artifact_arg]
    completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=False)
    result = {
        "status": "passed" if completed.returncode == 0 and "Dry run only" in completed.stdout else "failed",
        "returncode": completed.returncode,
        "command": " ".join(command),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    report["replay_dry_run_result"] = result
    add_step(report, "replay_dry_run_check", result["status"], result)
    if result["status"] != "passed":
        report["failures"].append("Replay dry-run did not complete successfully.")


def export_package_check(base_url: str, project_id: str, report: Dict[str, Any]) -> None:
    try:
        created = request_json(base_url, "POST", f"/projects/{project_id}/export")
        metadata = request_json(base_url, "GET", f"/projects/{project_id}/export")
        zip_path = Path(created["export_package_path"])
        zip_entries = zip_file_entries(zip_path) if zip_path.exists() else []
        missing = [path for path in EXPORT_KEY_FILES if path not in zip_entries]
        result = {
            **metadata,
            "created_status": created.get("status"),
            "zip_path_exists": zip_path.exists(),
            "zip_contains_required_files": not missing,
            "missing_zip_files": missing,
        }
        report["export_package"] = result
        ok = (
            created.get("status") == "created"
            and metadata.get("status") == "available"
            and zip_path.exists()
            and bool(metadata.get("export_package_sha256"))
            and metadata.get("included_file_count", 0) > 0
            and not missing
        )
        add_step(report, "export_package_check", "passed" if ok else "failed", result)
        if not ok:
            report["failures"].append(f"Export package check failed: {result}")
    except Exception as exc:
        add_step(report, "export_package_check", "failed", {"error": str(exc)})
        report["failures"].append(f"export package check failed: {exc}")


def ui_route_check(base_url: str, report: Dict[str, Any]) -> None:
    try:
        html = request_text(base_url, "GET", "/ui")
        result = {
            "status_code": 200,
            "contains_workflow_title": "Bulk RNA-seq Mock Workflow" in html,
            "contains_export_package": "Export Package" in html,
            "contains_result_interpretation": "Result Interpretation" in html,
        }
        ok = all(value for key, value in result.items() if key != "status_code")
        report["ui_route"] = result
        add_step(report, "ui_route_check", "passed" if ok else "failed", result)
        if not ok:
            report["failures"].append(f"UI route content check failed: {result}")
    except Exception as exc:
        report["ui_route"] = {"status_code": None, "error": str(exc)}
        add_step(report, "ui_route_check", "failed", {"error": str(exc)})
        report["failures"].append(f"UI route check failed: {exc}")


def run_coze_project(base_url: str, run_mode: str, name: str) -> Dict[str, Any]:
    project = request_json(
        base_url,
        "POST",
        "/coze/projects",
        {
            "project_name": name,
            "omics_type": "bulk_rnaseq",
            "input_level": "count_matrix",
            "organism": "simulated",
            "gene_id_type": "symbol",
            "annotation_version": "simulated",
        },
    )
    project_id = project["project_id"]
    request_json(
        base_url,
        "POST",
        f"/coze/projects/{project_id}/inspect",
        {
            "count_matrix_path": "examples/real_small_count_matrix.csv",
            "metadata_path": "examples/real_small_metadata.csv",
        },
    )
    request_json(
        base_url,
        "POST",
        f"/coze/projects/{project_id}/prepare-analysis",
        {
            "gene_id_column": "gene_id",
            "sample_id_column": "sample_id",
            "group_column": "condition",
            "reference_group": "control",
            "test_group": "treatment",
            "batch_column": None,
            "covariates": [],
            "fdr_threshold": 0.05,
            "log2fc_threshold": 1.0,
            "run_enrichment": False,
        },
    )
    run = request_json(
        base_url,
        "POST",
        f"/coze/projects/{project_id}/confirm-and-run",
        {"confirmed": True, "run_mode": run_mode, "analysis_plan_overrides": {}},
    )
    status = request_json(base_url, "GET", f"/coze/projects/{project_id}/status")
    report = request_json(base_url, "GET", f"/coze/projects/{project_id}/report")
    results = request_json(base_url, "GET", f"/projects/{project_id}/results")
    manifest = request_json(base_url, "GET", f"/projects/{project_id}/artifacts")
    return {
        "project_id": project_id,
        "run": run,
        "status": status,
        "report": report,
        "results": results,
        "manifest": manifest,
    }


def build_bad_input_files(directory: Path) -> Tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    count_matrix = directory / "bad_count_matrix.csv"
    metadata = directory / "bad_metadata.csv"
    count_matrix.write_text(
        "\n".join(
            [
                "gene_id,S1,S2",
                "GeneA,10,-1",
                "GeneB,5,6",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    metadata.write_text(
        "\n".join(
            [
                "sample_id,condition",
                "S1,control",
                "S3,treatment",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return count_matrix, metadata


def bad_input_config(project_id: str, count_matrix: Path, metadata: Path) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "omics_type": "bulk_rnaseq",
        "input_level": "count_matrix",
        "count_matrix_file": str(count_matrix),
        "metadata_file": str(metadata),
        "sample_id_column": "sample_id",
        "gene_id_column": "gene_id",
        "group_column": "condition",
        "reference_group": "control",
        "test_group": "treatment",
        "batch_column": None,
        "covariates": [],
        "organism": "simulated",
        "gene_id_type": "symbol",
        "annotation_version": "acceptance_bad_input",
        "fdr_threshold": 0.05,
        "log2fc_threshold": 1.0,
        "validation_methods": ["edgeR", "limma_voom"],
    }


def summarize_bad_input_smoke(
    qc: Dict[str, Any],
    run_error: Optional[AcceptanceHttpError],
    results: Dict[str, Any],
) -> Dict[str, Any]:
    issues = qc.get("validation_issues") or []
    codes = sorted({issue.get("code") for issue in issues if issue.get("code")})
    return {
        "qc_passed": qc.get("passed"),
        "validation_issue_codes": codes,
        "structured_validation_issues_returned": bool(issues),
        "run_blocked": run_error is not None and run_error.status_code == 400,
        "run_error_status_code": run_error.status_code if run_error else None,
        "run_error_body": run_error.json_body() if run_error else None,
        "reliability_grade": (results.get("reliability") or {}).get("grade") or results.get("reliability_grade"),
        "strong_conclusion_allowed": bool(results.get("strong_conclusion_allowed")),
    }


def bad_input_smoke_passed(result: Dict[str, Any]) -> bool:
    required_codes = {"SAMPLE_ID_MISMATCH", "COUNT_VALUES_NEGATIVE"}
    codes = set(result.get("validation_issue_codes") or [])
    return (
        result.get("qc_passed") is False
        and result.get("structured_validation_issues_returned") is True
        and result.get("run_blocked") is True
        and required_codes.issubset(codes)
        and result.get("strong_conclusion_allowed") is False
    )


def request_json(
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    text = request_text(base_url, method, path, payload, timeout=timeout)
    return json.loads(text) if text else {}


def request_text(
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 300,
) -> str:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AcceptanceHttpError(exc.code, method, path, body) from exc


def artifact_statuses(manifest: Dict[str, Any]) -> Dict[str, str]:
    return {
        entry.get("relative_path"): entry.get("status")
        for entry in manifest.get("files", [])
        if entry.get("relative_path")
    }


def zip_file_entries(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()


def _smoke_step_details(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "project_id": result["project_id"],
        "run_status": result["run"].get("run_status"),
        "status": result["status"].get("status"),
        "reliability_grade": result["run"].get("reliability_grade"),
        "strong_conclusion_allowed": result["report"].get("strong_conclusion_allowed"),
    }


def add_step(report: Dict[str, Any], name: str, status: str, details: Dict[str, Any]) -> None:
    report.setdefault("steps", []).append({"name": name, "status": status, "details": details})


def finalize_report_status(report: Dict[str, Any]) -> None:
    if report["failures"]:
        report["overall_status"] = "failed"
    elif report["warnings"] or any(step.get("status") == "skipped" for step in report.get("steps", [])):
        report["overall_status"] = "passed_with_warnings"
    else:
        report["overall_status"] = "passed"


def write_acceptance_reports(repo_root: Path, timestamp: str, report: Dict[str, Any]) -> Tuple[Path, Path]:
    output_dir = repo_root / "acceptance_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"phase_1_acceptance_{timestamp}.json"
    md_path = output_dir / f"phase_1_acceptance_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    md_path.write_text(markdown_summary(report), encoding="utf-8")
    return json_path, md_path


def markdown_summary(report: Dict[str, Any]) -> str:
    lines = [
        "# Phase 1 Acceptance Report",
        "",
        f"- Timestamp: {report.get('timestamp')}",
        f"- Git commit: {report.get('git_commit') or 'unavailable'}",
        f"- Base URL: {report.get('base_url')}",
        f"- Overall status: {report.get('overall_status')}",
        f"- Pytest summary: {report.get('pytest_summary')}",
        f"- Run modes tested: {', '.join(report.get('run_modes_tested') or []) or 'none'}",
        f"- Docker image: {report.get('docker_image') or 'unavailable'}",
        "",
        "## Smoke Projects",
        "",
    ]
    for label, project_id in (report.get("smoke_project_ids") or {}).items():
        lines.append(f"- {label}: {project_id}")
    lines.extend(["", "## Final Statuses", ""])
    for label, status in (report.get("final_statuses") or {}).items():
        lines.append(f"- {label}: {status}")
    lines.extend(["", "## Reliability Grades", ""])
    for label, grade in (report.get("reliability_grades") or {}).items():
        lines.append(f"- {label}: {grade}")
    lines.extend(["", "## Steps", ""])
    for step in report.get("steps", []):
        lines.append(f"- {step.get('name')}: {step.get('status')}")
    lines.extend(["", "## Export Package", ""])
    export = report.get("export_package") or {}
    lines.append(f"- Status: {export.get('status') or export.get('created_status') or 'not_run'}")
    lines.append(f"- Path: {export.get('export_package_path') or 'unavailable'}")
    lines.append(f"- SHA256: {export.get('export_package_sha256') or 'unavailable'}")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in report.get("warnings", [])] or ["- None"])
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in report.get("failures", [])] or ["- None"])
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This acceptance report verifies workflow execution and artifact packaging. It does not upgrade reliability grade or permit strong scientific conclusions.",
            "",
        ]
    )
    return "\n".join(lines)


def git_commit(repo_root: Path) -> Optional[str]:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
