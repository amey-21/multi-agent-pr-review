import os
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, requests
from src.github.app_auth import get_installation_token
from src.webhook.verify import verify_github_signature
from src.graph.workflow import build_review_graph
from src.github.client import GitHubClient
from pathlib import Path

# configure basic logging so background task failures are actually
# visible somewhere, not silently swallowed — this directly addresses
# the observability gap we discussed before writing any code
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook")

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")
# if not GITHUB_APP_PRIVATE_KEY:
#     key_path = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH")
#     if key_path:
#         GITHUB_APP_PRIVATE_KEY = Path(key_path).read_text(encoding="utf-8")


async def run_review_pipeline(repo_name: str, pr_number: int, installation_id: str):
    """
    The actual background work: runs the full LangGraph pipeline and
    posts the result as a PR comment. This function runs AFTER the
    webhook endpoint has already returned 200 OK to GitHub — so any
    exception here needs to be caught and logged HERE, since nothing
    downstream will ever see it otherwise.
    """
    try:
        logger.info(f"Starting review for {repo_name}#{pr_number}")

        # NEW: get a fresh, short-lived installation token instead of
        # using a personal access token — scoped only to what this
        # specific installation permitted
        try:
            token = get_installation_token(
                app_id=GITHUB_APP_ID,
                private_key=GITHUB_APP_PRIVATE_KEY,
                installation_id=installation_id,
            )
        except requests.HTTPError as e:
            logger.error(f"Failed to get installation token for {repo_name}#{pr_number}: {e}")
            return  # can't proceed without a valid token — stop here,
                     # but the failure is at least LOGGED, not silent

        graph = build_review_graph()
        initial_state = {
            "repo_name": repo_name,
            "pr_number": pr_number,
            "github_token": token,
            "pr_diff": None,
            "patch_text": None,
            "security_result": None,
            "performance_result": None,
            "test_result": None,
            "docs_result": None,
            "final_report": None,
        }

        final_state = await graph.ainvoke(initial_state)
        report = final_state["final_report"]

        # post the report back to GitHub as a PR comment
        client = GitHubClient(token=token)
        comment_text = format_report_as_comment(report)
        client.post_review_comment(repo_name, pr_number, comment_text)

        logger.info(f"Review completed for {repo_name}#{pr_number}: "
                    f"{report.total_findings} finding(s)")

    except Exception as e:
        # THIS is the fix for the silent-failure problem we discussed.
        # Without this except block, a crash here would vanish with
        # zero trace — GitHub already has its 200 OK, nobody else 
        # is watching this coroutine.
        logger.error(
            f"Review pipeline FAILED for {repo_name}#{pr_number}: {e}",
            exc_info=True
        )


def format_report_as_comment(report) -> str:
    """
    Converts a ReviewReport into GitHub-flavored markdown for posting
    as a PR comment. Simple string formatting — deterministic, no LLM
    needed here either, same principle as the Supervisor's summary.
    """
    lines = [
        f"## 🤖 Automated PR Review",
        f"",
        f"{report.summary}",
        f"",
    ]

    if report.findings:
        lines.append("### Findings\n")
        for f in report.findings:
            location = f" (line {f.line})" if f.line else ""
            lines.append(f"**[{f.severity}]**{location} {f.description}")
            if f.remediation:
                lines.append(f"> 💡 {f.remediation}")
            lines.append("")

    return "\n".join(lines)


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(raw_body, signature, WEBHOOK_SECRET):
        logger.warning("Webhook signature verification FAILED — rejecting request")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")
    action = payload.get("action")

    if event_type == "pull_request" and action in ("opened", "synchronize", "reopened"):
        repo_name = payload["repository"]["full_name"]
        pr_number = payload["pull_request"]["number"]
        installation_id = payload["installation"]["id"]   # NEW

        background_tasks.add_task(
            run_review_pipeline, repo_name, pr_number, installation_id  # NEW arg
        )

        return {"status": "review scheduled", "repo": repo_name, "pr": pr_number}

    return {"status": "ignored", "event": event_type, "action": action}