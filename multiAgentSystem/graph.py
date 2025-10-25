"""
Graph building logic for the multi-agent system.
"""

from langgraph.graph import StateGraph, END
from multiAgentSystem.state import AgentState
from multiAgentSystem.agents import (
    supervisor_node,
    supervisor_router,
    reasoning_node,
    critic_node,
)


def build_graph():
    """
    Build and compile the StateGraph for the multi-agent system.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    g = StateGraph(AgentState)

    # Nodes
    g.add_node("supervisor", supervisor_node)
    g.add_node("reasoning", reasoning_node)
    g.add_node("critic", critic_node)

    # Edges
    g.set_entry_point("supervisor")
    g.add_conditional_edges("supervisor", supervisor_router, {
        "reasoning": "reasoning",
        "critic": "critic",
        "__end__": END,
    })
    g.add_edge("reasoning", "supervisor")
    g.add_edge("critic", "supervisor")

    return g.compile()
