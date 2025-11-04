"""
LangChain Tool Wrappers for log analysis tools.

This module wraps the existing grep and GC analyzer tools as proper LangChain tools
to enable MLflow tracing and better agent decision-making.
"""

from langchain_core.tools import tool
from typing import List, Optional, Annotated
import json

from multiAgentSystem.tools.grep_tool import grep_path_tool as _grep_path_tool
from multiAgentSystem.tools.gc_analyzer import GC_analyzer_tool as _gc_analyzer_tool


@tool
def grep_logs(
    logs_path: Annotated[str, "Path to the logs directory or file to search"],
    keywords: Annotated[List[str], "List of keywords or patterns to search for in logs"],
    use_or_logic: Annotated[bool, "If True, match ANY keyword (OR). If False, match ALL keywords (AND)"] = True,
    case_sensitive: Annotated[bool, "If True, perform case-sensitive search"] = False,
    max_results: Annotated[int, "Maximum number of log lines to return"] = 5000
) -> str:
    """
    Search Spark logs for specific keywords or patterns.
    
    This tool searches through log files to find lines matching the given keywords.
    Use this when you need to find specific errors, events, or patterns in logs.
    
    Best practices:
    - Start with broader keywords to get context
    - Then use specific error codes or identifiers for focused searches
    - Combine related terms (e.g., ['executor', 'lost', 'killed'])
    
    Examples:
    - Find executor failures: keywords=['ExecutorLostFailure', 'executor', 'lost']
    - Find OOM errors: keywords=['OutOfMemoryError', 'OOM', 'heap space']
    - Find stage failures: keywords=['stage', 'failed', 'materialization']
    
    Returns:
        JSON string with matched log lines including file path, line number, and content.
    """
    try:
        # Join keywords into a pattern
        if use_or_logic:
            pattern = "|".join(keywords)
        else:
            # For AND logic, we'll need to filter results
            pattern = keywords[0] if keywords else ""
        
        # Call the underlying grep tool
        results_json = _grep_path_tool(
            target=logs_path,
            pattern=pattern,
            ignore_case=not case_sensitive,
            max_results=max_results
        )
        
        # Parse and potentially filter for AND logic
        if not use_or_logic and len(keywords) > 1:
            results = json.loads(results_json)
            filtered = []
            for item in results:
                line_text = item.get("line_text", "").lower() if not case_sensitive else item.get("line_text", "")
                kw_check = [kw.lower() if not case_sensitive else kw for kw in keywords]
                if all(kw in line_text for kw in kw_check):
                    filtered.append(item)
            results_json = json.dumps(filtered, ensure_ascii=False)
        
        return results_json
    
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "keywords": keywords,
            "logs_path": logs_path
        })


@tool
def analyze_gc_logs(
    log_content: Annotated[str, "Raw log content containing GC (Garbage Collection) log entries"],
    min_pause_duration_ms: Annotated[float, "Minimum GC pause duration in milliseconds to analyze"] = 100.0,
    only_stop_the_world: Annotated[bool, "If True, only analyze stop-the-world GC pauses"] = True,
    top_n_pauses: Annotated[int, "Number of top GC pauses to return"] = 5
) -> str:
    """
    Analyze Garbage Collection (GC) logs to identify memory issues.
    
    This tool parses GC logs and identifies problematic GC pauses that may indicate
    memory pressure, heap issues, or configuration problems.
    
    Use this tool when:
    - You suspect memory-related issues (OOM, heap space errors)
    - Logs contain GC pause information
    - Need to understand memory pressure patterns
    - Investigating executor or driver crashes
    
    The tool provides:
    - Summary statistics of GC activity
    - Top N longest GC pauses with timestamps
    - Analysis of stop-the-world vs. concurrent collections
    - Recommendations for memory tuning
    
    Returns:
        JSON string with GC analysis including summary, top pauses table, and recommendations.
    """
    try:
        # Call the underlying GC analyzer tool
        analysis_result = _gc_analyzer_tool(
            log_text=log_content,
            format="markdown",
            max_rows=top_n_pauses * 2,  # Get more rows for better analysis
            min_duration_ms=min_pause_duration_ms,
            only_stw=only_stop_the_world,
            top_n=top_n_pauses
        )
        
        # Format as JSON for structured output
        return json.dumps({
            "summary": analysis_result.get("summary", "No GC analysis available"),
            "top_pauses": analysis_result.get("top_pauses_table", "No pause data"),
            "recommendations": "Consider increasing executor memory, tuning GC parameters, or investigating memory leaks if long pauses detected."
        }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            "error": f"Failed to analyze GC logs: {str(e)}",
            "suggestion": "Ensure log content contains valid GC log entries with timestamps and pause durations."
        })


# Export tools as a list for easy consumption
log_analysis_tools = [grep_logs, analyze_gc_logs]


def get_tool_descriptions() -> str:
    """
    Get human-readable descriptions of available tools.
    
    Returns:
        Formatted string describing all available tools.
    """
    return """
Available Log Analysis Tools:

1. grep_logs: Search logs for keywords/patterns
   - Use for finding specific errors, events, or patterns
   - Supports OR/AND logic for multiple keywords
   - Returns matched lines with file paths and line numbers

2. analyze_gc_logs: Analyze Garbage Collection logs
   - Use when investigating memory issues (OOM, heap errors)
   - Identifies long GC pauses and memory pressure
   - Provides tuning recommendations

Choose the right tool based on the hypothesis you're investigating.
"""
