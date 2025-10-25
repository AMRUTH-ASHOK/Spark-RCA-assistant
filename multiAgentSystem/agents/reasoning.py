"""
Reasoning Agent for assessing evidence sufficiency and generating summaries.
"""

from typing import List, Dict, Any
from multiAgentSystem.deps import get_deps
from multiAgentSystem.prompts import REASON_DECIDE_PROMPT, SUMMARIZE_PROMPT
from multiAgentSystem.utils import (
    invoke_json,
    format_hypotheses,
    format_evidence,
    format_keywords,
)
from multiAgentSystem.utils import clip, dedupe_keep_order
from multiAgentSystem.config import MAX_ANALYZE_PARSE_LOOPS
from multiAgentSystem.state import AgentState
from multiAgentSystem.agents.analyzer import analyzer_llm
from multiAgentSystem.agents.parser import parser_fn


def reasoning_node(state: AgentState) -> AgentState:
    """
    Reasoning Agent:
      - assesses sufficiency
      - if insufficient: runs inner analyser↔parser mini-loop (up to MAX_ANALYZE_PARSE_LOOPS)
      - re-assesses; if still insufficient -> last_status='continue'
      - if sufficient: summarises -> last_status='summarized' with draft+confidence
      
    Args:
        state: Current agent state
        
    Returns:
        Updated state with reasoning results
    """
    # 1) Assess sufficiency
    decide = invoke_json(
        REASON_DECIDE_PROMPT,
        {
            "user_context": state.get("user_context", ""),
            "logs_path": state.get("logs_path", ""),
            "hypotheses": format_hypotheses(state.get("hypotheses", [])),
            "evidence": format_evidence(state.get("evidence", [])),
            "keywords": format_keywords(state.get("keywords", [])),
            "iteration": int(state.get("iteration", 0)),
        },
    )

    need_more = bool(decide.get("need_more"))
    new_hypotheses = decide.get("hypotheses") or []
    if not isinstance(new_hypotheses, list):
        new_hypotheses = [str(new_hypotheses)]
    hypotheses = dedupe_keep_order((state.get("hypotheses") or []) + [str(h) for h in new_hypotheses])

    evidence = list(state.get("evidence") or [])
    keywords = list(state.get("keywords") or [])
    last_logs_chunk = state.get("last_logs_chunk", "") or ""
    analyze_loops = int(state.get("analyze_parse_loops", 0))

    # 2) If insufficient, run the inner analyser↔parser loop
    if need_more:
        for _ in range(MAX_ANALYZE_PARSE_LOOPS):
            analyze_loops += 1
            ana = analyzer_llm(hypotheses, state.get("user_context", ""), last_logs_chunk, keywords)
            new_kws = ana["keywords"]
            keywords = dedupe_keep_order((keywords or []) + new_kws)

            logs_chunk = parser_fn(state.get("logs_path", ""), new_kws, hint="loop")
            last_logs_chunk = logs_chunk
            evidence.append(logs_chunk)

            # MVP: dummy parser always returns something; break after first loop.
            break

        # Re-assess sufficiency after collecting evidence
        decide2 = invoke_json(
            REASON_DECIDE_PROMPT,
            {
                "user_context": state.get("user_context", ""),
                "logs_path": state.get("logs_path", ""),
                "hypotheses": format_hypotheses(hypotheses),
                "evidence": format_evidence(evidence),
                "keywords": format_keywords(keywords),
                "iteration": int(state.get("iteration", 0)),
            },
        )
        need_more = bool(decide2.get("need_more"))

        if need_more:
            return {
                "hypotheses": hypotheses,
                "keywords": keywords,
                "evidence": evidence,
                "last_logs_chunk": last_logs_chunk,
                "analyze_parse_loops": analyze_loops,
                "last_status": "continue",
            }

    # 3) Evidence sufficient → summarise inside Reasoning
    summary = invoke_json(
        SUMMARIZE_PROMPT,
        {
            "user_context": state.get("user_context", ""),
            "logs_path": state.get("logs_path", ""),
            "hypotheses": format_hypotheses(hypotheses),
            "evidence": format_evidence(evidence),
        },
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
        "evidence": evidence,
        "last_logs_chunk": last_logs_chunk,
        "analyze_parse_loops": analyze_loops,
        "draft": {"problem": problem, "rca": rca, "mitigation": mitigation},
        "confidence": conf,
        "last_status": "summarized",
    }
