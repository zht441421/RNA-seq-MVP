import json
import subprocess

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app
from backend.app.runners.docker_r_env_checker import DockerREnvironmentChecker


def test_docker_env_checker_handles_missing_docker() -> None:
    result = DockerREnvironmentChecker(docker_executable="definitely_missing_docker_for_env_test").check()

    assert result["docker_available"] is False
    assert result["image_available"] is False
    assert result["ready_for_docker_r"] is False
    assert result["errors"]


def test_system_docker_r_env_endpoint_returns_structured_missing_docker_result() -> None:
    settings = get_settings()
    old_docker = settings.docker_executable
    settings.docker_executable = "definitely_missing_docker_for_api_env_test"
    try:
        response = TestClient(app).get("/system/docker-r-env")
    finally:
        settings.docker_executable = old_docker

    assert response.status_code == 200
    payload = response.json()
    assert payload["docker_available"] is False
    assert payload["ready_for_docker_r"] is False
    assert payload["errors"]


def test_docker_env_checker_handles_missing_image(monkeypatch) -> None:
    def fake_run(command, capture_output, text, check):
        if command[:2] == ["docker", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="24.0.0", stderr="")
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="No such image")
        raise AssertionError(command)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = DockerREnvironmentChecker(docker_executable="docker", image_name="missing:latest").check()

    assert result["docker_available"] is True
    assert result["image_available"] is False
    assert result["ready_for_docker_r"] is False
    assert "missing:latest" in result["errors"][0]


def test_docker_env_checker_parses_container_r_result(monkeypatch) -> None:
    payload = {
        "r_available": True,
        "r_version": "4.4.0",
        "packages": {
            "DESeq2": {"installed": True, "version": "1.44.0"},
            "edgeR": {"installed": True, "version": "4.2.0"},
            "limma": {"installed": True, "version": "3.60.0"},
            "ggplot2": {"installed": True, "version": "3.5.0"},
            "pheatmap": {"installed": True, "version": "1.0.12"},
            "jsonlite": {"installed": True, "version": "1.8.8"},
            "readr": {"installed": True, "version": "2.1.5"},
        },
    }

    def fake_run(command, capture_output, text, check):
        if command[:2] == ["docker", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="24.0.0", stderr="")
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 0, stdout="[]", stderr="")
        if command[:3] == ["docker", "run", "--rm"]:
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = DockerREnvironmentChecker(docker_executable="docker", image_name="ready:latest").check()

    assert result["docker_available"] is True
    assert result["image_available"] is True
    assert result["r_available_in_container"] is True
    assert result["ready_for_docker_r"] is True
    assert result["packages"]["DESeq2"]["version"] == "1.44.0"
