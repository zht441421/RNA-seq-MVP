import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SIMULATOR = ROOT / "backend/app/services/local_agent_simulator.py"
WORKFLOW_TEST = ROOT / "tests/test_phase_8_3_local_agent_simulation.py"
DOC = ROOT / "docs/phase-8-3-local-agent-simulation.md"
MANIFEST = ROOT / "docs/coze-tool-manifest.json"


def main() -> int:
    run_tests = "--skip-tests" not in sys.argv[1:]
    sys.path.insert(0, str(ROOT))
    from backend.app.contracts.coze_tools import build_coze_tool_manifest
    from backend.app.main import app
    from backend.app.services.local_agent_simulator import LocalAgentSimulator

    valid = all(path.is_file() for path in (SIMULATOR, WORKFLOW_TEST, DOC, MANIFEST))
    try:
        stored = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stored = None
    valid = valid and stored == build_coze_tool_manifest()
    if valid:
        manifest_names = {tool["name"] for tool in stored["tools"]}
        simulator_names = set(LocalAgentSimulator._INTENT_TO_TOOL.values())
        valid = manifest_names == simulator_names
        openapi = app.openapi()
        for tool in stored["tools"]:
            binding = tool["http"]
            operation = openapi.get("paths", {}).get(binding["path"], {}).get(binding["method"].lower(), {})
            valid = valid and operation.get("operationId") == binding["operation_id"]
    if valid and run_tests:
        valid = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=False
        ).returncode == 0
    print("Phase 8.3 local agent simulation verified" if valid else "Phase 8.3 local agent simulation verification failed")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
