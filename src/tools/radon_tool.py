import subprocess
import json
import tempfile
import os
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers, write_to_temp_file



@tool
def run_radon_complexity(code_patch: str) -> str:
    """
    Measures cyclomatic complexity of functions using Radon.
    Use this to detect overly complex functions that are hard to 
    test and maintain. High complexity (rank D, E, F) indicates 
    a function doing too much and should likely be split up.
    
    Args:
        code_patch: The code or diff text to analyze
        
    Returns:
        String listing complexity scores per function
    """
    # with tempfile.NamedTemporaryFile(
    #     mode='w', suffix='.py', delete=False, encoding='utf-8'
    # ) as tmp:
    #     clean_lines = []
    #     for line in code_patch.split('\n'):
    #         if line.startswith('+') and not line.startswith('+++'):
    #             clean_lines.append(line[1:])
    #         elif line.startswith('-') and not line.startswith('---'):
    #             pass
    #         elif not line.startswith('@@'):
    #             clean_lines.append(line)
    #     tmp.write('\n'.join(clean_lines))
    #     tmp_path = tmp.name

    clean_code = strip_diff_markers(code_patch)
    tmp_path = write_to_temp_file(clean_code)

    try:
        result = subprocess.run(
            ["radon", "cc", tmp_path, "-j"],
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL   # explicitly disconnect from parent's stdin
        )

        if not result.stdout.strip():
            return "No functions found to analyze."

        data = json.loads(result.stdout)
        functions = data.get(tmp_path, [])

        if not functions:
            return "No functions found to analyze."

        # radon ranks: A (simple) -> F (very complex)
        # we only care about C and worse for flagging
        concerning = [f for f in functions if f.get("rank", "A") in ("C", "D", "E", "F")]

        if not concerning:
            return f"Analyzed {len(functions)} function(s). All within acceptable complexity (rank A/B)."

        output_lines = [f"Radon found {len(concerning)} function(s) with high complexity:\n"]
        for func in concerning:
            name = func.get("name", "?")
            rank = func.get("rank", "?")
            complexity = func.get("complexity", "?")
            line_num = func.get("lineno", "?")
            output_lines.append(
                f"[Rank {rank}] Line {line_num}: '{name}' has complexity {complexity} "
                f"(consider breaking this function into smaller pieces)"
            )

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "Radon timed out."
    except json.JSONDecodeError:
        return f"Could not parse Radon output: {result.stdout[:200]}"
    finally:
        os.unlink(tmp_path)