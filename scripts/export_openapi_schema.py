import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_app():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from backend.app.main import app

    return app


def main() -> None:
    docs_dir = REPO_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    output_path = docs_dir / "openapi.json"
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(_load_app().openapi(), output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    print(output_path)


if __name__ == "__main__":
    main()
