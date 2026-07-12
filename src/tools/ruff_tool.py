import subprocess
import json
import tempfile
import os
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers, write_to_temp_file



@tool
def run_ruff(code_patch: str) -> str:
    """
    Runs Ruff linter to detect code quality issues, unused imports,
    undefined variables, style violations, and common bug patterns.
    Use this to check general code quality and catch likely bugs.
    
    Args:
        code_patch: The code or diff text to analyze
        
    Returns:
        String describing all findings, or confirmation of no issues
    """

    clean_code = strip_diff_markers(code_patch)
    tmp_path = write_to_temp_file(clean_code)

    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", tmp_path],
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL   # explicitly disconnect from parent's stdin
        )

        if not result.stdout.strip():
            return "No issues detected by Ruff."

        issues = json.loads(result.stdout)
        if not issues:
            return "No issues detected by Ruff."

        output_lines = [f"Ruff found {len(issues)} issue(s):\n"]
        for issue in issues:
            code = issue.get("code", "?")
            message = issue.get("message", "")
            line_num = issue.get("location", {}).get("row", "?")
            output_lines.append(f"[{code}] Line {line_num}: {message}")

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "Ruff timed out."
    except json.JSONDecodeError:
        return f"Could not parse Ruff output: {result.stdout[:200]}"
    finally:
        os.unlink(tmp_path)