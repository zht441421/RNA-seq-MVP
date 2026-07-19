from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DOC = ROOT / "docs/reference-datasets/README.md"
MANIFEST_PATH = ROOT / "docs/reference-datasets/reference-dataset-manifest.json"
GOLDEN_ROOT = ROOT / "docs/reference-datasets/golden-results"
PHASE_DOC = ROOT / "docs/phase-8-4-reference-dataset-deployment-readiness.md"
ENV_EXAMPLE = ROOT / "docs/examples/deployment/phase-8-4.env.example"
PLUGIN_PACKAGE = ROOT / "docs/deployment/phase-8-4-coze-plugin-package.json"
COZE_MANIFEST = ROOT / "docs/coze-tool-manifest.json"
WINDOWS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def main() -> int:
    run_tests = "--skip-tests" not in sys.argv[1:]
    failures = verify_readiness()
    if not failures and run_tests:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=False
        )
        if completed.returncode != 0:
            failures.append("full pytest suite failed")
    if failures:
        print("Phase 8.4 reference dataset readiness verification failed")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Phase 8.4 reference dataset readiness verified")
    return 0


def verify_readiness() -> list[str]:
    sys.path.insert(0, str(ROOT))
    from backend.app.contracts.coze_tools import build_coze_tool_manifest
    from backend.app.main import app
    from backend.app.services.reference_validation import (
        compare_golden_result,
        load_json_object,
        validate_golden_result,
        validate_reference_manifest,
        validate_tool_openapi_compatibility,
    )

    failures: list[str] = []
    required_files = (
        REFERENCE_DOC,
        MANIFEST_PATH,
        PHASE_DOC,
        ENV_EXAMPLE,
        PLUGIN_PACKAGE,
        COZE_MANIFEST,
    )
    for path in required_files:
        if not path.is_file():
            failures.append(f"required file missing: {path.relative_to(ROOT).as_posix()}")
    if failures:
        return failures

    try:
        manifest = load_json_object(MANIFEST_PATH)
        stored_coze_manifest = load_json_object(COZE_MANIFEST)
        plugin_package = load_json_object(PLUGIN_PACKAGE)
    except (OSError, ValueError, json.JSONDecodeError):
        return ["required JSON material could not be parsed"]

    failures.extend(
        validate_reference_manifest(
            manifest, repository_root=ROOT, verify_local_files=True
        )
    )
    failures.extend(_json_secret_failures(manifest, "reference dataset manifest"))
    failures.extend(_json_secret_failures(stored_coze_manifest, "Coze manifest"))
    failures.extend(_json_secret_failures(plugin_package, "deployment plugin package"))
    golden_documents: dict[str, dict] = {}
    for dataset in manifest.get("datasets", []):
        golden_reference = str(dataset.get("golden_result") or "")
        golden_path = _safe_repository_path(golden_reference)
        if golden_path is None or not golden_path.is_file():
            failures.append(f"Golden Result missing for dataset: {dataset.get('dataset_id')}")
            continue
        try:
            golden = load_json_object(golden_path)
        except (OSError, ValueError, json.JSONDecodeError):
            failures.append(f"Golden Result is invalid JSON: {golden_reference}")
            continue
        golden_documents[dataset["dataset_id"]] = golden
        failures.extend(
            _json_secret_failures(golden, f"Golden Result {dataset['dataset_id']}")
        )
        failures.extend(validate_golden_result(golden))
        if golden.get("dataset_id") != dataset.get("dataset_id"):
            failures.append(f"Golden Result dataset mismatch: {dataset.get('dataset_id')}")
        comparison = compare_golden_result(
            _self_check_observation(golden),
            golden,
            environment={"deseq2_ready": False},
        )
        if not comparison["passed"]:
            failures.append(f"Golden Result is not self-consistent: {dataset.get('dataset_id')}")

    canonical_manifest = build_coze_tool_manifest()
    if stored_coze_manifest != canonical_manifest:
        failures.append("stored Coze manifest does not match canonical definitions")
    live_openapi = app.openapi()
    if not str(live_openapi.get("openapi") or "").startswith("3."):
        failures.append("live OpenAPI schema is invalid")
    failures.extend(
        validate_tool_openapi_compatibility(stored_coze_manifest, live_openapi)
    )
    expected_mappings = {
        tool["name"]: tool["http"]["operation_id"]
        for tool in stored_coze_manifest.get("tools", [])
    }
    package_mappings = {
        tool.get("name"): tool.get("operation_id")
        for tool in plugin_package.get("tools", [])
        if isinstance(tool, dict)
    }
    if package_mappings != expected_mappings:
        failures.append("deployment plugin mappings do not match Coze manifest")
    if plugin_package.get("base_url", {}).get("value") is not None:
        failures.append("deployment package must not embed a base URL")
    if plugin_package.get("authentication", {}).get("credential_in_package") is not False:
        failures.append("deployment package credential boundary is invalid")
    publication = plugin_package.get("publication", {})
    if any(publication.get(field) is not False for field in (
        "performed", "staging_deployment_performed", "production_endpoint_created"
    )):
        failures.append("deployment package incorrectly claims deployment or publication")

    public_materials = [REFERENCE_DOC, MANIFEST_PATH, *GOLDEN_ROOT.glob("*.json"), PHASE_DOC, ENV_EXAMPLE, PLUGIN_PACKAGE, COZE_MANIFEST]
    for path in public_materials:
        text = path.read_text(encoding="utf-8")
        failures.extend(_safe_material_failures(path, text))
    failures.extend(_environment_secret_failures(ENV_EXAMPLE))

    required_doc_statements = (
        "No real Coze deployment or publication was performed",
        "does not prove scientific validity",
        "synthetic fixture validates workflow behavior",
        "Rollback requirements",
        "Manual staging gates",
    )
    phase_text = " ".join(PHASE_DOC.read_text(encoding="utf-8").lower().split())
    for statement in required_doc_statements:
        if " ".join(statement.lower().split()) not in phase_text:
            failures.append(f"deployment readiness documentation missing: {statement}")
    return failures


def _safe_repository_path(value: str) -> Path | None:
    posix = PurePosixPath(value.replace("\\", "/"))
    if not value or posix.is_absolute() or ".." in posix.parts:
        return None
    return ROOT / Path(*posix.parts)


def _self_check_observation(golden: dict) -> dict:
    checks = golden["checks"]
    observation: dict = {
        **checks["exact"],
        "input_gene_count": checks["numeric_ranges"]["input_gene_count"]["min"],
        "reliability_information": {
            "available": False,
            "grade": None,
            "strong_conclusion_allowed": False,
        },
        "warnings": [],
        "limitations": [],
        "interpretation_boundary": "Exploratory output only.",
        "summary_fields": golden.get("expected_summary_schema_fields", []),
        "artifact_categories": checks["required_artifact_categories"],
        "claims": [],
        "deseq2_execution_state": "not_requested",
    }
    return observation


def _safe_material_failures(path: Path, text: str) -> list[str]:
    failures: list[str] = []
    lowered = text.lower()
    local_roots = (
        "/home/",
        "/mnt/",
        "/users/",
        "/private/",
        "/tmp/",
        "/var/",
        "/root/",
        "/workspace/",
    )
    if WINDOWS_PATH.search(text) or "file://" in lowered or any(root in lowered for root in local_roots):
        failures.append(f"local absolute path found in material: {path.relative_to(ROOT).as_posix()}")
    for raw_url in URL.findall(text):
        parsed = urlsplit(raw_url.rstrip(".,);]"))
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme.lower() != "https":
            failures.append(f"insecure URL found in material: {path.relative_to(ROOT).as_posix()}")
        if hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
            failures.append(f"local URL found in material: {path.relative_to(ROOT).as_posix()}")
        if parsed.username or parsed.password or parsed.query:
            failures.append(f"credential-bearing URL found in material: {path.relative_to(ROOT).as_posix()}")
    return failures


def _environment_secret_failures(path: Path) -> list[str]:
    failures: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name == "BIOINFO_API_KEY" and not (
            value.startswith("<") and value.endswith(">")
        ):
            failures.append("environment example contains a non-placeholder API key")
    return failures


def _json_secret_failures(value: object, label: str) -> list[str]:
    sensitive_keys = {
        "api_key",
        "access_token",
        "token",
        "password",
        "secret",
        "private_key",
    }
    failures: list[str] = []

    def visit(child: object, path: str) -> None:
        if isinstance(child, dict):
            for key, nested in child.items():
                nested_path = f"{path}.{key}" if path else str(key)
                if str(key).lower() in sensitive_keys and nested not in (
                    None,
                    "",
                    False,
                    "<set-in-deployment-secret-store>",
                ):
                    failures.append(f"possible secret value found in {label}: {nested_path}")
                visit(nested, nested_path)
        elif isinstance(child, list):
            for index, nested in enumerate(child):
                visit(nested, f"{path}[{index}]")

    visit(value, "")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
