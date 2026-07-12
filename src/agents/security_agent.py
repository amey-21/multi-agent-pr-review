from langchain_openai import ChatOpenAI
from src.tools.semgrep_tool import run_semgrep
from src.tools.secret_scanner import scan_secrets
from src.tools.bandit_tool import run_bandit
from src.github.models import AgentResult, AgentFindings, Finding
from dotenv import load_dotenv

load_dotenv()

# temperature=0 → deterministic, less "creative" output
# critical for security findings we don't want the LLM 
# inventing severity levels differently each run

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)  

SYNTHESIS_PROMPT = """You are a security review assistant. Below are raw 
findings from three static analysis tools: Semgrep, a custom secret 
scanner, and Bandit.

Your job is NOT to find new issues. Your job is ONLY to read these 
existing findings and convert them into the structured format requested.

For each distinct issue found, create one Finding with:
- severity: normalize to exactly one of CRITICAL, HIGH, MEDIUM, LOW

IMPORTANT — SEVERITY OVERRIDE RULE: The calibration guide below takes 
ABSOLUTE PRECEDENCE over any severity label reported by the underlying 
tool. If a tool's finding matches one of these categories, you MUST use 
the calibration guide's severity and IGNORE the tool's own stated 
severity level entirely — even if the raw tool output explicitly says 
something like "Severity: MEDIUM" or uses a WARNING/ERROR/INFO label 
that conflicts with this guide.

IMPORTANT — INDEPENDENT SEVERITY RULE: Judge each finding's severity 
completely INDEPENDENTLY of the other findings in this batch. Do NOT 
rank findings relative to each other (e.g. do not treat a finding as 
"less severe" just because a CRITICAL finding also happens to be present 
in the same report). Each finding's severity must be determined SOLELY 
by the calibration guide category it matches — apply the guide the same 
way whether this finding is the only one in the report or one of many.

Severity calibration (overrides tool-reported severity):
- CRITICAL: hardcoded secrets/credentials, remote code execution risks
- HIGH: SQL injection, command injection, insecure deserialization, 
  authentication/authorization bypass
- MEDIUM: weak cryptography (e.g. MD5, weak SSL versions), insecure 
  defaults that require specific conditions to exploit
- LOW: informational findings, minor hardening suggestions

- line: extract the line number if present, else null
- description: a clear one-sentence explanation
- rule_id: the tool's rule identifier if present, else null
- remediation: a brief suggested fix if you can infer one, else null

If multiple tools flagged the SAME issue on the SAME line, merge them 
into ONE finding rather than duplicating. When merging, use the HIGHEST 
severity among the calibration-guide-derived severities, never an average.

If a tool section shows "[TOOL_CRASHED] <tool> failed: ...", this means 
that tool crashed and did NOT run successfully. Do NOT create a Finding 
from this error text — it is not a security issue, it is a tool failure. 
Instead, mention in the summary that this tool did not run and the scan 
may be incomplete for that category of checks.

If no issues were found by any tool, return an empty findings list and 
say so in the summary.

Raw tool output:
{raw_output}
"""

# Known rule IDs (or rule ID substrings) that ALWAYS map to a specific
# severity, regardless of what the LLM infers. This is deterministic —
# these facts don't change based on context, so they don't belong in
# the LLM's judgment path. Keyed by substring match since tool rule IDs
# can vary slightly (e.g. Bandit test IDs vs Semgrep dotted rule paths).
SEVERITY_OVERRIDES = {
    "B608": "HIGH",                          # Bandit: hardcoded SQL expressions
    "sql-injection": "HIGH",                  # Semgrep rule paths containing this
    "sqlalchemy-execute-raw-query": "HIGH",   # Semgrep SQLAlchemy raw query rule
    "formatted-sql-query": "HIGH",            # Semgrep formatted SQL query rule
    "B105": "MEDIUM",                          # Bandit: hardcoded password string
    "B301": "MEDIUM",                          # Bandit: pickle deserialization
    "B324": "MEDIUM",                          # Bandit: weak hash (MD5 etc.)
}


def apply_severity_overrides(findings: list[Finding]) -> list[Finding]:
    """
    Post-processes LLM-generated findings, forcing severity to a known
    value when the finding's rule_id matches a known pattern. This runs
    AFTER structured output, correcting any batch-relative bias the LLM
    introduced during synthesis — see the SQL injection MEDIUM-vs-HIGH
    investigation for why this exists.
    """
    for finding in findings:
        if not finding.rule_id:
            continue
        for pattern, forced_severity in SEVERITY_OVERRIDES.items():
            if pattern in finding.rule_id:
                finding.severity = forced_severity
                break
    return findings

async def run_security_agent(patch_text: str) -> AgentResult:
    """
    Deterministic security pipeline:
    1. ALWAYS run all three tools no LLM decision involved here
    2. Combine raw outputs
    3. Use LLM ONLY to structure/deduplicate the combined findings

    This is intentionally NOT an autonomous agent loop.
    We chose forced tool execution because missed security 
    checks are unacceptable see Milestone 3 discussion.
    """

    # Step 1: force every tool to run, every time
    try:
        semgrep_output = await run_semgrep.ainvoke({"code_patch": patch_text})
    except Exception as e:
        semgrep_output = f"[TOOL_CRASHED] Semgrep failed: {str(e)}"
    try:
        secrets_output = await scan_secrets.ainvoke({"code_patch": patch_text})
    except Exception as e:
        secrets_output = f"[TOOL_CRASHED] Secret scanner failed: {str(e)}"
    try:
        bandit_output = await run_bandit.ainvoke({"code_patch": patch_text})
    except Exception as e:
        bandit_output = f"[TOOL_CRASHED] Bandit failed: {str(e)}"


    raw_combined = (
        f"=== SEMGREP ===\n{semgrep_output}\n\n"
        f"=== SECRET SCANNER ===\n{secrets_output}\n\n"
        f"=== BANDIT ===\n{bandit_output}"
    )

    # Step 2: force the LLM's output into our Pydantic schema
    # with_structured_output() handles the tool_use mechanics for us
    structured_llm = llm.with_structured_output(AgentFindings)
    prompt = SYNTHESIS_PROMPT.format(raw_output=raw_combined)
    result: AgentFindings = await structured_llm.ainvoke(prompt)

    corrected_findings = apply_severity_overrides(result.findings)

    return AgentResult(
        agent_name="security",
        findings=corrected_findings,
        raw_tool_output=raw_combined,
        summary=result.summary,
    )