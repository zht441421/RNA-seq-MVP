from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "phase-7-3-request-limits-timeout-hardening.md"
TESTS = tuple(ROOT / "tests" / name for name in (
    "test_phase_7_3_request_limit_settings.py",
    "test_phase_7_3_request_limit_behavior.py",
    "test_phase_7_3_request_limits_docs.py",
    "test_phase_7_3_request_limits_baseline_script.py",
))
REQUIRED = (
    "disabled by default", "bioinfo_max_request_bytes",
    "bioinfo_request_timeout_seconds", "http 413",
    "request_body_too_large", "reverse proxy", "api gateway", "coze",
    "deseq2 subprocess", "no body content", "no secrets",
)

def main() -> int:
    if not DOC.is_file() or any(not path.is_file() for path in TESTS):
        print("Phase 7.3 request limits baseline verification failed")
        print("required Phase 7.3 material is missing")
        return 1
    try:
        text = " ".join(DOC.read_text(encoding="utf-8").lower().split())
    except (OSError, UnicodeError):
        print("Phase 7.3 request limits baseline verification failed")
        print("Phase 7.3 documentation could not be read")
        return 1
    if any(phrase not in text for phrase in REQUIRED):
        print("Phase 7.3 request limits baseline verification failed")
        print("one or more required Phase 7.3 topics are missing")
        return 1
    print("Phase 7.3 request limits baseline verified")
    return 0

if __name__ == "__main__":
    sys.exit(main())
