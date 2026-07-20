from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from backend.app.contracts.coze_tools import build_coze_tool_manifest
from backend.app.main import app
from backend.app.services import formal_de_preflight
from backend.app.services.reference_validation import validate_tool_openapi_compatibility
from scripts import probe_phase_8_6_1_r_deseq2_runtime as runtime_probe
from scripts.verify_phase_8_5_protected_staging import verify_structure as verify_phase_8_5
from scripts.verify_phase_8_6_reference_dataset_validation import verify_structure as verify_phase_8_6
from scripts.verify_phase_8_6_1_containerized_r_deseq2_runtime import verify_structure


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/runtime/r-deseq2-runtime.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _query_output(*, deseq2: str = "1.38.3") -> str:
    versions = {
        "DESeq2": deseq2,
        "SummarizedExperiment": "1.28.0",
        "S4Vectors": "0.36.1",
        "IRanges": "2.32.0",
        "BiocGenerics": "0.44.0",
        "BiocManager": "1.30.20",
        "BiocVersion": "3.16.0",
    }
    lines = ["BIOCONDUCTOR\t3.16"]
    lines.extend(f"PACKAGE\t{name}\t{version}" for name, version in versions.items())
    lines.extend(("LIBRARY\t/usr/lib/R/library", "LIBRARY\t/usr/lib/R/site-library"))
    lines.append("IDENTITY\t10001\t10001")
    return "\n".join(lines) + "\n"


def _patch_probe(monkeypatch: pytest.MonkeyPatch, *, deseq2: str = "1.38.3") -> None:
    monkeypatch.setattr(runtime_probe.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(args: list[str]):
        if args[0] == "R":
            return subprocess.CompletedProcess(args, 0, 'R version 4.2.2 Patched\n', '')
        if "--version" in args:
            return subprocess.CompletedProcess(args, 0, '', 'Rscript (R) version 4.2.2 Patched\n')
        return subprocess.CompletedProcess(args, 0, _query_output(deseq2=deseq2), '')

    monkeypatch.setattr(runtime_probe, "run_command", fake_run)
    monkeypatch.setattr(runtime_probe, "_directory_writable", lambda path, create=False: True)
    monkeypatch.setattr(runtime_probe.os, "access", lambda path, mode: False)
    monkeypatch.setattr(runtime_probe.os, "getuid", lambda: 10001, raising=False)
    monkeypatch.setattr(runtime_probe.os, "getgid", lambda: 10001, raising=False)


def test_runtime_manifest_schema_and_versions_are_frozen() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == "1.0"
    assert manifest["base_image_digest"].startswith("sha256:")
    assert manifest["python_version"] == "3.12.10"
    assert manifest["r_version"] == manifest["rscript_version"] == "4.2.2"
    assert manifest["bioconductor_version"] == "3.16"
    assert manifest["deseq2_version"] == "1.38.3"
    assert manifest["required_packages"]
    assert all(word not in json.dumps(manifest).lower() for word in ('"latest"', '"devel"', '"rolling"'))


def test_dockerfile_installs_and_load_verifies_fixed_runtime_at_build_time() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("FROM python:3.12.10-slim-bookworm@sha256:")
    assert "snapshot.debian.org" in text
    assert '"r-base-core=${R_BASE_CORE_VERSION}"' in text
    assert '"r-bioc-deseq2=${DESEQ2_DEBIAN_VERSION}"' in text
    assert "library(pkg, character.only=TRUE)" in text
    assert "Bioconductor version mismatch" in text
    assert "USER 10001:10001" in text
    assert "install.packages" not in text
    assert "BiocManager::install" not in text


def test_startup_and_task_execution_do_not_install_packages() -> None:
    startup = (ROOT / "deploy/staging/start-app.sh").read_text(encoding="utf-8").lower()
    execution = (ROOT / "backend/app/services/deseq2_execution.py").read_text(encoding="utf-8")
    assert all(term not in startup for term in ("apt-get", "install.packages", "biocmanager::install"))
    assert all(term not in execution.lower() for term in ("install.packages", "biocmanager::install", "shell=true"))
    assert "working_directory=output_dir" in execution
    assert "timeout_seconds=_DESEQ2_TIMEOUT_SECONDS" in execution


def test_staging_security_and_reference_mount_are_preserved() -> None:
    compose = (ROOT / "docker-compose.staging.yml").read_text(encoding="utf-8")
    override = (ROOT / "deploy/staging/phase-8-6.compose.yml").read_text(encoding="utf-8")
    for value in ('user: "10001:10001"', "read_only: true", "cap_drop:", "- ALL", "no-new-privileges:true"):
        assert value in compose
    assert '"127.0.0.1:8443:8443"' in compose
    assert "8000:8000" not in compose
    assert "BIOINFO_REQUIRE_API_KEY: \"true\"" in compose
    assert ".reference-data/prepared:/var/lib/bioinfo/reference-data:ro" in override


def test_runtime_probe_json_contract_reports_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probe(monkeypatch)
    result = runtime_probe.probe_runtime()
    assert result["ready"] is True
    assert result["identity"] == {
        "uid": 10001,
        "gid": 10001,
        "rscript_uid": 10001,
        "rscript_gid": 10001,
    }
    assert result["checks"]["rscript_identity_matches_application"] is True
    assert result["checks"]["application_source_writable"] is False
    assert result["checks"]["r_libraries_writable"] is False
    assert result["checks"]["task_workspace_writable"] is True
    assert result["checks"]["package_installation_attempted"] is False
    json.dumps(result, allow_nan=False)


def test_runtime_probe_rejects_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probe(monkeypatch, deseq2="9.9.9")
    result = runtime_probe.probe_runtime()
    assert result["ready"] is False
    assert result["required_package_checks"]["DESeq2"]["matches"] is False


def test_runtime_probe_reports_missing_r_and_rscript(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_probe.shutil, "which", lambda name: None)
    monkeypatch.setattr(runtime_probe, "_directory_writable", lambda path, create=False: True)
    monkeypatch.setattr(runtime_probe.os, "access", lambda path, mode: False)
    result = runtime_probe.probe_runtime()
    assert result["ready"] is False
    assert result["executables"] == {"R": None, "Rscript": None}


def test_enhanced_preflight_requires_dependencies_controlled_probe_and_writable_dirs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOINFO_R_RUNTIME_MANIFEST", raising=False)
    monkeypatch.setattr(formal_de_preflight, "check_executable_available", lambda name: True)
    monkeypatch.setattr(formal_de_preflight, "run_command_safely", lambda args, timeout_seconds=10, working_directory=None: formal_de_preflight.CommandResult(args=args, returncode=0, stdout="R version 4.2.2"))
    monkeypatch.setattr(formal_de_preflight, "check_r_package_available", lambda package: True)
    monkeypatch.setattr(formal_de_preflight, "check_controlled_runtime_script", lambda: (True, {}))
    monkeypatch.setattr(formal_de_preflight, "check_runtime_directories_writable", lambda: True)
    result = formal_de_preflight.run_deseq2_preflight()
    assert result["ready"] is True
    monkeypatch.setattr(formal_de_preflight, "check_runtime_directories_writable", lambda: False)
    assert formal_de_preflight.run_deseq2_preflight()["ready"] is False


def test_preflight_rejects_required_dependency_and_controlled_load_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOINFO_R_RUNTIME_MANIFEST", raising=False)
    monkeypatch.setattr(formal_de_preflight, "check_executable_available", lambda name: True)
    monkeypatch.setattr(formal_de_preflight, "run_command_safely", lambda args, timeout_seconds=10, working_directory=None: formal_de_preflight.CommandResult(args=args, returncode=0, stdout="R version 4.2.2"))
    monkeypatch.setattr(formal_de_preflight, "check_r_package_available", lambda package: package != "IRanges")
    monkeypatch.setattr(formal_de_preflight, "check_controlled_runtime_script", lambda: (False, {}))
    monkeypatch.setattr(formal_de_preflight, "check_runtime_directories_writable", lambda: True)
    result = formal_de_preflight.run_deseq2_preflight()
    assert result["ready"] is False
    assert any("dependency" in error.lower() for error in result["errors"])
    assert any("controlled" in error.lower() for error in result["errors"])


def test_subprocess_is_list_based_shell_false_timed_and_task_scoped() -> None:
    preflight_source = (ROOT / "backend/app/services/formal_de_preflight.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "backend/app/services/deseq2_execution.py").read_text(encoding="utf-8")
    assert "shell=False" in preflight_source
    assert "subprocess.TimeoutExpired" in preflight_source
    assert "working_directory=output_dir" in execution_source
    assert '["Rscript", "--vanilla"' in preflight_source
    assert "user-supplied" not in (ROOT / "backend/app/scripts/r/deseq2_runtime_preflight.R").read_text(encoding="utf-8").lower()


def test_api_operation_auth_request_audit_and_artifact_regression_gates_remain_valid() -> None:
    tools = build_coze_tool_manifest()
    assert validate_tool_openapi_compatibility(tools, app.openapi()) == []
    assert verify_phase_8_5() == []
    assert verify_phase_8_6() == []


def test_phase_8_6_golden_results_are_unchanged() -> None:
    expected = {
        "phase-8-6-pasilla-public-v1.json": "4e0a5f6cdca786d952fbfbb33b7d75581178a72f2df85b40832aad81700b1237",
        "phase-8-6-gse60450-luminal-public-v1.json": "b8a7f40c74859112ecfcda88d1f31c7bc195627839775df43cc9ed67a0f4d7a9",
    }
    root = ROOT / "docs/reference-datasets/golden-results"
    for name, digest in expected.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_phase_8_6_1_offline_structure_gate_passes() -> None:
    assert verify_structure() == []
