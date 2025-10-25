"""
Log Analyzer Agent for generating keywords from hypotheses.
"""

from typing import List, Dict, Any
from ..deps import get_deps
from ..prompts import ANALYZER_PROMPT
from ..utils import invoke_json
from ..config import DEFAULT_KEYWORDS


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
    )
    
    kws = data.get("keywords") or []
    if not isinstance(kws, list):
        kws = [str(kws)]
    kws = [str(k).strip() for k in kws if str(k).strip()]
    if not kws:
        kws = DEFAULT_KEYWORDS
    
    return {"keywords": kws[:8], "rationale": str(data.get("rationale") or "").strip()}
