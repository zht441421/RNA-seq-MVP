from fastapi.testclient import TestClient

from backend.app.main import app


def test_ui_contains_artifact_review_and_warning_messages() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    assert "Artifact Review" in response.text
    assert "Validation Issues" in response.text
    assert "当前证据不足以支持强科研结论。" in response.text
    assert "主分析已完成，但存在方法学 warning，请谨慎解释结果。" in response.text
