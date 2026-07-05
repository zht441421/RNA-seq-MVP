import json
import subprocess
from typing import Any, Dict, Optional

from backend.app.config import get_settings


REQUIRED_R_PACKAGES = ["DESeq2", "jsonlite", "readr"]
OPTIONAL_R_PACKAGES = ["edgeR", "limma", "ggplot2", "pheatmap"]
ALL_R_PACKAGES = ["DESeq2", "edgeR", "limma", "ggplot2", "pheatmap", "jsonlite", "readr"]


class REnvironmentChecker:
    def __init__(self, rscript_executable: Optional[str] = None) -> None:
        settings = get_settings()
        self.rscript_executable = rscript_executable or settings.rscript_executable
        self.script_path = settings.project_root / "backend" / "app" / "scripts" / "r" / "check_bioconductor_env.R"

    def check(self) -> Dict[str, Any]:
        command = [self.rscript_executable, str(self.script_path)]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            return unavailable_result(
                rscript_executable=self.rscript_executable,
                error=f"Rscript executable was not found: {self.rscript_executable}",
                stderr=str(exc),
            )

        if completed.returncode != 0:
            return unavailable_result(
                rscript_executable=self.rscript_executable,
                error="R environment check script failed.",
                stderr=completed.stderr,
                stdout=completed.stdout,
                returncode=completed.returncode,
            )

        try:
            result = json.loads((completed.stdout or "").strip())
        except json.JSONDecodeError as exc:
            return unavailable_result(
                rscript_executable=self.rscript_executable,
                error=f"R environment check returned invalid JSON: {exc}",
                stderr=completed.stderr,
                stdout=completed.stdout,
                returncode=completed.returncode,
            )

        result.setdefault("r_available", True)
        result.setdefault("packages", {})
        result.setdefault("missing_required", _missing(result["packages"], REQUIRED_R_PACKAGES))
        result.setdefault("missing_optional", _missing(result["packages"], OPTIONAL_R_PACKAGES))
        result["ready_for_real_r"] = bool(result.get("ready_for_real_r")) and not result["missing_required"]
        result["rscript_executable"] = self.rscript_executable
        result["stdout"] = completed.stdout
        result["stderr"] = completed.stderr
        result["returncode"] = completed.returncode
        return result


def unavailable_result(
    rscript_executable: str,
    error: str,
    stderr: str = "",
    stdout: str = "",
    returncode: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "r_available": False,
        "r_version": None,
        "packages": {
            package_name: {"installed": False, "version": None}
            for package_name in ALL_R_PACKAGES
        },
        "ready_for_real_r": False,
        "missing_required": REQUIRED_R_PACKAGES,
        "missing_optional": OPTIONAL_R_PACKAGES,
        "rscript_executable": rscript_executable,
        "error": error,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
    }


def _missing(packages: Dict[str, Any], package_names: list[str]) -> list[str]:
    missing = []
    for package_name in package_names:
        package_info = packages.get(package_name) or {}
        if not package_info.get("installed"):
            missing.append(package_name)
    return missing

