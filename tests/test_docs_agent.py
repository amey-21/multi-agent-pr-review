from src.agents.docs_agent import run_docs_agent

DOCS_FIXTURE = """
def calculate_total(items):
    return sum(items)


def add(a: int, b: int) -> int:
    \"\"\"does stuff\"\"\"
    return a + b
"""


def test_docs_agent_handles_missing_and_vague_docstrings():
    result = run_docs_agent(DOCS_FIXTURE)

    print(f"\nAgent: {result.agent_name}")
    print(f"Summary: {result.summary}")
    print(f"Raw tool output:\n{result.raw_tool_output}")

    assert result.agent_name == "docs"
    assert result.summary.strip()
    assert len(result.findings) > 0
    assert all(f.severity in ["MEDIUM", "LOW"] for f in result.findings)

    # The fixture intentionally triggers both deterministic and semantic paths:
    # one public function lacks a docstring, and one has a vague docstring.
    assert any("docstring" in f.description.lower() for f in result.findings)


if __name__ == "__main__":
    test_docs_agent_handles_missing_and_vague_docstrings()
    print("\n✅ Docs agent structured output working")
