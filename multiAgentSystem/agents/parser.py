"""
Log Parser Agent for finding and analyzing log patterns.

This agent uses LangChain tools to autonomously decide between:
1. grep_logs: Search logs for specific keywords
2. analyze_gc_logs: Analyze GC logs when memory issues are suspected

The agent outputs evidence in a deduplicated format to optimize token usage.
"""

import json
from typing import List, Dict, Any
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import create_react_agent

from multiAgentSystem.deps import get_deps
from multiAgentSystem.tools.langchain_tools import log_analysis_tools
from multiAgentSystem.state import AgentState
from multiAgentSystem.log_deduplicator import (
    deduplicate_grep_results,
    merge_evidence_maps,
    format_evidence_map_for_prompt
)


# Create the parser agent with access to log analysis tools
def create_parser_agent():
    """
    Create a ReAct agent that can autonomously choose between log analysis tools.
    
    Returns:
        LangGraph ReAct agent with log analysis capabilities
    """
    llm = get_deps().llm
    
    # Create system prompt for the parser agent
    system_prompt = """You are a Log Parser Agent specialized in analyzing Spark logs for root cause analysis.

Your role is to intelligently search and analyze logs based on the given keywords and hypotheses.

TOOL SELECTION STRATEGY:

1. Use 'grep_logs' when:
   - Searching for specific errors, events, or patterns
   - Following causal chains (executor failures, stage failures, etc.)
   - Need to find all occurrences of specific keywords
   - Starting investigation (broad search)

2. Use 'analyze_gc_logs' when:
   - Keywords suggest memory issues (OOM, heap, GC, memory)
   - grep_logs found GC-related log entries
   - Need to understand memory pressure patterns
   - Investigating executor/driver crashes potentially due to memory

SEARCH STRATEGY:
- Start with grep_logs using the provided keywords
- If results suggest GC issues, follow up with analyze_gc_logs
- Return findings in a clear, structured format

Always provide:
- What you searched for
- What you found
- Summary of key findings
"""
    
    agent = create_react_agent(
        llm,
        tools=log_analysis_tools,
        state_modifier=system_prompt
    )
    
    return agent


# Initialize the parser agent
_parser_agent = None

def get_parser_agent():
    """Get or create the parser agent (singleton pattern)."""
    global _parser_agent
    if _parser_agent is None:
        _parser_agent = create_parser_agent()
    return _parser_agent


def parser_node(state: AgentState) -> AgentState:
    """
    Parser agent node that uses LangChain tools to search and analyze logs.
    
    The agent:
    1. Takes keywords from the analyzer
    2. Autonomously decides which tools to use (grep vs GC analysis)
    3. Deduplicates results into evidence_map
    4. Returns control to reasoning agent
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with evidence_map, last_logs_chunk, cleared next_action
    """
    logs_path = state.get("logs_path", "")
    
    # Get keywords - prefer the latest from analyzer
    kw = state.get("last_generated_keywords") or state.get("keywords") or []
    if isinstance(kw, str):
        kw = [kw]
    kw = [str(k).strip() for k in kw if str(k).strip()]
    
    # Validate inputs
    if not logs_path or not logs_path.strip():
        error_evidence = {
            "error_no_path": {
                "content": "[ERROR] No logs path provided. Please provide a valid logs path to analyze.",
                "timestamps": [],
                "count": 1,
                "first_seen": "N/A",
                "last_seen": "N/A",
                "file_path": "N/A",
                "pattern": "error"
            }
        }
        return {
            "evidence_map": merge_evidence_maps(state.get("evidence_map", {}), error_evidence),
            "last_logs_chunk": "Error: No logs path provided",
            "last_generated_keywords": []
        }
    
    if not kw or len(kw) == 0:
        error_evidence = {
            "error_no_keywords": {
                "content": f"[ERROR] No keywords provided for search. Path: {logs_path}",
                "timestamps": [],
                "count": 1,
                "first_seen": "N/A",
                "last_seen": "N/A",
                "file_path": logs_path,
                "pattern": "error"
            }
        }
        return {
            "evidence_map": merge_evidence_maps(state.get("evidence_map", {}), error_evidence),
            "last_logs_chunk": "Error: No keywords provided",
            "last_generated_keywords": []
        }
    
    try:
        # Create input for the parser agent
        agent_input = {
            "messages": [
                {
                    "role": "user",
                    "content": f"""Analyze Spark logs to find evidence for the following investigation:

Logs Path: {logs_path}
Keywords to search: {', '.join(kw)}

Task: Use the available tools to search the logs and extract relevant evidence.
Decide which tool(s) to use based on the keywords and what you find."""
                }
            ]
        }
        
        # Invoke the parser agent
        agent = get_parser_agent()
        result = agent.invoke(agent_input)
        
        # Extract the agent's findings from messages
        messages = result.get("messages", [])
        agent_response = ""
        
        # Get the last assistant message
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                agent_response = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                agent_response = msg.get("content", "")
                break
        
        # The agent may have used grep_logs - check if we can deduplicate the results
        # Look for tool call results in messages
        grep_results = []
        for msg in messages:
            if hasattr(msg, 'type') and msg.type == 'tool':
                try:
                    tool_output = msg.content
                    parsed = json.loads(tool_output)
                    if isinstance(parsed, list):
                        grep_results.extend(parsed)
                except Exception:
                    # Ignore malformed tool outputs - agent will summarize instead
                    pass
        
        # Deduplicate grep results if we found any
        new_evidence_map = {}
        if grep_results:
            pattern_used = "|".join(kw)
            new_evidence_map = deduplicate_grep_results(grep_results, pattern_used)
        else:
            # If no structured grep results, store the agent's response as evidence
            import hashlib
            content_hash = hashlib.md5(agent_response.encode()).hexdigest()[:12]
            key = f"{logs_path}::{'|'.join(kw)}::{content_hash}"
            new_evidence_map[key] = {
                "content": agent_response or "[No findings from parser agent]",
                "timestamps": [],
                "count": 1,
                "first_seen": "N/A",
                "last_seen": "N/A",
                "file_path": logs_path,
                "pattern": "|".join(kw)
            }
        
        # Merge with existing evidence map
        existing_map = state.get("evidence_map", {})
        merged_map = merge_evidence_maps(existing_map, new_evidence_map)
        
        # Format a summary for last_logs_chunk
        summary = format_evidence_map_for_prompt(new_evidence_map, max_entries=10)
        
        return {
            "evidence_map": merged_map,
            "last_logs_chunk": summary,
            "last_generated_keywords": [],
        }
    
    except Exception as e:
        # Handle errors gracefully
        import hashlib
        error_content = f"[ERROR] Parser agent failed: {str(e)}\nLogs path: {logs_path}\nKeywords: {kw}"
        content_hash = hashlib.md5(error_content.encode()).hexdigest()[:12]
        key = f"{logs_path}::error::{content_hash}"
        
        error_evidence = {
            key: {
                "content": error_content,
                "timestamps": [],
                "count": 1,
                "first_seen": "N/A",
                "last_seen": "N/A",
                "file_path": logs_path,
                "pattern": "error"
            }
        }
        
        existing_map = state.get("evidence_map", {})
        merged_map = merge_evidence_maps(existing_map, error_evidence)
        
        return {
            "evidence_map": merged_map,
            "last_logs_chunk": error_content,
            "last_generated_keywords": []
        }

