import ast
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers


class DocstringVisitor(ast.NodeVisitor):
    """
    Walks the AST and records every function/class definition along
    with whether it has a docstring, and the docstring text itself
    if present (we need the actual text later for quality judgment).
    """

    def __init__(self):
        # each entry: {"name": str, "type": "function"/"class", 
        #              "line": int, "has_docstring": bool, "docstring": str|None}
        self.items = []

    def _check_node(self, node, node_type: str):
        docstring = ast.get_docstring(node)  # built-in AST helper —
                                               # returns the docstring 
                                               # string or None
        # skip dunder/private methods — same judgment call as 
        # the missing-tests heuristic
        if not node.name.startswith("_"):
            self.items.append({
                "name": node.name,
                "type": node_type,
                "line": node.lineno,
                "has_docstring": docstring is not None,
                "docstring": docstring,
            })

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_node(node, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_node(node, "function")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._check_node(node, "class")
        self.generic_visit(node)


@tool
def check_docstring_presence(code_patch: str) -> str:
    """
    Checks whether functions and classes in the patch have docstrings.
    Reports missing docstrings AND returns existing docstring text
    (paired with the function's code) so it can be evaluated for quality
    separately. This is a deterministic presence check — it does NOT
    judge whether existing docstrings are actually good.

    Args:
        code_patch: The code or diff text to analyze

    Returns:
        String listing functions/classes with and without docstrings
    """
    clean_code = strip_diff_markers(code_patch)
    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        return f"Could not parse code for docstring analysis: {e}"

    visitor = DocstringVisitor()
    visitor.visit(tree)

    if not visitor.items:
        return "No functions or classes found to analyze."

    missing = [i for i in visitor.items if not i["has_docstring"]]
    present = [i for i in visitor.items if i["has_docstring"]]

    output_lines = [
        f"Analyzed {len(visitor.items)} function(s)/class(es): "
        f"{len(present)} have docstrings, {len(missing)} are missing docstrings.\n"
    ]

    if missing:
        output_lines.append("MISSING DOCSTRINGS:")
        for item in missing:
            output_lines.append(f"  [{item['type']}] '{item['name']}' at line {item['line']}")

    if present:
        output_lines.append("\nEXISTING DOCSTRINGS (for quality review):")
        for item in present:
            output_lines.append(
                f"  [{item['type']}] '{item['name']}' at line {item['line']}: "
                f"\"{item['docstring']}\""
            )

    return "\n".join(output_lines)