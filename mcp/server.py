import os
import sys

# add project root to sys.path so we can import from src/
# this is necessary because this script may be launched by Claude
# Desktop from a different working directory than your project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
venv_scripts_dir = os.path.dirname(sys.executable)
os.environ["PATH"] = venv_scripts_dir + os.pathsep + os.environ.get("PATH", "")

# print("PATH seen by MCP server process:", os.environ.get("PATH", "NOT SET"), file=sys.stderr)

from mcp.server.fastmcp import FastMCP
from src.graph.workflow import build_review_graph
from src.agents.security_agent import run_security_agent
from src.github.client import GitHubClient
from src.graph.workflow import build_review_graph_no_fetch
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

# FastMCP is a high-level helper that handles the MCP protocol
# plumbing for you — similar to how FastAPI hides raw HTTP handling
mcp = FastMCP("pr-review-agents")


@mcp.tool()
async def review_pr(repo_name: str, pr_number: int) -> str:
    """
    Runs the full multi-agent review pipeline (security, performance,
    test coverage, docs) on a GitHub Pull Request and returns a
    formatted summary of all findings.
    
    Args:
        repo_name: GitHub repository in "owner/repo" format, 
                   e.g. "octocat/Hello-World"
        pr_number: the PR number to review
    """
    graph = build_review_graph()
    initial_state = {
        "repo_name": repo_name,
        "pr_number": pr_number,
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

    # MCP tools must return STRINGS — same rule as your LangChain
    # @tool functions back in Milestone 2. This isn't a coincidence:
    # both protocols exist to let an LLM consume the result, and 
    # LLMs only understand text.
    lines = [report.summary, ""]
    for f in report.findings:
        location = f" (line {f.line})" if f.line else ""
        lines.append(f"[{f.severity}]{location} {f.description}")

    return "\n".join(lines)


@mcp.tool()
async def check_security(code_snippet: str) -> str:
    """
    Runs ONLY the Security Agent (Semgrep, Bandit, secret scanning)
    on a pasted code snippet, without needing a real GitHub PR.
    Useful for quickly checking a piece of code before committing it.
    
    Args:
        code_snippet: raw Python code to scan for security issues
    """
    result = await run_security_agent(code_snippet)
    lines = [result.summary, ""]
    for f in result.findings:
        lines.append(f"[{f.severity}] {f.description}")
    return "\n".join(lines)


@mcp.tool()
async def review_file(code: str, filename: str = "file.py") -> str:
    """
    Runs the full multi-agent review pipeline (security, performance,
    test coverage, docs) on a single pasted file's contents, without
    needing a real GitHub PR. Useful for reviewing a file before 
    committing it.
    
    Args:
        code: the full source code to review
        filename: optional filename for context in the report
    """
    graph = build_review_graph_no_fetch()
    initial_state = {
        "repo_name": "local",
        "pr_number": 0,
        "pr_diff": None,
        "patch_text": f"### File: {filename}\n{code}",
        "security_result": None,
        "performance_result": None,
        "test_result": None,
        "docs_result": None,
        "final_report": None,
    }

    final_state = await graph.ainvoke(initial_state)
    report = final_state["final_report"]

    lines = [report.summary, ""]
    for f in report.findings:
        location = f" (line {f.line})" if f.line else ""
        lines.append(f"[{f.severity}]{location} {f.description}")

    return "\n".join(lines)


@mcp.tool()
async def explain_finding(finding_description: str, code_context: str = "") -> str:
    """
    Explains a security/quality finding in plain, beginner-friendly 
    English, including why it matters and the general risk it poses.
    Use this when a finding's technical description needs to be 
    translated for someone less experienced with the specific issue.
    
    Args:
        finding_description: the technical finding text to explain
        code_context: optional surrounding code for better context
    """
    prompt = f"""Explain this code review finding in plain, simple 
English for a junior developer who may not be familiar with the 
specific vulnerability or issue category. Explain WHAT the issue is, 
WHY it matters (what could go wrong), and keep it to 3-4 sentences.

Finding: {finding_description}

{"Code context:\n" + code_context if code_context else ""}
"""
    # NOTE: plain .ainvoke() with NO with_structured_output() — 
    # we want prose here, not a Pydantic object, per the reasoning
    # above: the only consumer is a human reading this in their IDE
    response = await llm.ainvoke(prompt)
    return response.content


@mcp.tool()
async def suggest_fix(finding_description: str, code_context: str) -> str:
    """
    Suggests a code fix for a specific finding, given the relevant
    code context. Returns a plain-text explanation plus a suggested
    code snippet, NOT an automatically-applied diff.
    
    Args:
        finding_description: the finding to fix
        code_context: the actual code that needs fixing
    """
    prompt = f"""Given this code review finding and the relevant code, 
suggest a specific fix. Show the corrected code and briefly explain 
what changed and why.

Finding: {finding_description}

Current code:
{code_context}
"""
    response = await llm.ainvoke(prompt)
    return response.content


if __name__ == "__main__":
    # this starts the server listening on stdio, waiting for
    # Claude Desktop (or any MCP client) to connect and start
    # sending protocol messages
    mcp.run()