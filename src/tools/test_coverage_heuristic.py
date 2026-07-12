import ast
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers


class FunctionCollector(ast.NodeVisitor):
    """
    Walks an AST and collects the names of top-level and class-method
    function definitions. We separately track which ones LOOK like
    test functions (start with 'test_') versus regular functions.
    """

    def __init__(self):
        self.regular_functions = []   # e.g. "calculate_discount"
        self.test_functions = []      # e.g. "test_calculate_discount"

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name.startswith("test_"):
            self.test_functions.append(node.name)
        else:
            # skip dunder methods and private helpers (leading underscore)
            # these are rarely unit-tested directly
            if not node.name.startswith("_"):
                self.regular_functions.append(node.name)
        self.generic_visit(node)  # keep walking (handles nested functions)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # async def functions are a DIFFERENT AST node type than
        # regular def functions — easy to forget this and silently
        # miss all async functions in the codebase
        if node.name.startswith("test_"):
            self.test_functions.append(node.name)
        else:
            if not node.name.startswith("_"):
                self.regular_functions.append(node.name)
        self.generic_visit(node)


def _extract_file_sections(patch_text: str) -> dict[str, str]:
    """
    The combined patch_text looks like:
    
    ### File: src/billing.py
    <patch content>
    
    ### File: tests/test_billing.py
    <patch content>
    
    This splits it back into {filename: patch_content} so we can
    process each file's AST separately.
    """
    sections = {}
    current_file = None
    current_lines = []

    for line in patch_text.split('\n'):
        if line.startswith("### File: "):
            if current_file:
                sections[current_file] = '\n'.join(current_lines)
            current_file = line.replace("### File: ", "").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_file:
        sections[current_file] = '\n'.join(current_lines)

    return sections


@tool
def detect_missing_tests(patch_text: str) -> str:
    """
    Heuristic check for new functions added without a correspondingly
    named test function in the same PR. Uses naming convention matching
    (function_name -> test_function_name), NOT actual coverage measurement.
    
    This is a HEURISTIC — it will have false positives (typos in test 
    names) and false negatives (tests that exercise a function without 
    matching its name, e.g. parametrized or table-driven tests). Findings
    from this tool should always be manually verified.
    
    Args:
        patch_text: The full multi-file patch text, with each file 
                     preceded by "### File: <filename>"
        
    Returns:
        String listing functions that appear to lack a matching test
    """
    sections = _extract_file_sections(patch_text)

    all_regular_functions = []  # list of (function_name, filename)
    all_test_functions = []     # list of test function names

    for filename, file_patch in sections.items():
        clean_code = strip_diff_markers(file_patch)
        try:
            tree = ast.parse(clean_code)
        except SyntaxError:
            # skip files that don't parse (could be non-Python,
            # or a patch fragment that isn't valid on its own)
            continue

        collector = FunctionCollector()
        collector.visit(tree)

        for fn_name in collector.regular_functions:
            all_regular_functions.append((fn_name, filename))
        all_test_functions.extend(collector.test_functions)

    if not all_regular_functions:
        return "No new functions detected in this patch."

    missing = []
    for fn_name, filename in all_regular_functions:
        expected_test_name = f"test_{fn_name}"
        # check if any test function name CONTAINS the function name
        # (looser than exact match, catches test_calculate_discount_v2 etc.)
        has_match = any(
            fn_name in test_name for test_name in all_test_functions
        )
        if not has_match:
            missing.append((fn_name, filename))

    if not missing:
        return (
            f"All {len(all_regular_functions)} new function(s) appear to "
            f"have a matching test function name."
        )

    output_lines = [
        f"{len(missing)} of {len(all_regular_functions)} new function(s) "
        f"have no matching test function name (heuristic — verify manually):\n"
    ]
    for fn_name, filename in missing:
        output_lines.append(
            f"'{fn_name}' in {filename} — no 'test_{fn_name}' or similar found"
        )

    return "\n".join(output_lines)