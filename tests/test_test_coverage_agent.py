from src.agents.test_agent import run_test_agent

VULNERABLE_PATCH = """
### File: src/billing.py
+def calculate_discount(price: float, percent: float) -> float:
+    return price - (price * percent / 100)
+
### File: tests/test_billing.py
+def test_total_price():
+    assert 90 == 100 - (100 * 10 / 100)
"""


def test_test_agent_reports_missing_test():
    result = run_test_agent(VULNERABLE_PATCH)

    print(f"\nAgent: {result.agent_name}")
    print(f"Summary: {result.summary}")
    if len(result.findings) > 0:
        print(f"\nFindings ({len(result.findings)}):")
        for finding in result.findings:
            print(f"  [{finding.severity}] {finding.description}")

    assert result.agent_name == "test_coverage"
    assert result.summary.strip()
    assert len(result.findings) > 0
    assert all(f.severity == "MEDIUM" for f in result.findings)
    assert any("calculate_discount" in f.description for f in result.findings)
    print("\n✅ Test coverage agent structured output working")


if __name__ == "__main__":
    test_test_agent_reports_missing_test()