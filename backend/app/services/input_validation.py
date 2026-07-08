import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath


ALLOWED_RNASEQ_INPUT_SUFFIXES = {".csv", ".tsv", ".txt"}
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_INPUT_ROOT = _REPO_ROOT / "data" / "inputs"


@dataclass(frozen=True)
class InputFileValidationResult:
    original_path: str
    resolved_path: Path | None
    exists: bool
    suffix: str
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RNASeqInputValidationResult:
    metadata: InputFileValidationResult
    count_matrix: InputFileValidationResult
    valid: bool
    errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def get_input_root() -> Path:
    configured_root = os.environ.get("BIOINFO_INPUT_ROOT", "").strip()
    root = Path(configured_root) if configured_root else _DEFAULT_INPUT_ROOT
    return root.expanduser().resolve(strict=False)


def resolve_input_path(relative_path: str) -> Path:
    errors = _path_safety_errors(relative_path)
    if errors:
        raise ValueError("; ".join(errors))

    input_root = get_input_root()
    resolved_path = (input_root / relative_path).resolve(strict=False)
    if not _is_relative_to(resolved_path, input_root):
        raise ValueError("Resolved path escapes input root.")
    return resolved_path


def validate_input_file(
    relative_path: str,
    allowed_suffixes: set[str],
) -> InputFileValidationResult:
    normalized_allowed_suffixes = {suffix.lower() for suffix in allowed_suffixes}
    suffix = _path_suffix(relative_path)
    safety_errors = _path_safety_errors(relative_path)
    errors = list(safety_errors)

    if suffix not in normalized_allowed_suffixes:
        allowed = ", ".join(sorted(normalized_allowed_suffixes))
        errors.append(f"Unsupported file suffix: {suffix or '<none>'}. Allowed suffixes: {allowed}.")

    resolved_path: Path | None = None
    exists = False
    if not safety_errors:
        input_root = get_input_root()
        resolved_path = (input_root / relative_path).resolve(strict=False)
        if not _is_relative_to(resolved_path, input_root):
            errors.append("Resolved path escapes input root.")
        else:
            exists = resolved_path.is_file()
            if not exists:
                errors.append("File does not exist under input root.")

    return InputFileValidationResult(
        original_path=relative_path,
        resolved_path=resolved_path,
        exists=exists,
        suffix=suffix,
        valid=not errors,
        errors=errors,
    )


def validate_rnaseq_input_files(
    metadata_file: str,
    count_matrix_file: str,
) -> RNASeqInputValidationResult:
    metadata = validate_input_file(
        metadata_file,
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )
    count_matrix = validate_input_file(
        count_matrix_file,
        allowed_suffixes=ALLOWED_RNASEQ_INPUT_SUFFIXES,
    )
    errors = [
        *(f"metadata_file: {error}" for error in metadata.errors),
        *(f"count_matrix_file: {error}" for error in count_matrix.errors),
    ]
    limitations = [
        "This validation checks file path safety, allowed suffixes, and file existence only.",
        "This validation does not parse metadata or count matrix contents.",
        "This validation does not run QC, differential expression, enrichment analysis, or any RNA-seq computation.",
        "This validation does not create report files, artifact files, execution logs, or database records.",
    ]

    return RNASeqInputValidationResult(
        metadata=metadata,
        count_matrix=count_matrix,
        valid=metadata.valid and count_matrix.valid,
        errors=errors,
        limitations=limitations,
    )


def _path_safety_errors(relative_path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(relative_path, str) or not relative_path.strip():
        return ["Path must be a non-empty relative path."]

    if "\x00" in relative_path:
        errors.append("Path must not contain null bytes.")

    if _is_absolute_path(relative_path):
        errors.append("Absolute paths are not allowed.")

    if _has_path_traversal(relative_path):
        errors.append("Path traversal is not allowed.")

    return errors


def _is_absolute_path(path_value: str) -> bool:
    posix_path = PurePosixPath(path_value.replace("\\", "/"))
    windows_path = PureWindowsPath(path_value)
    return bool(
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or Path(path_value).is_absolute()
    )


def _has_path_traversal(path_value: str) -> bool:
    posix_path = PurePosixPath(path_value.replace("\\", "/"))
    return ".." in posix_path.parts


def _path_suffix(path_value: str) -> str:
    if not isinstance(path_value, str) or "\x00" in path_value:
        return ""
    return PurePosixPath(path_value.replace("\\", "/").strip()).suffix.lower()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
