import ast
from langchain_core.tools import tool
from src.tools.diff_utils import strip_diff_markers


class NPlusOneVisitor(ast.NodeVisitor):
    """
    Walks the Abstract Syntax Tree looking for the N+1 query pattern:
    an attribute access chain (e.g., user.profile.bio) happening 
    INSIDE a for-loop.
    
    WHY AST INSTEAD OF REGEX?
    Regex can't understand nesting or scope — it would false-positive
    on any dotted attribute access anywhere in the file. AST lets us
    know precisely: "this attribute access is inside a for loop body"
    which regex fundamentally cannot determine.
    """

    def __init__(self):
        self.findings = []
        self.loop_depth = 0  # tracks whether we're currently inside a loop

    def visit_For(self, node: ast.For):
        self.loop_depth += 1
        self.generic_visit(node)  # continue walking children
        self.loop_depth -= 1

    def visit_While(self, node: ast.While):
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_Attribute(self, node: ast.Attribute):
        # Only flag if we're inside a loop right now
        if self.loop_depth > 0:
            # Heuristic: chained attribute access (a.b.c) inside a loop
            # is suspicious — could be lazy-loading a related object
            if isinstance(node.value, ast.Attribute):
                self.findings.append({
                    "line": node.lineno,
                    "pattern": self._get_chain_str(node)
                })
        self.generic_visit(node)

    def _get_chain_str(self, node: ast.Attribute) -> str:
        """Reconstructs 'user.profile.bio' from nested AST nodes"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))


@tool
def detect_n_plus_one(code_patch: str) -> str:
    """
    Detects potential N+1 query patterns using custom AST analysis.
    Use this to find chained attribute access inside loops, which
    commonly indicates lazy-loaded database queries running once 
    per iteration instead of being batched.
    
    Args:
        code_patch: The code or diff text to analyze
        
    Returns:
        String describing potential N+1 patterns found. This is a
        HEURISTIC check — it will have false positives since it 
        cannot know if an attribute access actually triggers a 
        database query without knowing your ORM.
    """
    clean_code = strip_diff_markers(code_patch)

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        return f"Could not parse code for N+1 analysis: {e}"

    visitor = NPlusOneVisitor()
    visitor.visit(tree)

    if not visitor.findings:
        return "No potential N+1 query patterns detected."

    output_lines = [
        f"Found {len(visitor.findings)} potential N+1 pattern(s) "
        f"(heuristic — verify manually):\n"
    ]
    for finding in visitor.findings:
        output_lines.append(
            f"Line {finding['line']}: chained attribute access "
            f"'{finding['pattern']}' inside a loop — verify this "
            f"doesn't trigger a query per iteration"
        )

    return "\n".join(output_lines)