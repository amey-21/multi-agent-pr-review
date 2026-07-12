from src.github.models import AgentResult, Finding, ReviewReport

# Explicit ordering — lower number = higher priority = shown first
SEVERITY_RANK = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


def merge_and_rank_findings(agent_results: list[AgentResult]) -> list[Finding]:
    """
    Deterministic merge: flatten all agents' findings into one list,
    sort by severity (CRITICAL first, LOW last). No LLM involved —
    this is pure, predictable Python logic, appropriate since ranking
    doesn't require semantic judgment, just a fixed ordering rule.
    """
    all_findings = []
    for result in agent_results:
        all_findings.extend(result.findings)

    # sort() with a key function — SEVERITY_RANK.get(finding.severity, 99)
    # the .get(..., 99) fallback protects against an unexpected severity
    # string that isn't in our dict, pushing it to the end rather than crashing
    all_findings.sort(key=lambda f: SEVERITY_RANK.get(f.severity, 99))

    return all_findings


def build_review_report(agent_results: list[AgentResult]) -> ReviewReport:
    """
    Assembles the final ReviewReport from all four agents' results.
    Counting and sorting are deterministic; only the top-level summary
    text could optionally involve an LLM (we'll keep it simple/deterministic 
    for now and revisit if needed).
    """
    ranked_findings = merge_and_rank_findings(agent_results)

    critical_count = sum(1 for f in ranked_findings if f.severity == "CRITICAL")
    high_count = sum(1 for f in ranked_findings if f.severity == "HIGH")
    medium_count = sum(1 for f in ranked_findings if f.severity == "MEDIUM")
    low_count = sum(1 for f in ranked_findings if f.severity == "LOW")

    agent_summaries = {
        result.agent_name: result.summary for result in agent_results
    }

    summary = (
        f"Reviewed PR across {len(agent_results)} dimensions "
        f"(security, performance, test coverage, docs). "
        f"Found {len(ranked_findings)} total finding(s): "
        f"{critical_count} critical, {high_count} high, "
        f"{medium_count} medium, {low_count} low severity."
    )

    return ReviewReport(
        total_findings=len(ranked_findings),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        findings=ranked_findings,
        summary=summary,
        agent_summaries=agent_summaries,
    )