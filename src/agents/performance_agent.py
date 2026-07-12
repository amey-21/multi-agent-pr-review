from langchain_openai import ChatOpenAI
from src.tools.ruff_tool import run_ruff
from src.tools.radon_tool import run_radon_complexity
from src.tools.n_plusone_detector import detect_n_plus_one
from src.github.models import AgentFindings, AgentResult
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

SYNTHESIS_PROMPT = """You are a code performance review assistant. Below 
are raw findings from three analysis tools: Ruff (linting), Radon 
(cyclomatic complexity), and a custom N+1 query pattern detector.

Your job is NOT to find new issues. Your job is ONLY to read these 
existing findings and convert them into the structured format requested.

For each distinct issue found, create one Finding with:
- severity: normalize to exactly one of CRITICAL, HIGH, MEDIUM, LOW
  (high complexity rank D/E/F = HIGH, rank C = MEDIUM, ruff style 
  issues = LOW unless they indicate an actual bug)
- line: extract the line number if present, else null
- description: a clear one-sentence explanation
- rule_id: the tool's rule identifier if present, else null
- remediation: a brief suggested fix if you can infer one, else null

The N+1 detector is a HEURISTIC — it may have false positives. When 
including its findings, set severity to MEDIUM at most (never HIGH or 
CRITICAL) and mention in the description that this should be manually 
verified.

If a tool section shows "[TOOL_CRASHED] <tool> failed: ...", do NOT create a 
Finding from it. Instead, mention in the summary that this tool did not 
run and the scan may be incomplete for that category.

If no issues were found by any tool, return an empty findings list and 
say so in the summary.

Raw tool output:
{raw_output}
"""


async def run_performance_agent(patch_text: str) -> AgentResult:
    try:
        ruff_output = await run_ruff.ainvoke({"code_patch": patch_text})
    except Exception as e:
        ruff_output = f"[TOOL_CRASHED] Ruff failed: {str(e)}"

    try:
        radon_output = await run_radon_complexity.ainvoke({"code_patch": patch_text})
    except Exception as e:
        radon_output = f"[TOOL_CRASHED] Radon failed: {str(e)}"

    try:
        nplus1_output = await detect_n_plus_one.ainvoke({"code_patch": patch_text})
    except Exception as e:
        nplus1_output = f"[TOOL_CRASHED] N+1 detector failed: {str(e)}"

    raw_combined = (
        f"=== RUFF ===\n{ruff_output}\n\n"
        f"=== RADON COMPLEXITY ===\n{radon_output}\n\n"
        f"=== N+1 DETECTOR ===\n{nplus1_output}"
    )

    structured_llm = llm.with_structured_output(AgentFindings)
    prompt = SYNTHESIS_PROMPT.format(raw_output=raw_combined)
    result: AgentFindings = await structured_llm.ainvoke(prompt)

    return AgentResult(
        agent_name="performance",
        findings=result.findings,
        raw_tool_output=raw_combined,
        summary=result.summary,
    )