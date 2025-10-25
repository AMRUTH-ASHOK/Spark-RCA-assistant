"""
Supervisor Agent for orchestrating the multi-agent workflow.
"""

import json
from typing import Literal
from ..deps import get_deps
from ..prompts import SUPERVISOR_PROMPT
from ..utils import invoke_json
from ..config import MAX_OUTER_ITERATIONS, CONFIDENCE_THRESHOLD
from ..types import AgentState, NodeType


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor decides next_action and manages outer iteration.
    It always receives control after Reasoning or Critic.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with supervisor decision
    """
    iteration = int(state.get("iteration", 0))
    last_status = state.get("last_status", "") or ""
    critic_approved = bool(state.get("critic_approved", False))
    confidence = float(state.get("confidence", 0.0))

    # Allowed actions depend on the stage
    if iteration == 0:
        allowed = ["reasoning"]
    elif last_status == "summarized" and not critic_approved:
        allowed = ["critic", "reasoning"]
    elif critic_approved:
        allowed = ["end", "reasoning"]
    else:
        allowed = ["reasoning"]

    evidence_preview = "\n---\n".join(state.get("evidence", [])[-2:]) if state.get("evidence") else "(none)"

    sup = invoke_json(
        SUPERVISOR_PROMPT,
        {
            "allowed_actions": ", ".join(allowed),
            "iteration": iteration,
            "last_status": last_status or "(none)",
            "confidence": confidence,
            "critic_approved": critic_approved,
            "critique": state.get("critique", "") or "(none)",
            "draft": json.dumps(state.get("draft", {}), ensure_ascii=False) if state.get("draft") else "(none)",
            "evidence": evidence_preview,
        },
    )
    proposed = str(sup.get("next_action") or "").strip().lower()
    rationale = str(sup.get("rationale") or "").strip()

    # Policy guards / caps
    if iteration >= MAX_OUTER_ITERATIONS and last_status != "":
        next_action: Literal["reasoning", "critic", "end"] = "end"
        rationale = (rationale + " | Max outer iterations reached. Ending.").strip()
    else:
        if proposed not in allowed:
            if iteration == 0:
                next_action = "reasoning"
                rationale = (rationale + " | Defaulting to reasoning for initial pass.").strip()
            elif last_status == "summarized" and not critic_approved:
                next_action = "critic"
                rationale = (rationale + " | Must validate draft with Critic.").strip()
            elif critic_approved and confidence >= CONFIDENCE_THRESHOLD:
                next_action = "end"
                rationale = (rationale + " | Critic approved and confidence high. Ending.").strip()
            else:
                next_action = "reasoning"
                rationale = (rationale + " | Continuing reasoning.").strip()
        else:
            next_action = proposed  # respect Supervisor LLM choice

    new_iteration = iteration + 1 if next_action == "reasoning" else iteration

    return {
        "next_action": next_action,
        "iteration": new_iteration,
        "supervisor_rationale": rationale,
    }


def supervisor_router(state: AgentState) -> NodeType:
    """
    Router function for supervisor decisions.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node to execute
    """
    nxt = state.get("next_action", "") or ""
    if nxt == "critic":
        return "critic"
    if nxt == "reasoning":
        return "reasoning"
    return "__end__"
