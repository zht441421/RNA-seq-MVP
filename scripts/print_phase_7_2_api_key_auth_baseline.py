from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "phase-7-2-api-key-auth-scaffold.md"
TEST_PATHS = (
    PROJECT_ROOT / "tests" / "test_phase_7_2_api_key_auth_settings.py",
    PROJECT_ROOT / "tests" / "test_phase_7_2_api_key_auth_behavior.py",
    PROJECT_ROOT / "tests" / "test_phase_7_2_api_key_auth_docs.py",
    PROJECT_ROOT
    / "tests"
    / "test_phase_7_2_api_key_auth_baseline_script.py",
)
REQUIRED_PHRASES = (
    "disabled by default",
    "bioinfo_require_api_key",
    "bioinfo_api_key",
    "bioinfo_api_key_header",
    "x-bioinfo-api-key",
    "constant-time comparison",
    "sanitized 401",
    "no secrets",
    "coze",
    "reverse proxy",
)
SUCCESS_MESSAGE = "Phase 7.2 API key auth scaffold verified"
FAILURE_MESSAGE = "Phase 7.2 API key auth scaffold verification failed"


def main() -> int:
    if not DOC_PATH.is_file() or any(not path.is_file() for path in TEST_PATHS):
        print(FAILURE_MESSAGE)
        print("required Phase 7.2 material is missing")
        return 1

    try:
        text = " ".join(DOC_PATH.read_text(encoding="utf-8").lower().split())
    except (OSError, UnicodeError):
        print(FAILURE_MESSAGE)
        print("Phase 7.2 documentation could not be read")
        return 1

    if any(phrase not in text for phrase in REQUIRED_PHRASES):
        print(FAILURE_MESSAGE)
        print("one or more required Phase 7.2 topics are missing")
        return 1

    print(SUCCESS_MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
