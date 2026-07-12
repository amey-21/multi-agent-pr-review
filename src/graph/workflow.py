from langgraph.graph import StateGraph, START, END
from src.graph.state import ReviewState
from src.graph.nodes import (
    fetch_pr_node,
    security_node,
    performance_node,
    test_node,
    docs_node,
    supervisor_node,
)


def build_review_graph():
    """
    Constructs the LangGraph StateGraph. This function just DEFINES
    the graph structure — it doesn't run anything yet. Think of this
    as drawing the diagram, not executing the workflow.
    """
    graph = StateGraph(ReviewState)

    # Step 1: register each node function with a name
    graph.add_node("fetch_pr", fetch_pr_node)
    graph.add_node("security", security_node)
    graph.add_node("performance", performance_node)
    graph.add_node("test_coverage", test_node)
    graph.add_node("docs", docs_node)
    graph.add_node("supervisor", supervisor_node) 

    # Step 2: define edges — this is what creates the fan-out
    # START -> fetch_pr (always the first thing that runs)
    graph.add_edge(START, "fetch_pr")

    # fetch_pr -> all four agents
    # THIS is the fan-out: four edges FROM THE SAME NODE means
    # LangGraph runs all four target nodes in parallel, since
    # none of them depend on each other, only on fetch_pr
    graph.add_edge("fetch_pr", "security")
    graph.add_edge("fetch_pr", "performance")
    graph.add_edge("fetch_pr", "test_coverage")
    graph.add_edge("fetch_pr", "docs")

    # CHANGED: all four agents now feed INTO supervisor, not END directly
    # this is the fan-in — LangGraph automatically waits for ALL FOUR
    # of these edges to be satisfied before running supervisor even once
    graph.add_edge("security", "supervisor")
    graph.add_edge("performance", "supervisor")
    graph.add_edge("test_coverage", "supervisor")
    graph.add_edge("docs", "supervisor")

    graph.add_edge("supervisor", END)

    return graph.compile()


def build_review_graph_no_fetch():
    """
    Same graph as build_review_graph(), but skips fetch_pr_node.
    Used for testing the agent + supervisor pipeline with injected
    patch_text, without requiring a real GitHub API call.
    
    START connects directly to the four agent nodes instead of 
    going through fetch_pr first.
    """
    graph = StateGraph(ReviewState)

    graph.add_node("security", security_node)
    graph.add_node("performance", performance_node)
    graph.add_node("test_coverage", test_node)
    graph.add_node("docs", docs_node)
    graph.add_node("supervisor", supervisor_node)

    # START fans out directly to all four agents — no fetch_pr node at all
    graph.add_edge(START, "security")
    graph.add_edge(START, "performance")
    graph.add_edge(START, "test_coverage")
    graph.add_edge(START, "docs")

    graph.add_edge("security", "supervisor")
    graph.add_edge("performance", "supervisor")
    graph.add_edge("test_coverage", "supervisor")
    graph.add_edge("docs", "supervisor")

    graph.add_edge("supervisor", END)

    return graph.compile()