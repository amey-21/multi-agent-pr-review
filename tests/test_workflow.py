import asyncio
import time
from src.graph.workflow import build_review_graph_no_fetch


REALISTIC_PATCH = """### File: src/billing.py
+import hashlib
+
+API_KEY = "sk-ant-api03-abc123def456ghi789"
+
+def calculate_discount(price, percent):
+    query = f"SELECT * FROM discounts WHERE code = {percent}"
+    return price - (price * percent / 100)
+
+def apply_tax(price):
+    \"\"\"does stuff\"\"\"
+    return price * 1.08
"""


async def run_full_pipeline_test():
    graph = build_review_graph_no_fetch()

    initial_state = {
        "repo_name": "test/fixture",
        "pr_number": 0,
        "pr_diff": None,
        "patch_text": REALISTIC_PATCH,   # injected directly, fetch_pr skipped
        "security_result": None,
        "performance_result": None,
        "test_result": None,
        "docs_result": None,
        "final_report": None,
    }

    start = time.time()
    final_state = await graph.ainvoke(initial_state)
    
    elapsed = time.time() - start

    print(f"\nTotal execution time: {elapsed:.2f}s")

    report = final_state["final_report"]
    print(f"\nFinal Report Summary: {report.summary}")
    print(f"Critical: {report.critical_count}, High: {report.high_count}, "
          f"Medium: {report.medium_count}, Low: {report.low_count}")

    print("\nRanked findings:")
    for f in report.findings:
        print(f"  [{f.severity}] {f.description}")

    assert report.total_findings > 0
    # this patch has a REAL secret + REAL SQL injection — 
    # we should see at least one CRITICAL or HIGH finding
    assert report.critical_count > 0 or report.high_count > 0
    print("\n✅ Full pipeline correctly identified real issues")


if __name__ == "__main__":
    asyncio.run(run_full_pipeline_test())