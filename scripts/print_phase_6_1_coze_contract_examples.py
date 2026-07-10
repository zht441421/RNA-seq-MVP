from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_EXAMPLE_FILES = (
    "create_task_request.json",
    "create_task_response.json",
    "register_metadata_request.json",
    "register_count_matrix_request.json",
    "run_minimal_contrast_request.json",
    "run_deseq2_contrast_request.json",
    "coze_summary_minimal_response.json",
    "artifact_download_reference.json",
    "error_invalid_contrast_response.json",
    "error_missing_input_response.json",
)

FORBIDDEN_FRAGMENTS = (
    "d:\\",
    "c:\\",
    "/home/",
    "/mnt/",
    "file://",
    "traceback",
    "token",
    "password",
    "secret",
)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    examples_dir = repo_root / "docs" / "examples" / "coze"

    errors: list[str] = []
    parsed_count = 0
    for filename in REQUIRED_EXAMPLE_FILES:
        path = examples_dir / filename
        if not path.is_file():
            errors.append(f"Missing example file: {filename}")
            continue

        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden_fragment in FORBIDDEN_FRAGMENTS:
            if forbidden_fragment in lowered:
                errors.append(f"Forbidden fragment in {filename}: {forbidden_fragment}")

        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {filename}: {exc}")
        else:
            parsed_count += 1

    if errors:
        print("Phase 6.1 Coze contract examples verification failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Phase 6.1 Coze contract examples verified")
    print(f"- directory: {examples_dir.relative_to(repo_root).as_posix()}")
    print(f"- json_files: {parsed_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
