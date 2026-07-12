import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from src.webhook.app import app
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.webhook.app import run_review_pipeline

client = TestClient(app)

SECRET = "test_secret_123"

def make_signature(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def test_rejects_invalid_signature():
    payload = {"action": "opened", "repository": {"full_name": "test/repo"}, 
               "pull_request": {"number": 1}}
    body = json.dumps(payload).encode()
    
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=invalid_signature_here",
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json"
        }
    )
    print(f"\nInvalid signature response: {response.status_code}")
    assert response.status_code == 401


def test_accepts_valid_signature(monkeypatch):
    # temporarily override the secret the app checks against
    monkeypatch.setattr("src.webhook.app.WEBHOOK_SECRET", SECRET)
    
    payload = {
        "action": "opened",
        "repository": {"full_name": "test/repo"},
        "pull_request": {"number": 1}
    }
    body = json.dumps(payload).encode()
    valid_sig = make_signature(body, SECRET)

    response = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": valid_sig,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json"
        }
    )
    print(f"\nValid signature response: {response.status_code} {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "review scheduled"


@pytest.mark.asyncio
async def test_pipeline_posts_comment_on_success():
    """
    Verifies that a successful pipeline run actually calls
    post_review_comment with the formatted report — not just that
    the graph ran, but that the RESULT reaches GitHub.
    """
    mock_report = MagicMock()
    mock_report.total_findings = 2
    mock_report.summary = "Test summary"
    mock_report.findings = []

    with patch("src.webhook.app.build_review_graph") as mock_build_graph, \
         patch("src.webhook.app.GitHubClient") as mock_client_class:

        # simulate the graph returning a final_report
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={"final_report": mock_report}
        )
        mock_build_graph.return_value = mock_graph

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        await run_review_pipeline("test/repo", 42)

        # the real assertion: did we actually try to post a comment?
        mock_client_instance.post_review_comment.assert_called_once()
        call_args = mock_client_instance.post_review_comment.call_args
        assert call_args[0][0] == "test/repo"
        assert call_args[0][1] == 42


@pytest.mark.asyncio
async def test_pipeline_logs_failure_without_crashing(caplog):
    """
    Verifies the try/except in run_review_pipeline actually catches
    a failure and logs it — this directly tests the fix for the
    'GitHub never knows' silent-failure problem we designed against.
    """
    with patch("src.webhook.app.build_review_graph") as mock_build_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Simulated crash"))
        mock_build_graph.return_value = mock_graph

        # this should NOT raise — the whole point is it's caught internally
        await run_review_pipeline("test/repo", 42)

        assert "FAILED" in caplog.text
        assert "Simulated crash" in caplog.text


if __name__ == "__main__":
    test_rejects_invalid_signature()
    print("✅ Invalid signature correctly rejected")