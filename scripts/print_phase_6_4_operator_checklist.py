from __future__ import annotations

import sys
from pathlib import Path


CHECKLIST_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "phase-6-4-operator-checklist.md"
)

REQUIRED_SECTIONS = (
    "# Phase 6.4 Operator Checklist",
    "## Before Launch",
    "## Environment Variables",
    "## Directory Existence",
    "## Local-Only Launch",
    "## Health Check",
    "## Smoke Test",
    "## Coze Base URL Readiness",
    "## Artifact Download Verification",
    "## Coze-Summary Verification",
    "## Safety Verification",
    "## DESeq2 Preflight Check",
    "## Backup And Cleanup",
    "## Troubleshooting",
    "## Known Limitations",
    "## Release Tag Verification",
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

SUCCESS_MESSAGE = "Phase 6.4 operator checklist verified"
FAILURE_MESSAGE = "Phase 6.4 operator checklist verification failed"


def main() -> int:
    if not CHECKLIST_PATH.is_file():
        print(FAILURE_MESSAGE)
        print("required checklist file is missing")
        return 1

    try:
        text = CHECKLIST_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print(FAILURE_MESSAGE)
        print("required checklist file could not be read")
        return 1

    missing_sections = [
        section for section in REQUIRED_SECTIONS if section not in text
    ]
    has_forbidden_fragment = any(
        fragment in text.lower() for fragment in FORBIDDEN_FRAGMENTS
    )

    if missing_sections or has_forbidden_fragment:
        print(FAILURE_MESSAGE)
        if missing_sections:
            print("one or more required checklist sections are missing")
        if has_forbidden_fragment:
            print("checklist safety scan failed")
        return 1

    print(SUCCESS_MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
