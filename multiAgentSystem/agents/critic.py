"""
Critic Agent for validating draft outputs against evidence.
"""

import json
from typing import Dict, Any
from multiAgentSystem.deps import get_deps
from multiAgentSystem.prompts import CRITIC_PROMPT
from multiAgentSystem.utils import invoke_json, format_evidence_map
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
    # Prefer evidence_map, fallback to evidence for backward compatibility
    evidence_map = state.get("evidence_map", {})
    legacy_evidence = state.get("evidence", [])
    
    data = invoke_json(
        CRITIC_PROMPT,
        {
            "draft": json.dumps(state.get("draft", {}), ensure_ascii=False),
            "evidence": format_evidence_map(evidence_map) if evidence_map else "\n---\n".join(legacy_evidence) if legacy_evidence else "(none)",
        },
        agent_name="critic"
    )
    
    approve = bool(data.get("approve")) if isinstance(data.get("approve"), bool) else False
    reasons = str(data.get("reasons") or "").strip()
    
    try:
        adj = float(data.get("confidence_adjustment", 0.0))
    except Exception:
        adj = 0.0
    adj = clip(adj, -0.30, 0.30)  # Updated range to match new prompt
    
    current_conf = float(state.get("confidence", 0.5))
    new_conf = clip(current_conf + adj, 0.0, 1.0)

    return {
        "critic_approved": approve,
        "critique": reasons,
        "confidence": new_conf,
    }

