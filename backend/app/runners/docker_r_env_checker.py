import json
import subprocess
from typing import Any, Dict, Optional

from backend.app.config import get_settings
from backend.app.runners.r_env_checker import ALL_R_PACKAGES, OPTIONAL_R_PACKAGES, REQUIRED_R_PACKAGES


class DockerREnvironmentChecker:
    def __init__(
        self,
        docker_executable: Optional[str] = None,
        image_name: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.docker_executable = docker_executable or settings.docker_executable
        self.image_name = image_name or settings.docker_r_image

    def check(self) -> Dict[str, Any]:
        docker_available = self._docker_available()
        if not docker_available["available"]:
            return unavailable_docker_result(
                docker_executable=self.docker_executable,
                image_name=self.image_name,
                error=docker_available["error"],
            )

        image_available = self._image_available()
        if not image_available["available"]:
            return unavailable_image_result(
                docker_executable=self.docker_executable,
                image_name=self.image_name,
                error=image_available["error"],
                stderr=image_available.get("stderr", ""),
            )

        command = [
            self.docker_executable,
            "run",
            "--rm",
            self.image_name,
            "Rscript",
            "/opt/bioinformatics-agent/scripts/check_bioconductor_env.R",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return unavailable_container_r_result(
                docker_executable=self.docker_executable,
                image_name=self.image_name,
                error="Docker R environment check failed.",
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )

        try:
            r_payload = json.loads((completed.stdout or "").strip())
        except json.JSONDecodeError as exc:
            return unavailable_container_r_result(
                docker_executable=self.docker_executable,
                image_name=self.image_name,
                error=f"Docker R environment check returned invalid JSON: {exc}",
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )

        packages = r_payload.get("packages", {})
        missing_required = _missing(packages, REQUIRED_R_PACKAGES)
        missing_optional = _missing(packages, OPTIONAL_R_PACKAGES)
        return {
            "docker_available": True,
            "image_available": True,
            "image_name": self.image_name,
            "r_available_in_container": bool(r_payload.get("r_available")),
            "r_version": r_payload.get("r_version"),
            "packages": packages,
            "ready_for_docker_r": bool(r_payload.get("r_available")) and not missing_required,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "errors": [],
            "docker_executable": self.docker_executable,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }

    def _docker_available(self) -> Dict[str, Any]:
        try:
            completed = subprocess.run(
                [self.docker_executable, "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return {"available": False, "error": f"Docker executable was not found: {self.docker_executable}", "stderr": str(exc)}
        if completed.returncode != 0:
            return {"available": False, "error": "Docker is not available.", "stderr": completed.stderr}
        return {"available": True}

    def _image_available(self) -> Dict[str, Any]:
        completed = subprocess.run(
            [self.docker_executable, "image", "inspect", self.image_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return {
                "available": False,
                "error": f"Docker image is not available: {self.image_name}",
                "stderr": completed.stderr,
            }
        return {"available": True}


def unavailable_docker_result(docker_executable: str, image_name: str, error: str) -> Dict[str, Any]:
    return {
        "docker_available": False,
        "image_available": False,
        "image_name": image_name,
        "r_available_in_container": False,
        "packages": _empty_packages(),
        "ready_for_docker_r": False,
        "missing_required": REQUIRED_R_PACKAGES,
        "missing_optional": OPTIONAL_R_PACKAGES,
        "errors": [error],
        "docker_executable": docker_executable,
    }


def unavailable_image_result(docker_executable: str, image_name: str, error: str, stderr: str = "") -> Dict[str, Any]:
    return {
        "docker_available": True,
        "image_available": False,
        "image_name": image_name,
        "r_available_in_container": False,
        "packages": _empty_packages(),
        "ready_for_docker_r": False,
        "missing_required": REQUIRED_R_PACKAGES,
        "missing_optional": OPTIONAL_R_PACKAGES,
        "errors": [error],
        "stderr": stderr,
        "docker_executable": docker_executable,
    }


def unavailable_container_r_result(
    docker_executable: str,
    image_name: str,
    error: str,
    stdout: str = "",
    stderr: str = "",
    returncode: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "docker_available": True,
        "image_available": True,
        "image_name": image_name,
        "r_available_in_container": False,
        "packages": _empty_packages(),
        "ready_for_docker_r": False,
        "missing_required": REQUIRED_R_PACKAGES,
        "missing_optional": OPTIONAL_R_PACKAGES,
        "errors": [error],
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
        "docker_executable": docker_executable,
    }


def _empty_packages() -> Dict[str, Dict[str, Any]]:
    return {package_name: {"installed": False, "version": None} for package_name in ALL_R_PACKAGES}


def _missing(packages: Dict[str, Any], package_names: list[str]) -> list[str]:
    missing = []
    for package_name in package_names:
        package_info = packages.get(package_name) or {}
        if not package_info.get("installed"):
            missing.append(package_name)
    return missing

