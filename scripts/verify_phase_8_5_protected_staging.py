from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.staging.yml"
DOCKERFILE = ROOT / "Dockerfile"
NGINX = ROOT / "deploy/staging/nginx.conf"
ENTRYPOINT = ROOT / "deploy/staging/start-app.sh"
DOC = ROOT / "docs/phase-8-5-protected-staging-deployment.md"
SMOKE = ROOT / "scripts/smoke_phase_8_5_protected_staging.py"
PREPARE = ROOT / "scripts/prepare_phase_8_5_local_staging.py"
OPENSSL_CONFIG = ROOT / "deploy/staging/openssl-local.cnf"
PHASE_84_VERIFY = ROOT / "scripts/verify_phase_8_4_reference_dataset_readiness.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Phase 8.5 protected staging.")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Test a running local staging stack.")
    args = parser.parse_args()
    failures = verify_structure()
    if not failures:
        phase_84 = subprocess.run(
            [sys.executable, str(PHASE_84_VERIFY), "--skip-tests"],
            cwd=ROOT,
            check=False,
        )
        if phase_84.returncode:
            failures.append("Phase 8.4 reference and Golden Result gate failed")
    if not failures and not args.skip_tests:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=False)
        if result.returncode:
            failures.append("full pytest suite failed")
    if not failures and args.smoke:
        result = subprocess.run([sys.executable, str(SMOKE)], cwd=ROOT, check=False)
        if result.returncode:
            failures.append("local protected staging smoke test failed")
    if failures:
        print("Phase 8.5 protected staging verification failed")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Phase 8.5 protected staging verified")
    return 0


def verify_structure() -> list[str]:
    failures: list[str] = []
    required = (COMPOSE, DOCKERFILE, NGINX, ENTRYPOINT, OPENSSL_CONFIG, DOC, SMOKE, PREPARE, PHASE_84_VERIFY)
    for path in required:
        if not path.is_file():
            failures.append(f"required file missing: {path.relative_to(ROOT).as_posix()}")
    if failures:
        return failures

    compose = COMPOSE.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    nginx = NGINX.read_text(encoding="utf-8")
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    docs = DOC.read_text(encoding="utf-8").lower()

    compose_requirements = (
        'user: "10001:10001"', "read_only: true", "cap_drop:", "no-new-privileges:true",
        "BIOINFO_REQUIRE_API_KEY: \"true\"", "BIOINFO_API_KEY_FILE:", "secrets:",
        "staging_state:/var/lib/bioinfo/state", "staging_artifacts:/var/lib/bioinfo/artifacts",
        '"127.0.0.1:8443:8443"', "internal: true", "healthcheck:",
    )
    for value in compose_requirements:
        if value not in compose:
            failures.append(f"staging Compose safety requirement missing: {value}")
    if "8000:8000" in compose:
        failures.append("API container must not publish its internal port")
    for value in ("USER 10001:10001", "ENTRYPOINT", "HEALTHCHECK"):
        if value not in dockerfile:
            failures.append(f"Dockerfile runtime requirement missing: {value}")
    if "BIOINFO_API_KEY=" in dockerfile or "PRIVATE KEY" in dockerfile:
        failures.append("Dockerfile contains credential material")
    for value in ("listen 8443 ssl", "ssl_certificate ", "return 308 https://localhost:8443", "proxy_set_header X-Forwarded-For $remote_addr"):
        if value not in nginx:
            failures.append(f"TLS proxy requirement missing: {value}")
    if "$http_x_forwarded" in nginx.lower() or "$http_authorization" in nginx.lower():
        failures.append("proxy trusts a client-controlled forwarding or authorization value")
    if "$http_x_bioinfo_api_key" in nginx.lower():
        failures.append("proxy logging/configuration explicitly expands the API key header")
    if "--no-proxy-headers" not in entrypoint or "--workers 1" not in entrypoint:
        failures.append("application entrypoint does not enforce the single-worker proxy boundary")

    doc_requirements = (
        "no remote deployment", "secret rotation", "rollback", "persistence", "restart",
        "health", "rate limit", "execution trace", "phase 8.6", "does not prove scientific validity",
    )
    for value in doc_requirements:
        if value not in docs:
            failures.append(f"staging runbook missing statement: {value}")

    ignored = subprocess.run(
        ["git", "check-ignore", ".staging-secrets/api_key.txt", ".staging-secrets/staging.key", ".staging-runtime/state.json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if ignored.returncode:
        failures.append("local secrets or runtime state are not ignored by Git")
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False)
    for relative in tracked.stdout.splitlines():
        lowered = relative.lower()
        if lowered.startswith(".staging-secrets/") or lowered.endswith((".pem", ".key")):
            failures.append(f"tracked secret/private-key material: {relative}")
    manifest = json.loads((ROOT / "docs/coze-tool-manifest.json").read_text(encoding="utf-8"))
    operation_ids = {tool["http"]["operation_id"] for tool in manifest["tools"]}
    if len(operation_ids) != 7:
        failures.append("all seven agent tool operation IDs were not preserved")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
