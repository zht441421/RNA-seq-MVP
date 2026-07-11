from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ROOT / "backend" / "app" / "middleware" / "rate_limit.py",
    ROOT / "tests" / "test_phase_7_4_rate_limiting.py",
    ROOT / "docs" / "phase-7-4-rate-limiting-scaffold.md",
)


def main() -> int:
    config = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    variables = (
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_REQUESTS",
        "RATE_LIMIT_WINDOW_SECONDS",
        "RATE_LIMIT_SCOPE",
        "RATE_LIMIT_EXEMPT_PATHS",
    )
    if not all(path.is_file() for path in REQUIRED):
        print("Phase 7.4 rate limiting baseline verification failed")
        return 1
    if not all(variable in config for variable in variables):
        print("Phase 7.4 rate limiting baseline verification failed")
        return 1
    if "Phase 7.4" not in readme:
        print("Phase 7.4 rate limiting baseline verification failed")
        return 1
    print("Phase 7.4 rate limiting baseline verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
