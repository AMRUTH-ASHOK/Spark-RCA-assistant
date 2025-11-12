"""
Supervisor Agent for orchestrating the multi-agent workflow.
"""

import json
from typing import Literal
from multiAgentSystem.deps import get_deps
from multiAgentSystem.prompts import SUPERVISOR_PROMPT
from multiAgentSystem.utils import invoke_json
from multiAgentSystem.config import MAX_OUTER_ITERATIONS, CONFIDENCE_THRESHOLD
from multiAgentSystem.state import AgentState, NodeType
from multiAgentSystem.tools.pdf_report_tool import generate_rca_report_tool



def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor decides next_action and manages outer iteration.
    It receives control after Reasoning, Critic, or at the start.
    
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

    # Create evidence preview - prefer evidence_map for token efficiency
    evidence_map = state.get("evidence_map", {})
    legacy_evidence = state.get("evidence", [])
    
    if evidence_map:
        from multiAgentSystem.log_deduplicator import get_evidence_summary_stats
        stats = get_evidence_summary_stats(evidence_map)
        evidence_preview = f"Evidence: {stats['unique_patterns']} unique patterns, {stats['total_occurrences']} occurrences across {stats['unique_files']} files"
    elif legacy_evidence:
        evidence_preview = "\n---\n".join(legacy_evidence[-2:])
    else:
        evidence_preview = "(none)"

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
        agent_name="supervisor"
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

    # Increment iteration only when starting a new reasoning cycle from supervisor
    new_iteration = iteration + 1 if next_action == "reasoning" else iteration

    # Generate PDF report if ending the workflow
    pdf_report_path = None
    if next_action == "end":
        try:
            # Prepare output data for PDF generation
            output_data = {
                "problem": state.get("draft", {}).get("problem", ""),
                "rca": state.get("draft", {}).get("rca", ""),
                "mitigation": state.get("draft", {}).get("mitigation", ""),
                "confidence": confidence,
                "iterations": new_iteration,
                "keywords": state.get("keywords", []),
                "evidence": state.get("evidence", []),
                "critic_approved": critic_approved,
                "critique": state.get("critique", "")
            }
            
            # Generate the PDF report
            pdf_report_path = generate_rca_report_tool(output_data)
            print(f"\n✓ PDF Report generated: {pdf_report_path}")
            
        except Exception as e:
            print(f"\n⚠ Warning: Failed to generate PDF report: {e}")
            pdf_report_path = f"Error: {str(e)}"

    return {
        "next_action": next_action,
        "iteration": new_iteration,
        "supervisor_rationale": rationale,
        "pdf_report_path": pdf_report_path,
    }


def supervisor_router(state: AgentState) -> NodeType:
    """
    Router function for supervisor decisions.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node to execute
        
    Note:
        Supervisor only routes to: reasoning, critic, or __end__
        It should NEVER route to analyzer directly.
        Analyzer is only accessed via reasoning agent's internal routing.
    """
    nxt = state.get("next_action", "") or ""
    if nxt == "critic":
        return "critic"
    if nxt == "reasoning":
        return "reasoning"
    # Note: "analyzer" is not a valid supervisor route
    # The reasoning agent handles analyzer routing internally
    return "__end__"
