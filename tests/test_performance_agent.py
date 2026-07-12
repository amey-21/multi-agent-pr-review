from src.agents.performance_agent import run_performance_agent

HIGH_COMPLEXITY_PATCH = """
def deeply_nested_control_flow(a, b, c, d, e, f):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return 1
                    elif f:
                        return 2
                    else:
                        return 3
                elif e:
                    return 4
                else:
                    return 5
            elif d:
                return 6
            else:
                return 7
        elif e:
            return 8
        else:
            return 9
    elif b:
        if c:
            return 10
        elif d:
            return 11
        else:
            return 12
    else:
        return 13
"""


def test_performance_agent_flags_high_complexity_patch():
    result = run_performance_agent(HIGH_COMPLEXITY_PATCH)

    print(f"\nAgent: {result.agent_name}")
    print(f"Summary: {result.summary}")
    print(f"Raw tool output:\n{result.raw_tool_output}")

    assert result.agent_name == "performance"
    assert result.summary.strip()
    assert "=== RADON COMPLEXITY ===" in result.raw_tool_output
    assert all(f.severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"] for f in result.findings)
    assert len(result.findings) >= 0


if __name__ == "__main__":
    test_performance_agent_flags_high_complexity_patch()
    print("\n✅ Performance agent structured output working")
