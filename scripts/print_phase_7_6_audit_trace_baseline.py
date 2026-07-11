from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ROOT / "backend/app/services/execution_trace.py",
    ROOT / "tests/test_phase_7_6_audit_execution_trace.py",
    ROOT / "docs/phase-7-6-audit-execution-trace-scaffold.md",
)

def main() -> int:
    trace = REQUIRED[0].read_text(encoding="utf-8") if REQUIRED[0].is_file() else ""
    registry = (ROOT / "backend/app/services/task_registry.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checks = (all(path.is_file() for path in REQUIRED), "trace_id" in trace, "configuration_snapshot_id" in trace, "begin_execution_trace" in registry, "Phase 7.6" in readme)
    if not all(checks):
        print("Phase 7.6 audit execution trace baseline verification failed")
        return 1
    print("Phase 7.6 audit execution trace baseline verified")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
