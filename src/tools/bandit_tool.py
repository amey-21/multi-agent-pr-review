import subprocess
import json
import tempfile
import os
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers, write_to_temp_file

#  Bandit is a Python security linter. Install it with pip install bandit 
# and wrap it exactly like semgrep. The command is bandit -f json - and 
# it reads from stdin instead of a file

@tool
def run_bandit(code_patch: str) -> str:
    """
    Runs Bandit static analysis on a code patch to find security vulnerabilities.
    Use this to detect: security vulnerabilities and insecure coding practices in Python code.

    Args:
        code_patch: The code or diff text to analyze
    
    Returns:
        String describing all findings, or confirmation of no issues found
    
    WHY THIS DOCSTRING MATTERS:
    The LLM reads this docstring to decide WHEN to call this tool.
    A vague docstring = agent calls it at wrong times.
    A clear docstring = agent knows exactly when to use it.
    """

    clean_code = strip_diff_markers(code_patch)
    tmp_path = write_to_temp_file(clean_code)

    try:
        # Step 2: run bandit as a subprocess
        result = subprocess.run(
            [
                "bandit",
                "-f", "json",  # output in JSON format
                "-r", tmp_path  # recursively scan the temp file
            ],
            capture_output=True,
            text=True,
            timeout=30,  # seconds
            stdin=subprocess.DEVNULL   # explicitly disconnect from parent's stdin
        )

        if not result.stdout.strip():
            error_message = result.stderr.strip() or "Bandit produced no output."
            return f"Bandit scan failed: {error_message}"

        # Step 3: Parse Bandit's JSON output
        findings = json.loads(result.stdout)
        results = findings.get("results", [])

        if not results:
            return "No security issues found by Bandit."

        # Step 4: Format findings
        output_lines = [f'Bandit found {len(results)} issue(s):\n']

        for issue in results:
            output_lines.append(
                f"Severity: {issue['issue_severity']}, "
                f"Line: {issue['line_number']}, "
                f"Issue: {issue['issue_text']}, \n"
                f"Message: {issue.get('more_info', 'No additional info')}"
            )

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "Bandit scan timed out after 30 seconds."

    except json.JSONDecodeError:
        return f"Failed to parse Bandit output: {result.stdout}"

    except Exception as e:
        return f"Bandit scan failed: {str(e)}"
