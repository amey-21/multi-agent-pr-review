import subprocess
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers, write_to_temp_file
import os


@tool
def run_pydocstyle(code_patch: str) -> str:
    """
    Runs pydocstyle to check docstring FORMAT against PEP 257 conventions
    (e.g. missing periods, incorrect capitalization, wrong quote style).
    This checks STYLE only, not whether the docstring content is accurate
    or useful.

    Args:
        code_patch: The code or diff text to analyze

    Returns:
        String describing style violations, or confirmation of no issues
    """
    clean_code = strip_diff_markers(code_patch)
    tmp_path = write_to_temp_file(clean_code)

    try:
        result = subprocess.run(
            ["pydocstyle", tmp_path],
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL   # explicitly disconnect from parent's stdin
        )

        if not result.stdout.strip():
            return "No docstring style violations detected."

        # Parse and filter output rather than returning it raw.
        # pydocstyle output alternates: a location line, then an
        # indented "CODE: message" line
        lines = result.stdout.strip().split('\n')
        filtered_findings = []
        current_location = None

        for line in lines:
            if line.strip().startswith(("D1", "D2", "D3", "D4")):
                # this is a rule violation line
                # D100 = "Missing docstring in public module" —
                # always a false positive on our temp-file fragments,
                # since these are never real standalone modules
                if "D100" in line:
                    continue

                # strip the leaked filesystem path, keep only line number
                # current_location looks like:
                # "C:\...\tmpXXXX.py:7 in public function `add`:"
                if current_location:
                    # extract just ":7 in public function `add`:" part
                    # by splitting on the temp file path
                    _, _, remainder = current_location.rpartition(tmp_path)
                    filtered_findings.append(f"{remainder.strip()} {line.strip()}")
            else:
                current_location = line

        if not filtered_findings:
            return "No docstring style violations detected."

        return "pydocstyle violations found:\n" + "\n".join(filtered_findings)

    except subprocess.TimeoutExpired:
        return "pydocstyle timed out."
    except FileNotFoundError:
        return "[ERROR] pydocstyle is not installed or not on PATH."
    finally:
        os.unlink(tmp_path)