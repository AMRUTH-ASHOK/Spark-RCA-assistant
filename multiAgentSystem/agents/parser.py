"""
Log Parser Agent for finding and analyzing log patterns.

This module provides a parser function that uses specialized tools to:
1. Search logs for specific keywords using grep_path_tool
2. Analyze GC logs using GC_analyzer_tool when relevant
"""

import json
from typing import List, Dict, Any, Optional
from multiAgentSystem.tools.grep_tool import grep_path_tool
from multiAgentSystem.tools.gc_analyzer import GC_analyzer_tool


def parser_fn(logs_path: str, keywords: List[str], hint: str = "") -> str:
    """
    Log Parser that uses specialized tools to search and analyze logs.
    
    Args:
        logs_path: Path to logs directory or file
        keywords: Keywords to search for
        hint: Additional context or analysis type hint
        
    Returns:
        Formatted log analysis results
    """
    # Default response in case tools fail
    default_snippet = (
        f"[LOGS ANALYSIS] path={logs_path}\n"
        f"keywords={keywords}\n"
        f"note={hint or 'analysis'}\n"
        "No matching logs found or unable to access logs path."
    )
    
    try:
        # Check if we're looking for GC-related issues
        gc_related = any(k.lower() in ["gc", "garbage", "memory", "heap", "oom", "outofmemory"] 
                         for k in keywords)
        
        # First, use grep to find relevant log lines
        grep_pattern = "|".join(keywords)
        grep_results_json = grep_path_tool(
            target=logs_path,
            pattern=grep_pattern,
            ignore_case=True,
            max_results=100
        )
        
        # Parse the JSON results
        try:
            grep_results = json.loads(grep_results_json)
        except json.JSONDecodeError:
            grep_results = []
        
        # If no results found, return default snippet
        if not grep_results:
            return default_snippet
        
        # If GC-related keywords and we found results, run GC analyzer
        if gc_related:
            # Extract the raw log text from grep results
            log_text = "\n".join(item.get("line_text", "") for item in grep_results if "line_text" in item)
            
            # Run GC analyzer on the extracted text
            gc_analysis = GC_analyzer_tool(
                log_text=log_text,
                format="markdown",
                max_rows=20,
                min_duration_ms=100.0,  # Focus on longer pauses
                only_stw=True,          # Focus on stop-the-world events
                top_n=5
            )
            
            # Format the GC analysis results
            return (
                f"[GC ANALYSIS] path={logs_path}\n"
                f"keywords={keywords}\n"
                f"note={hint or 'gc analysis'}\n\n"
                f"Summary:\n{gc_analysis['summary']}\n\n"
                f"Top Pauses:\n{gc_analysis['top_pauses_table']}\n"
            )
        
        # For non-GC issues, format the grep results
        formatted_results = []
        for item in grep_results[:20]:  # Limit to 20 results for readability
            path = item.get("path", "unknown")
            line_no = item.get("line_no", 0)
            line_text = item.get("line_text", "")
            formatted_results.append(f"{path}:{line_no}: {line_text}")
        
        return (
            f"[LOG SEARCH] path={logs_path}\n"
            f"keywords={keywords}\n"
            f"note={hint or 'log search'}\n\n"
            f"Found {len(grep_results)} matching lines. Top results:\n\n" +
            "\n".join(formatted_results)
        )
    
    except Exception as e:
        # If any tool fails, return a meaningful error message
        return (
            f"[ERROR] path={logs_path}\n"
            f"keywords={keywords}\n"
            f"note={hint or 'error'}\n"
            f"Error analyzing logs: {str(e)}\n\n"
            "Example: ExecutorLostFailure: executor 7 exited. Reason: Container killed by YARN due to memory limit.\n"
            "GC: Full GC pauses exceeded 3s near failure. Task 45 failed with java.lang.OutOfMemoryError: Java heap space."
        )
