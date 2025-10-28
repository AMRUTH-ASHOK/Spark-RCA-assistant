"""
Log Analyzer Agent for generating keywords from hypotheses.
"""

from typing import List, Dict, Any
from multiAgentSystem.state import AgentState
from multiAgentSystem.deps import get_deps
from multiAgentSystem.prompts import ANALYZER_PROMPT
from multiAgentSystem.utils import invoke_json
from multiAgentSystem.config import DEFAULT_KEYWORDS


def analyzer_llm(hypotheses: List[str], user_context: str, last_logs_chunk: str, existing_keywords: List[str]) -> Dict[str, Any]:
    """
    Convert hypotheses and context into high-signal keywords for Spark logs.
    
    Args:
        hypotheses: List of hypotheses to analyze
        user_context: User-provided context
        last_logs_chunk: Latest logs snippet
        existing_keywords: Previously generated keywords
        
    Returns:
        Dict with 'keywords' and 'rationale' keys
    """
    data = invoke_json(
        ANALYZER_PROMPT,
        {
            "user_context": user_context or "(none)",
            "hypotheses": "\n- " + "\n- ".join(hypotheses) if hypotheses else "(none)",
            "keywords": ", ".join(existing_keywords) if existing_keywords else "(none)",
            "last_logs_chunk": last_logs_chunk or "(none)",
        },
        agent_name="analyzer"
    )
    
    kws = data.get("keywords") or []
    if not isinstance(kws, list):
        kws = [str(kws)]
    kws = [str(k).strip() for k in kws if str(k).strip()]
    if not kws:
        kws = DEFAULT_KEYWORDS
    
    return {"keywords": kws[:8], "rationale": str(data.get("rationale") or "").strip()}


def analyzer_node(state: "AgentState") -> "AgentState":
    """
    Analyzer agent node that produces keywords from hypotheses and requests the parser.
    Returns partial state that the graph runner will merge.
    """
    hypotheses = list(state.get("hypotheses") or [])
    user_context = state.get("user_context", "")
    last_logs_chunk = state.get("last_logs_chunk", "") or ""
    existing_keywords = list(state.get("keywords") or [])

    out = analyzer_llm(hypotheses, user_context, last_logs_chunk, existing_keywords)
    new_kws = [str(k).strip() for k in out.get("keywords", []) if str(k).strip()]
    # Merge new keywords while preserving order
    from multiAgentSystem.utils import dedupe_keep_order
    keywords = dedupe_keep_order(existing_keywords + new_kws)

    # Increment analyze_parse_loops counter (the analyzer is part of that inner loop)
    analyze_loops = int(state.get("analyze_parse_loops", 0)) + 1

    return {
        "keywords": keywords,
        "last_generated_keywords": new_kws,
        "analyze_parse_loops": analyze_loops,
        # After analyzer, the graph will automatically route to parser via edge
    }
