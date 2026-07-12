from src.tools.test_coverage_heuristic import detect_missing_tests

PATCH_WITH_TEST = """### File: src/billing.py
+def calculate_discount(price, percent):
+    return price - (price * percent / 100)

### File: tests/test_billing.py
+def test_calculate_discount():
+    assert calculate_discount(100, 10) == 90
"""

PATCH_WITHOUT_TEST = """### File: src/billing.py
+def calculate_discount(price, percent):
+    return price - (price * percent / 100)
+
+def apply_tax(price):
+    return price * 1.08
"""


def test_detects_tested_function():
    result = detect_missing_tests.invoke({"patch_text": PATCH_WITH_TEST})
    print(f"\nWith test:\n{result}")
    assert "appear to have a matching test" in result


def test_detects_missing_tests():
    result = detect_missing_tests.invoke({"patch_text": PATCH_WITHOUT_TEST})
    print(f"\nWithout test:\n{result}")
    assert "calculate_discount" in result
    assert "apply_tax" in result


if __name__ == "__main__":
    test_detects_tested_function()
    test_detects_missing_tests()
    print("\n✅ Missing tests heuristic working correctly")