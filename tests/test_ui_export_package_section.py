from fastapi.testclient import TestClient

from backend.app.main import app


def test_ui_contains_export_package_section() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    assert "Export Package" in response.text
    assert "Create Export Package" in response.text
    assert "export_package" in response.text

