"""State and type aliases for the multi-agent system.

This module intentionally avoids the name ``types`` so that it never
conflicts with Python's :mod:`types` standard-library module when the
package is imported from a notebook directory.
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
    last_generated_keywords: List[str]  # Keywords from most recent analyzer run

    # Draft + quality
    draft: Dict[str, str]          # {"problem": "...", "rca": "...", "mitigation": "..."}
    confidence: float
    critic_approved: bool
    critique: str

    # Supervisor control
    last_status: Literal["", "continue", "summarized"]
    next_action: Literal["", "reasoning", "critic", "end", "analyzer"]
    supervisor_rationale: str
    pdf_report_path: Optional[str]  # Path to generated PDF report

    # Counters
    analyze_parse_loops: int


# Literal types used throughout the system
StatusType = Literal["", "continue", "summarized"]
ActionType = Literal["", "reasoning", "critic", "end", "analyzer"]
NodeType = Literal["reasoning", "critic", "analyzer", "parser", "__end__"]
