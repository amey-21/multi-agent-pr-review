from langchain_openai import ChatOpenAI
from src.tools.docstring_checker import check_docstring_presence
from src.tools.pydocstyle_tool import run_pydocstyle
from src.github.models import AgentResult, AgentFindings
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

SYNTHESIS_PROMPT = """You are a documentation review assistant. Below are 
raw findings from two tools: an AST-based docstring presence checker, and 
pydocstyle (a PEP 257 style checker). 

For MISSING docstrings and STYLE violations, your job is ONLY to convert 
the existing findings into structured format — do not invent new 
findings beyond what these two tools reported.

HOWEVER, for functions/classes that DO have a docstring (shown under 
"EXISTING DOCSTRINGS" in the tool output), you must ALSO judge the 
QUALITY of each docstring yourself, since no tool can do this:
- Does the docstring accurately describe what the function name and 
  signature suggest it does?
- Is it too vague to be useful (e.g. "does stuff", "helper function")?
- Only flag a docstring as a quality issue if it is genuinely vague, 
  misleading, or unhelpful — do not nitpick good docstrings just to 
  find something to say.

For each finding, create one Finding with:
- severity: MEDIUM for missing docstrings on public functions, LOW for 
  style violations, MEDIUM for genuinely poor-quality existing docstrings
- line: extract the line number if present, else null
- file: null if not available
- description: clear explanation of the issue
- rule_id: the tool's error code if present (e.g. pydocstyle's D-codes), 
  else null for quality judgments you made yourself
- remediation: a suggested improved docstring or fix

If a tool section shows "[TOOL_CRASHED] <tool> failed: ...", do NOT create a 
Finding from it. Instead mention in the summary that this check did not 
run.

If no issues were found, return an empty findings list and say so in 
the summary.

Raw tool output:
{raw_output}
"""


async def run_docs_agent(patch_text: str) -> AgentResult:
    try:
        presence_output = await check_docstring_presence.ainvoke({"code_patch": patch_text})
    except Exception as e:
        presence_output = f"[TOOL_CRASHED] Docstring presence check failed: {str(e)}"

    try:
        style_output = await run_pydocstyle.invoke({"code_patch": patch_text})
    except Exception as e:
        style_output = f"[TOOL_CRASHED] pydocstyle failed: {str(e)}"

    raw_combined = (
        f"=== DOCSTRING PRESENCE CHECK ===\n{presence_output}\n\n"
        f"=== PYDOCSTYLE ===\n{style_output}"
    )

    structured_llm = llm.with_structured_output(AgentFindings)
    prompt = SYNTHESIS_PROMPT.format(raw_output=raw_combined)
    result: AgentFindings = await structured_llm.ainvoke(prompt)

    return AgentResult(
        agent_name="docs",
        findings=result.findings,
        raw_tool_output=raw_combined,
        summary=result.summary,
    )