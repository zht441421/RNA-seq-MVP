from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app
from backend.app.runners.r_env_checker import REnvironmentChecker


def test_r_env_checker_handles_missing_rscript() -> None:
    result = REnvironmentChecker(rscript_executable="definitely_missing_Rscript_for_env_test").check()

    assert result["r_available"] is False
    assert result["ready_for_real_r"] is False
    assert "DESeq2" in result["missing_required"]
    assert result["packages"]["DESeq2"]["installed"] is False
    assert result["error"]


def test_system_r_env_endpoint_returns_structured_missing_rscript_result() -> None:
    settings = get_settings()
    old_rscript = settings.rscript_executable
    settings.rscript_executable = "definitely_missing_Rscript_for_api_env_test"
    try:
        client = TestClient(app)
        response = client.get("/system/r-env")
    finally:
        settings.rscript_executable = old_rscript

    assert response.status_code == 200
    payload = response.json()
    assert payload["r_available"] is False
    assert payload["ready_for_real_r"] is False
    assert payload["missing_required"]

