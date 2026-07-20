from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/runtime/r-deseq2-runtime.json"
APPLICATION_ROOT = ROOT
REQUIRED_PACKAGES = (
    "DESeq2",
    "SummarizedExperiment",
    "S4Vectors",
    "IRanges",
    "BiocGenerics",
    "BiocManager",
    "BiocVersion",
)
COMMAND_TIMEOUT_SECONDS = 20
R_VERSION = re.compile(r"(?:Rscript\s+\(R\)\s+version|R\s+version)\s+([0-9]+(?:\.[0-9]+){1,3})", re.I)
R_QUERY = """
suppressPackageStartupMessages({
  library(DESeq2)
  library(SummarizedExperiment)
  library(S4Vectors)
  library(IRanges)
  library(BiocGenerics)
  library(BiocManager)
  library(BiocVersion)
})
cat("BIOCONDUCTOR\\t", as.character(BiocManager::version()), "\\n", sep="")
for (pkg in c("DESeq2", "SummarizedExperiment", "S4Vectors", "IRanges", "BiocGenerics", "BiocManager", "BiocVersion")) {
  cat("PACKAGE\\t", pkg, "\\t", as.character(packageVersion(pkg)), "\\n", sep="")
}
for (path in .libPaths()) cat("LIBRARY\\t", path, "\\n", sep="")
cat(
  "IDENTITY\\t",
  system2("/usr/bin/id", "-u", stdout=TRUE),
  "\\t",
  system2("/usr/bin/id", "-g", stdout=TRUE),
  "\\n",
  sep=""
)
""".strip()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Runtime version manifest must be an object.")
    return value


def run_command(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
            shell=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


def _version_from(completed: subprocess.CompletedProcess[str] | None) -> str | None:
    if completed is None or completed.returncode != 0:
        return None
    match = R_VERSION.search("\n".join((completed.stdout or "", completed.stderr or "")))
    return match.group(1) if match else None


def _r_details(
    completed: subprocess.CompletedProcess[str] | None,
) -> tuple[dict[str, str], str | None, list[str], tuple[int, int] | None]:
    packages: dict[str, str] = {}
    bioconductor = None
    libraries: list[str] = []
    identity: tuple[int, int] | None = None
    if completed is None or completed.returncode != 0:
        return packages, bioconductor, libraries, identity
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) == 2 and fields[0] == "BIOCONDUCTOR":
            bioconductor = fields[1]
        elif len(fields) == 3 and fields[0] == "PACKAGE":
            packages[fields[1]] = fields[2]
        elif len(fields) == 2 and fields[0] == "LIBRARY":
            libraries.append(fields[1])
        elif len(fields) == 3 and fields[0] == "IDENTITY":
            try:
                identity = (int(fields[1]), int(fields[2]))
            except ValueError:
                identity = None
    return packages, bioconductor, libraries, identity


def _directory_writable(path: Path, *, create: bool = False) -> bool:
    try:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="phase-8-6-1-", dir=path, delete=True):
            return True
    except OSError:
        return False


def probe_runtime(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    r_path = shutil.which("R")
    rscript_path = shutil.which("Rscript")
    r_result = run_command(["R", "--version"]) if r_path else None
    rscript_result = run_command(["Rscript", "--version"]) if rscript_path else None
    query_result = run_command(["Rscript", "--vanilla", "-e", R_QUERY]) if rscript_path else None
    packages, bioconductor, libraries, rscript_identity = _r_details(query_result)
    r_version = _version_from(r_result)
    rscript_version = _version_from(rscript_result)
    expected_packages = {"DESeq2": manifest["deseq2_version"], "BiocManager": manifest["biocmanager_version"], **manifest["required_packages"]}
    package_checks = {
        package: {
            "loaded": package in packages,
            "version": packages.get(package),
            "expected_version": expected,
            "matches": packages.get(package) == expected,
        }
        for package, expected in expected_packages.items()
    }
    output_root = Path(os.environ.get("BIOINFO_OUTPUT_ROOT", ROOT / ".staging-runtime/phase-8-6-1-probe"))
    state_path = Path(os.environ.get("BIOINFO_TASK_STORE_PATH", output_root / "state/tasks.sqlite3"))
    temporary_writable = _directory_writable(Path(tempfile.gettempdir()))
    workspace_writable = _directory_writable(output_root, create=True)
    database_directory_writable = _directory_writable(state_path.parent, create=True)
    library_permissions = {path: os.access(path, os.W_OK) for path in libraries}
    uid = os.getuid() if hasattr(os, "getuid") else None
    gid = os.getgid() if hasattr(os, "getgid") else None
    checks = {
        "r_version_matches": r_version == manifest["r_version"],
        "rscript_version_matches": rscript_version == manifest["rscript_version"],
        "bioconductor_version_matches": bioconductor == manifest["bioconductor_version"],
        "required_packages_match": bool(package_checks) and all(item["loaded"] and item["matches"] for item in package_checks.values()),
        "runtime_user_non_root": uid not in (None, 0),
        "rscript_identity_matches_application": rscript_identity == (uid, gid),
        "temporary_directory_writable": temporary_writable,
        "task_workspace_writable": workspace_writable,
        "database_directory_writable": database_directory_writable,
        "application_source_writable": os.access(APPLICATION_ROOT, os.W_OK),
        "r_libraries_writable": any(library_permissions.values()),
        "package_installation_attempted": False,
        "package_installation_required": False,
    }
    ready = bool(
        all(checks[name] for name in (
            "r_version_matches", "rscript_version_matches", "bioconductor_version_matches",
            "required_packages_match", "runtime_user_non_root", "temporary_directory_writable",
            "rscript_identity_matches_application",
            "task_workspace_writable", "database_directory_writable",
        ))
        and not checks["application_source_writable"]
        and not checks["r_libraries_writable"]
    )
    return {
        "schema_version": "1.0",
        "ready": ready,
        "executables": {"R": r_path, "Rscript": rscript_path},
        "versions": {
            "R": r_version,
            "Rscript": rscript_version,
            "Bioconductor": bioconductor,
            "packages": packages,
        },
        "required_package_checks": package_checks,
        "identity": {
            "uid": uid,
            "gid": gid,
            "rscript_uid": rscript_identity[0] if rscript_identity else None,
            "rscript_gid": rscript_identity[1] if rscript_identity else None,
        },
        "runtime_paths": {
            "application_root": str(APPLICATION_ROOT),
            "r_libraries": libraries,
        },
        "library_permissions": library_permissions,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the fixed Phase 8.6.1 R/DESeq2 runtime.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = probe_runtime()
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        result = {"schema_version": "1.0", "ready": False, "error": "Runtime probe could not validate the frozen contract."}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Phase 8.6.1 R/DESeq2 runtime ready: {str(result.get('ready') is True).lower()}")
        versions = result.get("versions", {})
        print(f"R: {versions.get('R') or 'unavailable'}")
        print(f"Rscript: {versions.get('Rscript') or 'unavailable'}")
        print(f"Bioconductor: {versions.get('Bioconductor') or 'unavailable'}")
        print(f"DESeq2: {(versions.get('packages') or {}).get('DESeq2') or 'unavailable'}")
    return 0 if result.get("ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
