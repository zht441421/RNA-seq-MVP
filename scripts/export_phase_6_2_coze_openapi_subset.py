from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


RECOMMENDED_ENDPOINTS = (
    ("GET", "/health"),
    ("POST", "/task/create"),
    ("POST", "/task/{task_id}/inputs/register"),
    ("POST", "/task/run"),
    ("GET", "/task/{task_id}/status"),
    ("GET", "/task/{task_id}/coze-summary"),
    ("GET", "/task/{task_id}/artifacts"),
    ("GET", "/task/{task_id}/artifacts/{artifact_name}/download"),
    ("GET", "/task/formal-de/preflight"),
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
    source_path = repo_root / "docs" / "openapi.json"
    output_path = (
        repo_root
        / "docs"
        / "examples"
        / "coze_manifest"
        / "openapi_coze_subset.json"
    )

    source = json.loads(source_path.read_text(encoding="utf-8"))
    subset = _build_subset(source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = json.dumps(subset, indent=2, sort_keys=True) + "\n"
    _assert_safe_text(output_text)
    output_path.write_text(output_text, encoding="utf-8")
    json.loads(output_path.read_text(encoding="utf-8"))

    print("Phase 6.2 Coze OpenAPI subset exported")
    print(f"- output: {output_path.relative_to(repo_root).as_posix()}")
    print(f"- endpoints: {len(RECOMMENDED_ENDPOINTS)}")
    return 0


def _build_subset(source: dict[str, Any]) -> dict[str, Any]:
    source_paths = source.get("paths", {})
    selected_paths: dict[str, Any] = {}
    missing: list[str] = []

    for method, path in RECOMMENDED_ENDPOINTS:
        method_key = method.lower()
        path_item = source_paths.get(path, {})
        operation = path_item.get(method_key)
        if operation is None:
            missing.append(f"{method} {path}")
            continue
        selected_paths.setdefault(path, {})[method_key] = operation

    if missing:
        raise ValueError("Missing recommended OpenAPI endpoints: " + ", ".join(missing))

    return {
        "openapi": source.get("openapi", "3.1.0"),
        "info": {
            **source.get("info", {}),
            "description": (
                "Phase 6.2 draft subset for initial Coze plugin preparation. "
                "Generated from docs/openapi.json without changing runtime schemas."
            ),
        },
        "paths": selected_paths,
        "components": source.get("components", {}),
        "x-phase": "6.2",
        "x-purpose": "coze-plugin-manifest-preparation",
        "x-selected-endpoints": [
            {"method": method, "path": path}
            for method, path in RECOMMENDED_ENDPOINTS
        ],
    }


def _assert_safe_text(text: str) -> None:
    lowered = text.lower()
    for forbidden_fragment in FORBIDDEN_FRAGMENTS:
        if forbidden_fragment in lowered:
            raise ValueError(f"Unsafe fragment found in generated subset: {forbidden_fragment}")


if __name__ == "__main__":
    sys.exit(main())
