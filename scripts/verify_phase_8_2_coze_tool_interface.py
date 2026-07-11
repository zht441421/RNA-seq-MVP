import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/phase-8-2-coze-tool-interface.md"
MANIFEST = ROOT / "docs/coze-tool-manifest.json"
SCHEMA = ROOT / "backend/app/contracts/coze_tools.py"
TEST = ROOT / "tests/test_phase_8_2_coze_tool_interface.py"


def main() -> int:
    run_tests = "--skip-tests" not in sys.argv[1:]
    sys.path.insert(0, str(ROOT))
    from backend.app.contracts.coze_tools import build_coze_tool_manifest
    from backend.app.main import app

    files_exist = all(path.is_file() for path in (DOC, MANIFEST, SCHEMA, TEST))
    try:
        stored = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stored = None
    valid = files_exist and stored == build_coze_tool_manifest()
    if valid:
        openapi = app.openapi()
        for tool in stored["tools"]:
            binding = tool["http"]
            operation = openapi.get("paths", {}).get(binding["path"], {}).get(binding["method"].lower(), {})
            valid = valid and operation.get("operationId") == binding["operation_id"]
    if valid and run_tests:
        valid = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=False
        ).returncode == 0
    print("Phase 8.2 Coze tool interface verified" if valid else "Phase 8.2 Coze tool interface verification failed")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
