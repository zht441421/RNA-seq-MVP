from pathlib import Path
from typing import Union

from backend.app.config import get_settings


def resolve_input_path(file_path: Union[str, Path]) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return get_settings().project_root / path


def ensure_project_storage(project_id: str, category: str) -> Path:
    target = get_settings().storage_dir / "projects" / project_id / category
    target.mkdir(parents=True, exist_ok=True)
    return target


def safe_filename(name: str) -> str:
    allowed = []
    for char in name:
        if char.isalnum() or char in {".", "-", "_"}:
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed).strip("._") or "file"

