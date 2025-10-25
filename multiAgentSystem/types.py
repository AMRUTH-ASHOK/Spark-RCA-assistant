"""
Type definitions for the multi-agent system.
"""

from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional, Literal


class AgentState(TypedDict, total=False):
    """State object shared between all agents in the system."""
    
    # Inputs
    user_context: str
    logs_path: str

    # Working memory
    iteration: int
    hypotheses: List[str]
    keywords: List[str]
    evidence: List[str]
    last_logs_chunk: str
    analyzer_satisfied: bool

    # Draft + quality
    draft: Dict[str, str]          # {"problem": "...", "rca": "...", "mitigation": "..."}
    confidence: float
    critic_approved: bool
    critique: str

    # Supervisor control
    last_status: Literal["", "continue", "summarized"]
    next_action: Literal["", "reasoning", "critic", "end"]
    supervisor_rationale: str

    # Counters
    analyze_parse_loops: int


# Literal types used throughout the system
StatusType = Literal["", "continue", "summarized"]
ActionType = Literal["", "reasoning", "critic", "end"]
NodeType = Literal["reasoning", "critic", "__end__"]
