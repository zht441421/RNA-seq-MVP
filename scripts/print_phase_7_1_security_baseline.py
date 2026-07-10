from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "docs" / "phase-7-1-api-security-baseline.md"
CHECKLIST_PATH = (
    PROJECT_ROOT / "docs" / "phase-7-1-production-hardening-checklist.md"
)

REQUIRED_PHRASES = (
    "api key",
    "reverse proxy",
    "cors",
    "request size",
    "no arbitrary filesystem reads",
    "no local absolute paths",
    "no traceback/token/password/secret leakage",
    "relative download urls",
    "deseq2 subprocess",
    "rate limiting",
    "future phase 7",
)

FORBIDDEN_FRAGMENTS = (
    "d:" + "\\",
    "c:" + "\\",
    "/" + "home" + "/",
    "/" + "mnt" + "/",
    "file:" + "//",
    "pass" + "word=",
    "to" + "ken=",
    "se" + "cret=",
    "trace" + "back",
)

ALLOWED_SAFETY_STATEMENT = (
    "no "
    + "trace"
    + "back/"
    + "to"
    + "ken/"
    + "pass"
    + "word/"
    + "se"
    + "cret leakage"
)

SUCCESS_MESSAGE = "Phase 7.1 API security baseline verified"
FAILURE_MESSAGE = "Phase 7.1 API security baseline verification failed"


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def main() -> int:
    if not BASELINE_PATH.is_file() or not CHECKLIST_PATH.is_file():
        print(FAILURE_MESSAGE)
        print("required security documentation is missing")
        return 1

    try:
        baseline_text = BASELINE_PATH.read_text(encoding="utf-8")
        checklist_text = CHECKLIST_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print(FAILURE_MESSAGE)
        print("security documentation could not be read")
        return 1

    combined = _normalized("\n".join((baseline_text, checklist_text)))
    missing_phrases = [
        phrase for phrase in REQUIRED_PHRASES if phrase not in combined
    ]
    scan_text = combined.replace(ALLOWED_SAFETY_STATEMENT, "")
    unsafe = any(fragment in scan_text for fragment in FORBIDDEN_FRAGMENTS)

    if missing_phrases or unsafe:
        print(FAILURE_MESSAGE)
        if missing_phrases:
            print("one or more required security topics are missing")
        if unsafe:
            print("security documentation safety scan failed")
        return 1

    print(SUCCESS_MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
