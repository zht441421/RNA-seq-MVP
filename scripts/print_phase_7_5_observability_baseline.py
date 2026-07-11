from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ROOT / "backend" / "app" / "utils" / "logging.py",
    ROOT / "backend" / "app" / "middleware" / "observability.py",
    ROOT / "tests" / "test_phase_7_5_observability.py",
    ROOT / "docs" / "phase-7-5-observability-scaffold.md",
)


def main() -> int:
    main_source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checks = (
        all(path.is_file() for path in REQUIRED),
        "RequestObservabilityMiddleware" in main_source,
        '"version": app.version' in main_source,
        "Phase 7.5" in readme,
    )
    if not all(checks):
        print("Phase 7.5 observability baseline verification failed")
        return 1
    print("Phase 7.5 observability baseline verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
