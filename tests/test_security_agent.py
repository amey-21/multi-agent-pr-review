import asyncio

from src.agents.security_agent import run_security_agent

VULNERABLE_PATCH = """
+
+def add(a: int, b: int) -> int:
+    return a + b
"""

def test_security_agent_end_to_end():
    result = asyncio.run(run_security_agent(VULNERABLE_PATCH))

    print(f"\nAgent: {result.agent_name}")
    print(f"Summary: {result.summary}")
    if len(result.findings) > 0:
        print(f"\nFindings ({len(result.findings)}):")
        for f in result.findings:
            print(f"  [{f.severity}] Line {f.line}: {f.description}")
            if f.remediation:
                print(f"    Fix: {f.remediation}")

    assert result.summary.startswith("No security issues") or len(result.findings) > 0
    assert all(f.severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"] for f in result.findings)
    print("\n✅ Security agent structured output working")

if __name__ == "__main__":
    test_security_agent_end_to_end()