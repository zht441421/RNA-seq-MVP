import json
from pathlib import Path


MANIFEST_DIR = Path("docs/examples/coze_manifest")
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
REQUIRED_FIELD_MAPPING_TEXT = (
    "input_role",
    "source_relative_path",
    "contrast_column",
    "contrast_numerator",
    "contrast_denominator",
    "analysis_method",
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


def test_phase_6_2_manifest_example_files_exist() -> None:
    assert MANIFEST_DIR.is_dir()
    for filename in REQUIRED_FILES:
        assert (MANIFEST_DIR / filename).is_file()


def test_phase_6_2_manifest_json_files_parse() -> None:
    for path in MANIFEST_DIR.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_phase_6_2_manifest_endpoint_selection_includes_required_endpoints() -> None:
    payload = json.loads(
        (MANIFEST_DIR / "openapi_endpoint_selection.json").read_text(encoding="utf-8")
    )
    endpoints = {
        (item["method"].upper(), item["path"])
        for item in payload["endpoints"]
    }

    for endpoint in REQUIRED_ENDPOINTS:
        assert endpoint in endpoints


def test_phase_6_2_manifest_field_mapping_includes_required_fields() -> None:
    text = (MANIFEST_DIR / "coze_tool_field_mapping.json").read_text(
        encoding="utf-8"
    )

    for required_text in REQUIRED_FIELD_MAPPING_TEXT:
        assert required_text in text


def test_phase_6_2_manifest_files_do_not_expose_forbidden_fragments() -> None:
    for path in MANIFEST_DIR.iterdir():
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for forbidden_fragment in FORBIDDEN_FRAGMENTS:
            assert forbidden_fragment not in text
