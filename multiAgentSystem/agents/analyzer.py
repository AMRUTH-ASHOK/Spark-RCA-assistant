"""
Log Analyzer Agent for generating keywords from hypotheses.
"""

from typing import List, Dict, Any
from multiAgentSystem.state import AgentState
from multiAgentSystem.deps import get_deps
from multiAgentSystem.prompts import ANALYZER_PROMPT
from multiAgentSystem.utils import invoke_json
from multiAgentSystem.config import DEFAULT_KEYWORDS, MAX_ANALYZE_PARSE_LOOPS


def analyzer_llm(hypotheses: List[str], user_context: str, last_logs_chunk: str, existing_keywords: List[str]) -> Dict[str, Any]:
    """
    Convert hypotheses and context into high-signal keywords for Spark logs.
    Always includes DEFAULT_KEYWORDS plus LLM-suggested keywords.
    
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
    
    # Get LLM-suggested keywords
    llm_kws = data.get("keywords") or []
    if not isinstance(llm_kws, list):
        llm_kws = [str(llm_kws)]
    llm_kws = [str(k).strip() for k in llm_kws if str(k).strip()]
    
    # ALWAYS start with DEFAULT_KEYWORDS, then add LLM suggestions
    # This ensures we always search for common error patterns
    combined_kws = list(DEFAULT_KEYWORDS) + llm_kws
    
    # Deduplicate while preserving order (DEFAULT_KEYWORDS come first)
    from multiAgentSystem.utils import dedupe_keep_order
    final_kws = dedupe_keep_order(combined_kws)
    
    return {"keywords": final_kws[:15], "rationale": str(data.get("rationale") or "").strip()}


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
    
    # Check if we should stop the analyzer-parser loop
    # Stop if max loops reached OR if no new keywords were generated (convergence)
    analyzer_satisfied = False
    if analyze_loops >= MAX_ANALYZE_PARSE_LOOPS:
        analyzer_satisfied = True
    elif not new_kws:
        # If no new keywords found, we might be done, but let's ensure we did at least one pass
        if analyze_loops > 1:
            analyzer_satisfied = True

    return {
        "keywords": keywords,
        "last_generated_keywords": new_kws,
        "analyze_parse_loops": analyze_loops,
        "analyzer_satisfied": analyzer_satisfied,
        # After analyzer, the graph will automatically route to parser or reasoning based on analyzer_satisfied
    }
