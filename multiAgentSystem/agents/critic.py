"""
Critic Agent for validating draft outputs against evidence.
"""

import json
from typing import Dict, Any
from multiAgentSystem.deps import get_deps
from multiAgentSystem.prompts import CRITIC_PROMPT
from multiAgentSystem.utils import invoke_json
from multiAgentSystem.utils import clip
from multiAgentSystem.state import AgentState


def critic_node(state: AgentState) -> AgentState:
    """
    Critic validates draft vs evidence and nudges confidence.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with critic feedback
    """
    data = invoke_json(
        CRITIC_PROMPT,
        {
            "draft": json.dumps(state.get("draft", {}), ensure_ascii=False),
            "evidence": "\n---\n".join(state.get("evidence", [])) if state.get("evidence") else "(none)",
        },
    )
    
    approve = bool(data.get("approve")) if isinstance(data.get("approve"), bool) else False
    reasons = str(data.get("reasons") or "").strip()
    
    try:
        adj = float(data.get("confidence_adjustment", 0.0))
    except Exception:
        adj = 0.0
    adj = clip(adj, -0.25, 0.25)
    
    current_conf = float(state.get("confidence", 0.5))
    new_conf = clip(current_conf + adj, 0.0, 1.0)

    return {
        "critic_approved": approve,
        "critique": reasons,
        "confidence": new_conf,
    }
