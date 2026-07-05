from fastapi.testclient import TestClient

from backend.app.main import app


def test_ui_contains_reproducibility_artifact_names() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    assert "08_reproducible_code/README_REPRODUCE.md" in response.text
    assert "08_reproducible_code/analysis_config.json" in response.text
    assert "08_reproducible_code/run_command.txt" in response.text
    assert "08_reproducible_code/docker_command.txt" in response.text
    assert "08_reproducible_code/input_hashes.json" in response.text
    assert "08_reproducible_code/software_versions.json" in response.text
