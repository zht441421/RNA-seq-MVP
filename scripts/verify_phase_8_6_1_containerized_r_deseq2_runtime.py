from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.staging.yml"
REFERENCE_OVERRIDE = ROOT / "deploy/staging/phase-8-6.compose.yml"
ENTRYPOINT = ROOT / "deploy/staging/start-app.sh"
MANIFEST = ROOT / "docs/runtime/r-deseq2-runtime.json"
DOC = ROOT / "docs/phase-8-6-1-containerized-r-deseq2-runtime.md"
PROBE = ROOT / "scripts/probe_phase_8_6_1_r_deseq2_runtime.py"
CONTROLLED_R_PROBE = ROOT / "backend/app/scripts/r/deseq2_runtime_preflight.R"
REPORT = ROOT / ".staging-runtime/phase-8-6-1-verification.json"
IMAGE = "bioinformatics-agent-api:phase-8-6-1-local"


class VerificationFailure(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Phase 8.6.1 containerized R/DESeq2 runtime.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--offline", action="store_true")
    modes.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    failures = verify_structure()
    if not failures and args.offline:
        commands = (
            [sys.executable, "-m", "pytest", "-q", "tests/test_phase_8_6_1_containerized_r_deseq2_runtime.py"],
            [sys.executable, "scripts/verify_phase_8_2_coze_tool_interface.py", "--skip-tests"],
            [sys.executable, "scripts/verify_phase_8_3_local_agent_simulation.py", "--skip-tests"],
            [sys.executable, "scripts/verify_phase_8_6_reference_dataset_validation.py", "--offline", "--skip-tests"],
        )
        for command in commands:
            if subprocess.run(command, cwd=ROOT, check=False).returncode:
                failures.append("offline regression command failed")
                break
    docker_result: dict[str, Any] | None = None
    if not failures and args.docker:
        try:
            docker_result = verify_docker_runtime()
        except VerificationFailure as exc:
            failures.append(str(exc))
        except Exception as exc:
            failures.append(
                "Docker verification stopped after an unexpected safe orchestration failure "
                f"({type(exc).__name__})"
            )
    if failures:
        print("Phase 8.6.1 containerized R/DESeq2 runtime verification failed")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Phase 8.6.1 containerized R/DESeq2 runtime verified")
    if docker_result:
        print(json.dumps(docker_result, indent=2, sort_keys=True))
    return 0


def verify_structure() -> list[str]:
    failures: list[str] = []
    required = (DOCKERFILE, COMPOSE, REFERENCE_OVERRIDE, ENTRYPOINT, MANIFEST, DOC, PROBE, CONTROLLED_R_PROBE)
    for path in required:
        if not path.is_file():
            failures.append(f"required file missing: {path.relative_to(ROOT).as_posix()}")
    if failures:
        return failures
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return ["runtime version manifest is not valid JSON"]
    for field in (
        "schema_version", "base_image", "base_image_digest", "debian_snapshot",
        "linux_distribution", "python_version", "r_version", "rscript_version",
        "bioconductor_version", "biocmanager_version", "deseq2_version",
        "required_packages", "pinned_debian_packages", "verified_system_libraries",
    ):
        if not manifest.get(field):
            failures.append(f"runtime version manifest missing: {field}")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8").lower()
    lowered_dockerfile = dockerfile.lower()
    if "@sha256:" not in dockerfile.splitlines()[0] or any(word in dockerfile.splitlines()[0].lower() for word in ("latest", "devel", "rolling")):
        failures.append("application base image is not digest-pinned")
    for value in (
        "snapshot.debian.org", "r-base-core=", "r-cran-biocmanager=", "r-bioc-deseq2=",
        "R --version", "Rscript --version", "library(pkg, character.only=TRUE)", "USER 10001:10001",
    ):
        if value not in dockerfile:
            failures.append(f"Dockerfile runtime requirement missing: {value}")
    if "biocmanager::install" in lowered_dockerfile or "install.packages" in lowered_dockerfile:
        failures.append("Dockerfile uses dynamic R package installation")
    if "install.packages" in entrypoint or "biocmanager::install" in entrypoint or "apt-get" in entrypoint:
        failures.append("container startup attempts package installation")
    for value in (
        'user: "10001:10001"', "read_only: true", "cap_drop:", "- ALL",
        "no-new-privileges:true", '"127.0.0.1:8443:8443"',
        "BIOINFO_R_RUNTIME_MANIFEST:", "pids_limit: 256",
    ):
        if value not in compose:
            failures.append(f"staging security/runtime requirement missing: {value}")
    if "8000:8000" in compose:
        failures.append("FastAPI internal port is exposed directly")
    if ".reference-data/prepared:/var/lib/bioinfo/reference-data:ro" not in REFERENCE_OVERRIDE.read_text(encoding="utf-8"):
        failures.append("reference data mount is not read-only")
    if manifest.get("package_repository_policy", {}).get("runtime_installation_allowed") is not False:
        failures.append("runtime package installation policy is not disabled")
    if manifest.get("package_repository_policy", {}).get("task_time_installation_allowed") is not False:
        failures.append("task-time package installation policy is not disabled")
    tracked = subprocess.run(
        ["git", "ls-files", ".staging-secrets", ".staging-runtime", ".reference-data", "*.key", "*.pem", "*.sqlite3"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if tracked.stdout.strip():
        failures.append("secret, runtime, reference-data, or database material is tracked")
    return failures


def verify_docker_runtime() -> dict[str, Any]:
    env = {**os.environ, "BIOINFO_IMAGE_TAG": "phase-8-6-1-local", "BIOINFO_BUILD_ID": "phase-8-6-1-uncommitted"}
    base = ["docker", "compose", "-f", str(COMPOSE)]
    reference = [*base, "-f", str(REFERENCE_OVERRIDE)]
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "mode": "docker",
        "image": IMAGE,
        "scientific_baseline_created": False,
        "coze_integration": False,
        "remote_deployment": False,
    }
    _run([sys.executable, "scripts/prepare_phase_8_5_local_staging.py"])
    try:
        _run(["docker", "build", "--pull=false", "--build-arg", "VCS_REF=phase-8-6-1-uncommitted", "-t", IMAGE, "."])
        _run([*base, "up", "--no-build", "-d"], env=env)
        _wait_for_api_health(base, env)
        probe = _container_probe(base, env)
        preflight = _staging_preflight()
        _require(probe.get("ready") is True, "container runtime probe is not ready")
        _require(preflight.get("ready") is True, "existing DESeq2 preflight is not ready")
        _assert_container_security(base, env)
        _run([sys.executable, "scripts/smoke_phase_8_5_protected_staging.py"])
        result.update({"runtime_probe": probe, "preflight_ready": True, "phase_8_5_smoke": "passed"})
        _run([*base, "restart", "api"], env=env)
        _wait_for_api_health(base, env)
        restarted_probe = _container_probe(base, env)
        restarted_preflight = _staging_preflight()
        _require(restarted_probe.get("ready") is True and restarted_preflight.get("ready") is True, "runtime readiness did not survive restart")
        result["restart_readiness"] = "passed"
        _run([*base, "down"], env=env)

        prepared = ROOT / ".reference-data/prepared"
        if all((prepared / dataset / "counts.csv").is_file() for dataset in (
            "phase-8-6-pasilla-public-v1", "phase-8-6-gse60450-luminal-public-v1"
        )):
            _run([*reference, "up", "--no-build", "-d"], env=env)
            _wait_for_api_health(reference, env)
            _container_probe(reference, env)
            _require(_staging_preflight().get("ready") is True, "reference staging DESeq2 preflight is not ready")
            _run([*reference, "exec", "-T", "api", "/usr/bin/test", "!", "-w", "/var/lib/bioinfo/reference-data"], env=env)
            _run([sys.executable, "scripts/run_phase_8_6_reference_validation.py", "--all", "--mode", "staging"])
            result["phase_8_6_minimal_real_data"] = "passed"
        else:
            result["phase_8_6_minimal_real_data"] = "skipped_cache_unavailable"
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result
    finally:
        subprocess.run([*reference, "down"], cwd=ROOT, env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([*base, "down"], cwd=ROOT, env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _container_probe(compose: list[str], env: dict[str, str]) -> dict[str, Any]:
    completed = _run([*compose, "exec", "-T", "api", "python", "scripts/probe_phase_8_6_1_r_deseq2_runtime.py", "--json"], env=env, capture=True)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationFailure("container runtime probe returned invalid JSON") from exc


def _staging_preflight() -> dict[str, Any]:
    from scripts.run_phase_8_6_reference_validation import (
        ReferenceDataError,
        StagingClient,
        _json_request,
    )
    secret = ROOT / ".staging-secrets/api_key.txt"
    api_key = secret.read_text(encoding="utf-8").strip()
    for attempt in range(3):
        try:
            client = StagingClient("https://127.0.0.1:8443", api_key)
            return _json_request(client, "GET", "/task/formal-de/preflight")
        except ReferenceDataError:
            if attempt == 2:
                break
            time.sleep(2)
    raise VerificationFailure("protected staging preflight did not become available")


def _assert_container_security(compose: list[str], env: dict[str, str]) -> None:
    container_id = _run([*compose, "ps", "-q", "api"], env=env, capture=True).stdout.strip()
    inspect = json.loads(_run(["docker", "inspect", container_id], capture=True).stdout)[0]
    _require(inspect["Config"]["User"] == "10001:10001", "application container is not configured non-root")
    _require(inspect["HostConfig"]["ReadonlyRootfs"] is True, "application root filesystem is not read-only")
    _require("ALL" in (inspect["HostConfig"].get("CapDrop") or []), "capabilities are not dropped")
    _run([*compose, "exec", "-T", "api", "/usr/bin/test", "!", "-w", "/opt/bioinformatics-agent"], env=env)


def _wait_for_api_health(compose: list[str], env: dict[str, str]) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        container_id = _run([*compose, "ps", "-q", "api"], env=env, capture=True).stdout.strip()
        if container_id:
            status = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if status.returncode == 0 and status.stdout.strip() == "healthy":
                return
        time.sleep(2)
    raise VerificationFailure("application container did not become healthy")


def _run(command: list[str], *, env: dict[str, str] | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=capture, text=True, check=False)
    if completed.returncode:
        raise VerificationFailure("Docker verification command failed safely.")
    return completed


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


if __name__ == "__main__":
    raise SystemExit(main())
