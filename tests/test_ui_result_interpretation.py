from fastapi.testclient import TestClient

from backend.app.main import app


def test_ui_contains_result_interpretation_guarded_language() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    assert "Result Interpretation" in response.text
    assert "Top candidate statistical signals" in response.text
    assert "12_interpretation_summary.md" in response.text
    assert "Top biological findings" not in response.text
