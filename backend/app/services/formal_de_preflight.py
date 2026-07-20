import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


FORMAL_METHOD = "deseq2"
DESEQ2_UNAVAILABLE_LIMITATION = (
    "DESeq2 execution is not available until R, Rscript, BiocManager, and DESeq2 are installed."
)
_COMMAND_TIMEOUT_SECONDS = 20
_CONTROLLED_RUNTIME_TIMEOUT_SECONDS = 30
_CONTROLLED_RUNTIME_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts/r/deseq2_runtime_preflight.R"
)
_REQUIRED_R_PACKAGES = (
    "DESeq2",
    "SummarizedExperiment",
    "S4Vectors",
    "IRanges",
    "BiocGenerics",
    "BiocManager",
    "BiocVersion",
)
_SAFE_EXECUTABLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_SAFE_R_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.]*$")
_R_VERSION_RE = re.compile(
    r"(?:Rscript\s+\(R\)\s+version|R\s+version)\s+([0-9]+(?:\.[0-9]+){1,3})",
    re.IGNORECASE,
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>|]+")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?:(?:/home|/mnt)/[^\s\"'<>|]+)")
_FORBIDDEN_WORD_RE = re.compile(r"\b(traceback|token|password|secret)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def check_executable_available(name: str) -> bool:
    if not _SAFE_EXECUTABLE_RE.fullmatch(str(name or "")):
        return False
    return shutil.which(name) is not None


def run_command_safely(
    args: list[str],
    timeout_seconds: int = _COMMAND_TIMEOUT_SECONDS,
    working_directory: Path | None = None,
) -> CommandResult:
    if not _valid_command_args(args):
        return CommandResult(
            args=[],
            returncode=None,
            error="Invalid command arguments.",
        )

    safe_args = [_sanitize_public_text(arg) for arg in args]
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            shell=False,
            cwd=str(working_directory) if working_directory is not None else None,
        )
    except FileNotFoundError:
        return CommandResult(
            args=safe_args,
            returncode=None,
            error="Command executable was not found.",
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            args=safe_args,
            returncode=None,
            timed_out=True,
            error="Command timed out.",
        )
    except OSError:
        return CommandResult(
            args=safe_args,
            returncode=None,
            error="Command could not be executed.",
        )

    return CommandResult(
        args=safe_args,
        returncode=completed.returncode,
        stdout=_sanitize_public_text(completed.stdout or ""),
        stderr=_sanitize_public_text(completed.stderr or ""),
    )


def parse_r_version(output: str) -> str | None:
    match = _R_VERSION_RE.search(str(output or ""))
    return match.group(1) if match else None


def check_r_package_available(package_name: str) -> bool:
    if not _SAFE_R_PACKAGE_RE.fullmatch(str(package_name or "")):
        return False

    expression = (
        f'if (requireNamespace("{package_name}", quietly = TRUE)) '
        "quit(status = 0) else quit(status = 1)"
    )
    result = run_command_safely(
        ["Rscript", "--vanilla", "-e", expression],
        timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
    )
    return result.returncode == 0


def check_controlled_runtime_script() -> tuple[bool, dict[str, str]]:
    if not _CONTROLLED_RUNTIME_SCRIPT.is_file():
        return False, {}
    result = run_command_safely(
        ["Rscript", "--vanilla", str(_CONTROLLED_RUNTIME_SCRIPT)],
        timeout_seconds=_CONTROLLED_RUNTIME_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return False, {}
    versions: dict[str, str] = {}
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) == 2 and fields[0] == "BIOCONDUCTOR":
            versions["Bioconductor"] = fields[1]
        elif len(fields) == 3 and fields[0] == "PACKAGE":
            versions[fields[1]] = fields[2]
    return all(name in versions for name in _REQUIRED_R_PACKAGES), versions


def check_runtime_directories_writable() -> bool:
    configured_output = os.environ.get("BIOINFO_OUTPUT_ROOT", "").strip()
    output_root = (
        Path(configured_output)
        if configured_output
        else Path(__file__).resolve().parents[3] / "data/outputs"
    )
    return _directory_writable(output_root) and _directory_writable(
        Path(tempfile.gettempdir())
    )


def check_frozen_runtime_versions(versions: dict[str, str]) -> bool:
    manifest_value = os.environ.get("BIOINFO_R_RUNTIME_MANIFEST", "").strip()
    if not manifest_value:
        return True
    try:
        manifest = json.loads(Path(manifest_value).read_text(encoding="utf-8"))
        expected = {
            "Bioconductor": manifest["bioconductor_version"],
            "BiocManager": manifest["biocmanager_version"],
            "DESeq2": manifest["deseq2_version"],
            **manifest["required_packages"],
        }
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False
    return all(versions.get(name) == value for name, value in expected.items())


def run_deseq2_preflight() -> dict:
    commands_checked: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    r_available = check_executable_available("R")
    rscript_available = check_executable_available("Rscript")
    r_version = None
    rscript_version = None
    biocmanager_available = False
    deseq2_available = False
    required_dependencies_available = False
    controlled_runtime_ready = False
    writable_runtime_directories = False
    frozen_versions_match = False

    if r_available:
        commands_checked.append("R --version")
        r_version_result = run_command_safely(["R", "--version"])
        r_version = parse_r_version(
            "\n".join([r_version_result.stdout, r_version_result.stderr])
        )
        if r_version_result.returncode != 0 or r_version is None:
            warnings.append("R is available but its version could not be confirmed.")
    else:
        errors.append("R executable is not available.")

    if rscript_available:
        commands_checked.append("Rscript --version")
        rscript_version_result = run_command_safely(["Rscript", "--version"])
        rscript_version = parse_r_version(
            "\n".join([rscript_version_result.stdout, rscript_version_result.stderr])
        )
        if rscript_version_result.returncode != 0 or rscript_version is None:
            warnings.append("Rscript is available but its version could not be confirmed.")

        commands_checked.append('Rscript --vanilla -e requireNamespace("BiocManager")')
        biocmanager_available = check_r_package_available("BiocManager")
        if not biocmanager_available:
            errors.append("BiocManager R package is not available.")

        commands_checked.append('Rscript --vanilla -e requireNamespace("DESeq2")')
        deseq2_available = check_r_package_available("DESeq2")
        if not deseq2_available:
            errors.append("DESeq2 R package is not available.")
        required_dependencies_available = all(
            check_r_package_available(package)
            for package in _REQUIRED_R_PACKAGES
            if package not in {"BiocManager", "DESeq2"}
        )
        if not required_dependencies_available:
            errors.append("A required DESeq2 dependency is not available.")
        commands_checked.append("Rscript controlled DESeq2 runtime preflight script")
        controlled_runtime_ready, runtime_versions = check_controlled_runtime_script()
        if not controlled_runtime_ready:
            errors.append("The controlled DESeq2 runtime preflight script failed.")
        frozen_versions_match = check_frozen_runtime_versions(runtime_versions)
        if not frozen_versions_match:
            errors.append("The containerized R runtime does not match its frozen version contract.")
        writable_runtime_directories = check_runtime_directories_writable()
        if not writable_runtime_directories:
            errors.append("A required runtime working directory is not writable.")
    else:
        errors.append("Rscript executable is not available.")

    ready = bool(
        r_available
        and rscript_available
        and biocmanager_available
        and deseq2_available
        and required_dependencies_available
        and controlled_runtime_ready
        and frozen_versions_match
        and writable_runtime_directories
    )

    return {
        "r_available": r_available,
        "rscript_available": rscript_available,
        "r_version": r_version,
        "rscript_version": rscript_version,
        "biocmanager_available": biocmanager_available,
        "deseq2_available": deseq2_available,
        "formal_method": FORMAL_METHOD,
        "ready": ready,
        "checked_at": _checked_at(),
        "commands_checked": commands_checked,
        "warnings": warnings,
        "errors": errors,
        "limitations": _preflight_limitations(ready),
    }


def _preflight_limitations(ready: bool) -> list[str]:
    limitations = [
        "This preflight only checks local environment readiness for future DESeq2 execution.",
        "No DESeq2 differential expression analysis is run.",
        "No p-values, adjusted p-values, q-values, or statistical significance labels are produced.",
        "No R or Bioconductor packages are installed, updated, or modified.",
    ]
    if not ready:
        limitations.append(DESEQ2_UNAVAILABLE_LIMITATION)
    return limitations


def _valid_command_args(args: object) -> bool:
    return (
        isinstance(args, list)
        and bool(args)
        and all(isinstance(arg, str) and arg for arg in args)
    )


def _sanitize_public_text(value: object) -> str:
    text = str(value or "")
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("[redacted-path]", text)
    text = _POSIX_ABSOLUTE_PATH_RE.sub("[redacted-path]", text)
    text = _FORBIDDEN_WORD_RE.sub("redacted", text)
    return text


def _checked_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="deseq2-preflight-", dir=path, delete=True
        ):
            return True
    except OSError:
        return False
