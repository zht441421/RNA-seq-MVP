from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/reference-datasets/reference-dataset-manifest.json"
DOC = ROOT / "docs/phase-8-6-reference-dataset-validation.md"
COMPOSE_OVERRIDE = ROOT / "deploy/staging/phase-8-6.compose.yml"
FETCH = ROOT / "scripts/fetch_phase_8_6_reference_datasets.py"
PREPARE = ROOT / "scripts/prepare_phase_8_6_reference_datasets.py"
RUN = ROOT / "scripts/run_phase_8_6_reference_validation.py"
PHASE_85_VERIFY = ROOT / "scripts/verify_phase_8_5_protected_staging.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Phase 8.6 reference-data validation.")
    parser.add_argument("--offline", action="store_true", help="Explicitly select the default offline verification mode.")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--real-data", action="store_true", help="Require cached sources, prepare them, and run local validation.")
    parser.add_argument("--staging", action="store_true", help="Run validation against an already-running protected local staging stack.")
    args = parser.parse_args()
    failures = verify_structure()
    if not failures:
        result = subprocess.run(
            [sys.executable, str(PHASE_85_VERIFY), "--skip-tests"], cwd=ROOT, check=False
        )
        if result.returncode:
            failures.append("Phase 8.5 protected-staging regression gate failed")
    if not failures and args.real_data:
        commands = (
            [sys.executable, str(FETCH), "--all", "--cache-only"],
            [sys.executable, str(PREPARE), "--all"],
            [sys.executable, str(RUN), "--all", "--mode", "local"],
        )
        for command in commands:
            if subprocess.run(command, cwd=ROOT, check=False).returncode:
                failures.append("real-public local validation gate failed")
                break
    if not failures and args.staging:
        result = subprocess.run(
            [sys.executable, str(RUN), "--all", "--mode", "staging"],
            cwd=ROOT,
            check=False,
        )
        if result.returncode:
            failures.append("real-public protected-staging validation gate failed")
    if not failures and not args.skip_tests:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=False)
        if result.returncode:
            failures.append("full pytest suite failed")
    if failures:
        print("Phase 8.6 reference dataset validation failed")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Phase 8.6 reference dataset validation verified")
    return 0


def verify_structure() -> list[str]:
    sys.path.insert(0, str(ROOT))
    from backend.app.services.reference_validation import (
        load_json_object,
        validate_golden_result,
        validate_reference_manifest,
    )

    failures: list[str] = []
    required = (MANIFEST, DOC, COMPOSE_OVERRIDE, FETCH, PREPARE, RUN, PHASE_85_VERIFY)
    for path in required:
        if not path.is_file():
            failures.append(f"required file missing: {path.relative_to(ROOT).as_posix()}")
    if failures:
        return failures
    manifest = load_json_object(MANIFEST)
    failures.extend(validate_reference_manifest(manifest, repository_root=ROOT, verify_local_files=True))
    public = [
        dataset for dataset in manifest.get("datasets", [])
        if dataset.get("data_nature") == "real_public"
    ]
    if len(public) < 2:
        failures.append("at least two real-public reference datasets are required")
    for dataset in public:
        golden_path = ROOT / Path(dataset["golden_result"])
        if not golden_path.is_file():
            failures.append(f"Golden Result missing: {dataset.get('dataset_id')}")
            continue
        failures.extend(validate_golden_result(load_json_object(golden_path)))
        for required_field in (
            "provenance", "license", "citation", "source_version", "retrieval",
            "preprocessing", "validation_scope", "biological_interpretation_scope",
        ):
            if not dataset.get(required_field):
                failures.append(f"{dataset.get('dataset_id')} missing {required_field}")
    compose = COMPOSE_OVERRIDE.read_text(encoding="utf-8")
    if ".reference-data/prepared:/var/lib/bioinfo/reference-data:ro" not in compose:
        failures.append("staging reference inputs are not mounted read-only in an isolated directory")
    if "BIOINFO_INPUT_ROOT: /var/lib/bioinfo/reference-data" not in compose:
        failures.append("staging reference input root is not explicitly scoped")
    ignored = subprocess.run(
        ["git", "check-ignore", ".reference-data/cache/example", ".reference-data/prepared/example", ".staging-runtime/phase-8-6-validation/example"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if ignored.returncode:
        failures.append("reference cache/prepared data or validation reports are not ignored")
    tracked = subprocess.run(["git", "ls-files", ".reference-data", ".staging-runtime"], cwd=ROOT, capture_output=True, text=True, check=False)
    if tracked.stdout.strip():
        failures.append("generated reference data or runtime reports are tracked")
    rendered = json.dumps(manifest, sort_keys=True).lower()
    for unsafe in ("-----begin private key-----", "api_key\"", "access_token\""):
        if unsafe in rendered:
            failures.append("reference manifest contains secret or local-path material")
    if re.search(r"(?i)(?<![a-z0-9])[a-z]:[\\\\/]", rendered):
        failures.append("reference manifest contains secret or local-path material")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
