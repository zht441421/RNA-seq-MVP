import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/phase-8-1-coze-integration-contract.md"
MANIFEST = ROOT / "backend/app/contracts/coze_integration_manifest.json"
TEST = ROOT / "tests/test_phase_8_1_coze_integration_contract.py"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from backend.app.main import app

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
    schema = app.openapi()
    checks = [DOC.is_file(), MANIFEST.is_file(), TEST.is_file(), schema.get("openapi", "").startswith("3.")]
    for operation in manifest.get("operations", []):
        described = schema.get("paths", {}).get(operation["path"], {}).get(operation["method"].lower(), {})
        checks.append(described.get("operationId") == operation["operation_id"])
    if not checks or not all(checks):
        print("Phase 8.1 Coze integration contract verification failed")
        return 1
    print("Phase 8.1 Coze integration contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
