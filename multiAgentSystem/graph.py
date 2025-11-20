"""
Graph building logic for the multi-agent system.
"""

from langgraph.graph import StateGraph, END
from multiAgentSystem.state import AgentState
from multiAgentSystem.agents import (
    supervisor_node,
    supervisor_router,
    reasoning_node,
    analyzer_node,
    parser_node,
    critic_node,
)


def build_graph():
    """
    Build and compile the StateGraph for the multi-agent system.
    
    The graph structure follows a strict bidirectional pattern:
    - Supervisor <-> Reasoning (bidirectional)
    - Supervisor <-> Critic (bidirectional)
    - Reasoning <-> LogAnalyser (bidirectional)
    - LogAnalyser <-> LogParser (bidirectional)
    
    Entry point: Supervisor
    
    Returns:
        Compiled StateGraph ready for execution
    """
    g = StateGraph(AgentState)

    # Add all nodes
    g.add_node("supervisor", supervisor_node)
    g.add_node("reasoning", reasoning_node)
    g.add_node("analyzer", analyzer_node)
    g.add_node("parser", parser_node)
    g.add_node("critic", critic_node)

    # Set entry point
    g.set_entry_point("supervisor")
    
    # Supervisor conditional routing
    g.add_conditional_edges(
        "supervisor", 
        supervisor_router, 
        {
            "reasoning": "reasoning",
            "critic": "critic",
            "__end__": END,
        }
    )

    # Reasoning agent routing
    def reasoning_router(state: AgentState) -> str:
        """Route from reasoning: back to supervisor or to analyzer."""
        next_action = state.get("next_action", "")
        if next_action == "analyzer":
            return "analyzer"
        return "supervisor"
    
    g.add_conditional_edges(
        "reasoning",
        reasoning_router,
        {
            "supervisor": "supervisor",
            "analyzer": "analyzer",
        }
    )

    # Analyzer (LogAnalyser) routing
    def analyzer_router(state: AgentState) -> str:
        """Route from analyzer: to parser or back to reasoning."""
        # If analyzer is satisfied or max loops reached, go back to reasoning
        if state.get("analyzer_satisfied", False):
            return "reasoning"
        return "parser"
    
    g.add_conditional_edges(
        "analyzer",
        analyzer_router,
        {
            "parser": "parser",
            "reasoning": "reasoning",
        }
    )
    
    # Parser (LogParser) routing
    def parser_router(state: AgentState) -> str:
        """Route from parser: back to analyzer."""
        return "analyzer"
    
    g.add_conditional_edges(
        "parser",
        parser_router,
        {
            "analyzer": "analyzer",
        }
    )

    # Critic always returns to supervisor
    g.add_edge("critic", "supervisor")

    return g.compile()
