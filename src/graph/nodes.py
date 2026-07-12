import os
from src.graph.state import ReviewState
from src.github.client import GitHubClient
from src.agents.security_agent import run_security_agent
from src.agents.performance_agent import run_performance_agent
from src.agents.test_agent import run_test_agent
from src.agents.docs_agent import run_docs_agent
from src.graph.supervisor import build_review_report


def fetch_pr_node(state: ReviewState) -> dict:
    """
    First node in the graph. Fetches the PR diff from GitHub and
    prepares patch_text for the agents.
    
    NOTICE: this returns a PARTIAL dict — only the keys this node
    is responsible for setting. LangGraph merges this into the
    full state, it doesn't replace the whole state.
    """
    client = GitHubClient(token=state["github_token"])
    pr_diff = client.get_pr_diff(state["repo_name"], state["pr_number"])

    return {
        "pr_diff": pr_diff,
        "patch_text": pr_diff.get_patch_text(),
    }


async def security_node(state: ReviewState) -> dict:
    """
    Runs the Security Agent. This function has NO idea that three
    other agent nodes are running at the same time — it just reads
    patch_text from state and writes its own result key. LangGraph
    handles the concurrency, not this function.
    """
    result = await run_security_agent(state["patch_text"])
    return {"security_result": result}


async def performance_node(state: ReviewState) -> dict:
    result = await run_performance_agent(state["patch_text"])
    return {"performance_result": result}


async def test_node(state: ReviewState) -> dict:
    result = await run_test_agent(state["patch_text"])
    return {"test_result": result}


async def docs_node(state: ReviewState) -> dict:
    result = await run_docs_agent(state["patch_text"])
    return {"docs_result": result}


def supervisor_node(state: ReviewState) -> dict:
    """
    Runs AFTER all four agent nodes complete (LangGraph's fan-in
    ensures this waits for all of them). Reads their results from
    state and produces the final merged ReviewReport.
    """
    agent_results = [
        state["security_result"],
        state["performance_result"],
        state["test_result"],
        state["docs_result"],
    ]
    report = build_review_report(agent_results)
    return {"final_report": report}