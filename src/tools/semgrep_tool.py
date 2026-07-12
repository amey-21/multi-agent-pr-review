import subprocess
import json
import tempfile
import os
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers, write_to_temp_file



@tool
def run_semgrep(code_patch: str) -> str:
    """
    Runs Semgrep static analysis on a code patch to find security vulnerabilities.
    Use this to detect: SQL injection, XSS, path traversal, insecure deserialization,
    hardcoded credentials, and other OWASP Top 10 vulnerabilities.
    
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
        # Step 2: run semgrep as a subprocess
        result = subprocess.run(
            [
                "semgrep",
                "--config=p/security-audit",   # use semgrep's default ruleset
                "--json",          # structured output we can parse
                "--quiet",         # suppress progress messages
                tmp_path
            ],
            capture_output=True,
            text=True,
            timeout=30,             # never hang forever
            stdin=subprocess.DEVNULL   # explicitly disconnect from parent's stdin
        )
        
        # Step 3: parse the JSON output
        if result.stdout:
            findings = json.loads(result.stdout)
            results = findings.get("results", [])
            
            if not results:
                return "No security vulnerabilities detected by Semgrep."
            
            # Step 4: format findings as readable text for the LLM
            output_lines = [f"Semgrep found {len(results)} issue(s):\n"]
            
            for finding in results:
                severity = finding.get("extra", {}).get("severity", "UNKNOWN")
                message  = finding.get("extra", {}).get("message", "No message")
                line_num = finding.get("start", {}).get("line", "?")
                rule_id  = finding.get("check_id", "unknown-rule")
                
                output_lines.append(
                    f"[{severity}] Line {line_num}: {message}\n"
                    f"  Rule: {rule_id}\n"
                )
            
            return "\n".join(output_lines)
        
        return "Semgrep produced no output."
    
    except subprocess.TimeoutExpired:
        return "Semgrep timed out file may be too large."
    except json.JSONDecodeError:
        return f"Could not parse Semgrep output: {result.stdout[:200]}"
    finally:
        # Step 5: always clean up temp file
        # 'finally' runs even if an exception occurred above
        os.unlink(tmp_path)