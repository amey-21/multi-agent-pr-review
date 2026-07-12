from langchain_openai import ChatOpenAI
from src.tools.test_coverage_heuristic import detect_missing_tests
from src.github.models import AgentResult, AgentFindings
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)  


SYNTHESIS_PROMPT = """You are a test coverage review assistant. Below are 
raw findings from a heuristic tool that checks whether newly added 
functions have a correspondingly named test function in the same PR.

Your job is NOT to find new issues. Your job is ONLY to read the existing 
findings and convert them into the structured format requested.

IMPORTANT: This tool uses NAMING CONVENTIONS ONLY (e.g. function 
'calculate_discount' should have a test named 'test_calculate_discount').
It does NOT actually run any tests or measure real code coverage. It 
will have false positives (a test exists but has a different name, e.g. 
parametrized tests) and false negatives (a test name matches but doesn't 
actually exercise the function properly). 

For each flagged function, create one Finding with:
- severity: always MEDIUM at most for this tool (never HIGH or CRITICAL) 
  since this is a naming heuristic, not verified missing coverage
- line: null (this tool does not track line numbers)
- file: the filename where the untested function was found
- description: state which function appears to lack a test, and 
  explicitly note this is based on naming convention, not verified 
  execution
- rule_id: null
- remediation: suggest adding a test named 'test_<function_name>' or 
  confirming coverage exists under a different test name

If the tool output says all functions have matching tests, or says "No 
new functions detected," return an empty findings list and say so 
clearly in the summary.

If the tool output shows "[TOOL_CRASHED] ... failed", do NOT create a Finding 
from it. Instead mention in the summary that this check did not run.

Raw tool output:
{raw_output}
"""


async def run_test_agent(patch_text: str) -> AgentResult:
    try:
        missing_tests_output = await detect_missing_tests.ainvoke({"patch_text": patch_text})
    except Exception as e:
        missing_tests_output = f"[TOOL_CRASHED] Missing tests detector failed: {str(e)}"

    raw_combined = f"=== MISSING TESTS HEURISTIC ===\n{missing_tests_output}"

    structured_llm = llm.with_structured_output(AgentFindings)
    prompt = SYNTHESIS_PROMPT.format(raw_output=raw_combined)
    result: AgentFindings = await structured_llm.ainvoke(prompt)

    return AgentResult(
        agent_name="test_coverage",
        findings=result.findings,
        raw_tool_output=raw_combined,
        summary=result.summary,
    )