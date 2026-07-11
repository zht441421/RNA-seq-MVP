import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "coze-tool-manifest.json"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from backend.app.contracts.coze_tools import build_coze_tool_manifest

    OUTPUT.write_text(
        json.dumps(build_coze_tool_manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
