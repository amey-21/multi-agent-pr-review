from pydantic import BaseModel
from typing import List

class FileChange(BaseModel):
    """
    Represents a single file that was changed in the PR.
    
    Why Pydantic BaseModel?
    - Automatically validates data types
    - Gives us .dict() and .json() methods for free
    - Documents exactly what fields exist and their types
    """
    filename: str           # e.g. "src/auth/login.py"
    status: str             # "added", "modified", "removed"
    additions: int          # number of lines added
    deletions: int          # number of lines deleted
    patch: str | None       # the actual diff text (None if binary file)


class PRDiff(BaseModel):
    """
    Everything our agents need to know about a Pull Request.
    This is the INPUT to our entire multi-agent system.
    """
    pr_number: int          # e.g. 42
    pr_title: str           # e.g. "Fix SQL injection in user auth"
    repo_name: str          # e.g. "amey/my-project"
    author: str             # GitHub username of PR author
    base_branch: str        # branch being merged INTO (usually "main")
    head_branch: str        # branch with the new changes
    description: str        # PR body text
    files: List[FileChange] # all files changed
    max_chars: int = 100_000    # max chars to send to AI agents (default 100k)

    def get_patch_text(self, max_chars: int = 100_000) -> str:
        """
        Combines all file patches into one text block.
        This is what we'll feed to the AI agents.
        """
        parts = []
        for f in self.files:
            if f.patch:  # skip binary files
                parts.append(f"### File: {f.filename}\n{f.patch}")
        full_text = "\n\n".join(parts)
        return full_text[:max_chars]  # truncate if too long

class Finding(BaseModel):
    """
    A single issue discovered by any agent.
    This is the UNIVERSAL shape all 4 agents (security, perf, 
    test, docs) will use so the Supervisor can compare/rank
    findings from different agents using the same fields.
    """
    severity: str          # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    line: int | None       # line number, if known
    file: str | None       # filename, if known
    description: str       # human-readable explanation
    rule_id: str | None    # e.g. "python.lang.security...", for traceability
    remediation: str | None  # suggested fix, if the LLM can produce one


class AgentFindings(BaseModel):
    """
    Wrapper model — this is literally the schema we hand to LLM
    for structured output. LLM must return exactly this shape.
    """
    findings: List[Finding]
    summary: str           # one-paragraph overview for humans


class AgentResult(BaseModel):
    """
    What every agent returns to the Supervisor node eventually.
    Keeping raw_tool_output lets us debug/audit later 
    never throw away the original evidence.
    """
    agent_name: str
    findings: List[Finding]
    raw_tool_output: str
    summary: str


class ReviewReport(BaseModel):
    """
    The FINAL output of the entire multi-agent system what actually
    gets posted as a GitHub PR comment. This is what the Supervisor
    node produces after merging all four agents' findings.
    """
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    findings: List[Finding]       # deduplicated, ranked
    summary: str                  # human-readable overview
    agent_summaries: dict         # {"security": "...", "performance": "...", ...}