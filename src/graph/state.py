from typing import TypedDict, Optional
from src.github.models import PRDiff, AgentResult, ReviewReport


class ReviewState(TypedDict):
    """
    The shared object that flows through every node in the graph.
    
    WHY TypedDict instead of a Pydantic BaseModel here?
    LangGraph's engine needs to know exactly which keys exist and
    merge partial updates from parallel nodes automatically.
    TypedDict is LangGraph's expected format for state — it's a
    plain dict with type hints, not a validated class like Pydantic.
    Each node returns a PARTIAL dict (only the keys it's updating),
    and LangGraph merges it into the full state automatically.
    """
    repo_name: str
    pr_number: int
    github_token: Optional[str] 
    pr_diff: Optional[PRDiff]
    patch_text: Optional[str]

    # each agent writes to its OWN key — this is the fix for the
    # race condition we just discussed
    security_result: Optional[AgentResult]
    performance_result: Optional[AgentResult]
    test_result: Optional[AgentResult]
    docs_result: Optional[AgentResult]

    final_report: Optional[ReviewReport]