from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_FILES = (
    "plugin_metadata.json",
    "tool_sequence.json",
    "tool_instructions.md",
    "openapi_endpoint_selection.json",
    "coze_tool_field_mapping.json",
)

REQUIRED_ENDPOINTS = (
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

REQUIRED_SAFETY_PHRASES = (
    "safe relative",
    "local absolute paths",
    "coze-summary",
    "DESeq2",
    "preflight",
    "minimal workflow",
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
    manifest_dir = repo_root / "docs" / "examples" / "coze_manifest"
    errors: list[str] = []

    if not manifest_dir.is_dir():
        errors.append("Missing manifest directory: docs/examples/coze_manifest")
    else:
        _check_required_files(manifest_dir, errors)
        _check_json_files(manifest_dir, errors)
        _check_required_endpoints(manifest_dir, errors)
        _check_required_safety_language(manifest_dir, errors)
        _check_forbidden_fragments(manifest_dir, errors)

    if errors:
        print("Phase 6.2 Coze manifest materials verification failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Phase 6.2 Coze manifest materials verified")
    return 0


def _check_required_files(manifest_dir: Path, errors: list[str]) -> None:
    for filename in REQUIRED_FILES:
        if not (manifest_dir / filename).is_file():
            errors.append(f"Missing required file: {filename}")


def _check_json_files(manifest_dir: Path, errors: list[str]) -> None:
    for path in manifest_dir.glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {path.name}: {exc}")


def _check_required_endpoints(manifest_dir: Path, errors: list[str]) -> None:
    path = manifest_dir / "openapi_endpoint_selection.json"
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    endpoints = {
        (str(item.get("method", "")).upper(), str(item.get("path", "")))
        for item in payload.get("endpoints", [])
        if isinstance(item, dict)
    }
    for endpoint in REQUIRED_ENDPOINTS:
        if endpoint not in endpoints:
            errors.append(f"Missing endpoint selection: {endpoint[0]} {endpoint[1]}")


def _check_required_safety_language(manifest_dir: Path, errors: list[str]) -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in manifest_dir.iterdir()
        if path.is_file() and path.suffix in {".json", ".md"}
    )
    combined_lower = combined.lower()
    for phrase in REQUIRED_SAFETY_PHRASES:
        if phrase.lower() not in combined_lower:
            errors.append(f"Missing required safety language: {phrase}")


def _check_forbidden_fragments(manifest_dir: Path, errors: list[str]) -> None:
    for path in manifest_dir.iterdir():
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_fragment in FORBIDDEN_FRAGMENTS:
            if forbidden_fragment in text:
                errors.append(f"Unsafe fragment in {path.name}: {forbidden_fragment}")


if __name__ == "__main__":
    sys.exit(main())
