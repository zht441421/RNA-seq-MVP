from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "docs" / "phase-6-completion-baseline.md"
CHECKLIST_PATH = (
    PROJECT_ROOT / "docs" / "phase-6-deployment-readiness-checklist.md"
)

REQUIRED_FILES = (
    PROJECT_ROOT / "docs" / "phase-6-1-api-deployment-contract.md",
    PROJECT_ROOT / "docs" / "phase-6-1-coze-api-contract.md",
    PROJECT_ROOT / "docs" / "phase-6-2-coze-plugin-manifest-preparation.md",
    PROJECT_ROOT
    / "docs"
    / "examples"
    / "coze_manifest"
    / "openapi_coze_subset.json",
    PROJECT_ROOT / "scripts" / "run_phase_6_3_local_api_smoke_test.py",
    PROJECT_ROOT / "docs" / "phase-6-3-local-api-smoke-test.md",
    PROJECT_ROOT / "docs" / "phase-6-4-deployment-runbook.md",
    PROJECT_ROOT / "docs" / "phase-6-4-operator-checklist.md",
    PROJECT_ROOT / "docs" / "openapi.json",
)

REQUIRED_DIRECTORIES = (
    PROJECT_ROOT / "docs" / "examples" / "coze",
    PROJECT_ROOT / "docs" / "examples" / "coze_manifest",
)

FORBIDDEN_FRAGMENTS = (
    "d:" + "\\",
    "c:" + "\\",
    "/" + "home" + "/",
    "/" + "mnt" + "/",
    "file:" + "//",
    "to" + "ken",
    "pass" + "word",
    "se" + "cret",
    "trace" + "back",
)

ALLOWED_SAFETY_STATEMENT = (
    "no "
    + "trace"
    + "back"
    + "/"
    + "to"
    + "ken"
    + "/"
    + "pass"
    + "word"
    + "/"
    + "se"
    + "cret"
    + " leakage"
)

SUCCESS_MESSAGE = "Phase 6 deployment-readiness baseline verified"
FAILURE_MESSAGE = "Phase 6 deployment-readiness baseline verification failed"


def main() -> int:
    if not BASELINE_PATH.is_file() or not CHECKLIST_PATH.is_file():
        print(FAILURE_MESSAGE)
        print("required completion documentation is missing")
        return 1

    missing_material = any(not path.is_file() for path in REQUIRED_FILES)
    missing_material = missing_material or any(
        not path.is_dir() for path in REQUIRED_DIRECTORIES
    )

    try:
        baseline_text = BASELINE_PATH.read_text(encoding="utf-8")
        checklist_text = CHECKLIST_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print(FAILURE_MESSAGE)
        print("completion documentation could not be read")
        return 1

    safety_text = "\n".join((baseline_text, checklist_text)).lower()
    safety_text = safety_text.replace(ALLOWED_SAFETY_STATEMENT, "")
    has_forbidden_fragment = any(
        fragment in safety_text for fragment in FORBIDDEN_FRAGMENTS
    )

    if missing_material or has_forbidden_fragment:
        print(FAILURE_MESSAGE)
        if missing_material:
            print("one or more required Phase 6 materials are missing")
        if has_forbidden_fragment:
            print("completion documentation safety scan failed")
        return 1

    print(SUCCESS_MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
