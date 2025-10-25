"""
Utility functions for the multi-agent system.
"""

import json
from typing import Dict, Any, List, Optional


# JSON utilities
def safe_json_loads(text: str) -> Optional[dict]:
    """
    Tolerant JSON extractor for LLM outputs.
    
    Args:
        text: Raw text that may contain JSON
        
    Returns:
        Parsed JSON dict or None if parsing fails
    """
    try:
        return json.loads(text)
    except Exception:
        pass
    
    # Try to extract JSON from text
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            return None
    return None


def clip(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value between min and max bounds.
    
    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def dedupe_keep_order(items: List[str]) -> List[str]:
    """
    Remove duplicates from a list while preserving order.
    
    Args:
        items: List of strings to deduplicate
        
    Returns:
        Deduplicated list preserving original order
    """
    seen = set()
    out = []
    for x in items:
        k = str(x).strip()
        if not k:
            continue
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            out.append(k)
    return out


# LLM chain utilities
def invoke_json(prompt, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper to run prompt → LLM → string → JSON with tolerant parsing.
    
    Args:
        prompt: ChatPromptTemplate to invoke
        variables: Variables to pass to the prompt
        
    Returns:
        Parsed JSON dict or empty dict if parsing fails
    """
    from .deps import get_deps
    
    deps = get_deps()
    chain = prompt | deps.llm | deps.str_parser
    text = chain.invoke(variables)
    data = safe_json_loads(text) or {}
    if not isinstance(data, dict):
        data = {}
    return data


# Formatting utilities
def format_hypotheses(hypotheses: List[str]) -> str:
    """Format hypotheses list for display."""
    if not hypotheses:
        return "(none)"
    return "\n- " + "\n- ".join(hypotheses)


def format_evidence(evidence: List[str]) -> str:
    """Format evidence list for display."""
    if not evidence:
        return "(none)"
    return "\n---\n".join(evidence)


def format_keywords(keywords: List[str]) -> str:
    """Format keywords list for display."""
    if not keywords:
        return "(none)"
    return ", ".join(keywords)