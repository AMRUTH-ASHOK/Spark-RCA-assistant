"""
Reasoning Agent for assessing evidence sufficiency and generating summaries.
"""

from typing import List, Dict, Any

from multiAgentSystem.deps import get_deps
from multiAgentSystem.prompts import REASON_DECIDE_PROMPT, SUMMARIZE_PROMPT
from multiAgentSystem.utils import (
    invoke_json,
    format_hypotheses,
    format_keywords,
)
from multiAgentSystem.utils import clip, dedupe_keep_order
from multiAgentSystem.config import MAX_ANALYZE_PARSE_LOOPS
from multiAgentSystem.state import AgentState
from multiAgentSystem.exceptions import StateError

from multiAgentSystem.agents.analyzer import analyzer_llm

# MLflow tracing setup
try:
    import mlflow
    from mlflow.entities import SpanType
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None


def _trace_agent(name: str):
    """Decorator factory for MLflow agent tracing."""
    def decorator(func):
        if not MLFLOW_AVAILABLE:
            return func
        return mlflow.trace(span_type=SpanType.AGENT, name=name)(func)
    return decorator


@_trace_agent("reasoning_agent")
def reasoning_node(state: AgentState) -> AgentState:
    """
    Reasoning Agent:
      - assesses sufficiency
      - if insufficient and haven't exceeded loop limit: triggers analyzer→parser mini-loop
      - re-assesses after getting new evidence
      - if sufficient: summarizes -> last_status='summarized' with draft+confidence
      
    Args:
        state: Current agent state
        
    Returns:
        Updated state with reasoning results
    """
    analyze_loops = int(state.get("analyze_parse_loops", 0))
    
    # 1) Assess sufficiency using optimized evidence_map strategy
    evidence_for_prompt = state.get("evidence_summary") or "(no evidence collected yet)"

    decide = invoke_json(
        REASON_DECIDE_PROMPT,
        {
            "user_context": state.get("user_context", ""),
            "logs_path": state.get("logs_path", ""),
            "hypotheses": format_hypotheses(state.get("hypotheses", [])),
            "evidence": evidence_for_prompt,
            "keywords": format_keywords(state.get("keywords", [])),
            "iteration": int(state.get("iteration", 0)),
        },
        agent_name="reasoning"
    )

    need_more = bool(decide.get("need_more"))
    new_hypotheses = decide.get("hypotheses") or []
    if not isinstance(new_hypotheses, list):
        new_hypotheses = [str(new_hypotheses)]
    hypotheses = dedupe_keep_order((state.get("hypotheses") or []) + [str(h) for h in new_hypotheses])

    keywords = list(state.get("keywords") or [])
    last_logs_chunk = state.get("last_logs_chunk", "") or ""

    # 2) If insufficient and haven't exceeded loop limit, trigger analyzer
    if need_more and analyze_loops < MAX_ANALYZE_PARSE_LOOPS:
        # Request the analyzer to run (which will trigger parser, then return to reasoning)
        return {
            "hypotheses": hypotheses,
            "keywords": keywords,
            "last_logs_chunk": last_logs_chunk,
            "analyze_parse_loops": analyze_loops,
            "last_status": "continue",
            "next_action": "analyzer",
        }

    # 3) Either evidence is sufficient OR we've hit max loops → summarize
    # Use optimized evidence_map strategy
    evidence_for_summary = state.get("evidence_summary") or "(no evidence collected)"
    
    # Check if evidence contains critical errors
    evidence_map = state.get("evidence_map", {})
    has_critical_error = any("CRITICAL_ERROR" in key or "error_no" in key for key in evidence_map.keys())
    
    # If there's a critical error, generate a diagnostic report instead of RCA
    if has_critical_error:
        error_keys = [k for k in evidence_map.keys() if "CRITICAL_ERROR" in k or "error_no" in k]
        error_details = "\n\n".join([evidence_map[k]["sample_lines"][0] for k in error_keys if evidence_map[k]["sample_lines"]])
        
        return {
            "hypotheses": hypotheses,
            "keywords": keywords,
            "last_logs_chunk": last_logs_chunk,
            "analyze_parse_loops": analyze_loops,
            "draft": {
                "problem": f"System Configuration Error: Unable to perform analysis due to missing or invalid inputs.",
                "rca": f"Root Cause: {error_details}",
                "mitigation": (
                    "1. Verify that 'logs_path' is provided in the initial state\n"
                    "2. Ensure logs_path points to a valid Unity Catalog volume path\n"
                    "3. Check that the path is accessible and contains Spark log files\n"
                    "4. Re-run the analysis with correct configuration"
                )
            },
            "confidence": 0.0,
            "last_status": "summarized",
            "next_action": "",
        }

    summary = invoke_json(
        SUMMARIZE_PROMPT,
        {
            "user_context": state.get("user_context", ""),
            "logs_path": state.get("logs_path", ""),
            "hypotheses": format_hypotheses(hypotheses),
            "evidence": evidence_for_summary,
        },
        agent_name="reasoning"
    )

    problem = str(summary.get("problem") or "").strip() or "Problem: (unspecified)"
    rca = str(summary.get("rca") or "").strip() or "RCA: (unspecified)"
    mitigation = str(summary.get("mitigation") or "").strip() or "Mitigation: (unspecified)"
    
    try:
        conf = float(summary.get("confidence"))
    except Exception:
        conf = 0.5
    conf = clip(conf, 0.0, 1.0)

    return {
        "hypotheses": hypotheses,
        "keywords": keywords,
        "last_logs_chunk": last_logs_chunk,
        "analyze_parse_loops": analyze_loops,
        "draft": {"problem": problem, "rca": rca, "mitigation": mitigation},
        "confidence": conf,
        "last_status": "summarized",
        "next_action": "",  # Clear next_action, let supervisor decide
    }
