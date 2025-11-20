"""
Log Parser Agent for finding and analyzing log patterns.

This agent uses LangChain tools to autonomously decide between:
1. grep_logs: Search logs for specific keywords
2. analyze_gc_logs: Analyze GC logs when memory issues are suspected

The agent outputs evidence in a deduplicated format to optimize token usage.
"""

import json
from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from multiAgentSystem.deps import get_deps
from multiAgentSystem.tools.grep_tool import grep_path_tool
from multiAgentSystem.tools.gc_analyzer import GC_analyzer_tool

log_analysis_tools = [grep_path_tool, GC_analyzer_tool]
from multiAgentSystem.state import AgentState
from multiAgentSystem.evidence_manager import (
    process_grep_results,
    format_evidence_for_llm
)


# Create the parser agent with access to log analysis tools
def create_parser_agent():
    """
    Create a ReAct agent that can autonomously choose between log analysis tools.
    
    Returns:
        LangGraph ReAct agent with log analysis capabilities
    """
    llm = get_deps().get_agent_llm("parser")
    
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
    
    # Create the agent with just model and tools
    # System prompt will be included in the messages when invoking
    agent = create_react_agent(
        llm,
        tools=log_analysis_tools
    )
    
    # Store the system prompt for use during invocation
    agent.system_prompt = system_prompt
    
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
        # Merge error into existing evidence map
        evidence_map = state.get("evidence_map", {}).copy()
        evidence_map["error_no_path"] = {
            "count": 1,
            "timestamps": [],
            "files": [],
            "sample_lines": ["[ERROR] No logs path provided. Please provide a valid logs path to analyze."],
            "variables": []
        }
        error_summary = format_evidence_for_llm(evidence_map, max_patterns=10)
        return {
            "evidence_map": evidence_map,
            "evidence_summary": error_summary,
            "last_logs_chunk": "Error: No logs path provided",
            "last_generated_keywords": []
        }
    
    if not kw or len(kw) == 0:
        # Merge error into existing evidence map
        evidence_map = state.get("evidence_map", {}).copy()
        evidence_map["error_no_keywords"] = {
            "count": 1,
            "timestamps": [],
            "files": [logs_path],
            "sample_lines": [f"[ERROR] No keywords provided for search. Path: {logs_path}"],
            "variables": []
        }
        error_summary = format_evidence_for_llm(evidence_map, max_patterns=10)
        return {
            "evidence_map": evidence_map,
            "evidence_summary": error_summary,
            "last_logs_chunk": "Error: No keywords provided",
            "last_generated_keywords": []
        }
    
    try:
        # Create input for the parser agent
        agent = get_parser_agent()
        
        # Prepare messages with system prompt
        agent_input = {
            "messages": [
                SystemMessage(content=agent.system_prompt),
                HumanMessage(content=f"""Analyze Spark logs to find evidence for the following investigation:

Logs Path: {logs_path}
Keywords to search: {', '.join(kw)}

Task: Use the available tools to search the logs and extract relevant evidence.
Decide which tool(s) to use based on the keywords and what you find.""")
            ]
        }
        
        # Invoke the parser agent
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
        
        # Process grep results if we found any
        evidence_map = state.get("evidence_map", {}).copy()
        if grep_results:
            # Convert grep results to JSON string for process_grep_results
            grep_output = json.dumps(grep_results)
            evidence_map = process_grep_results(evidence_map, grep_output)
        else:
            # If no structured grep results, store the agent's response as evidence
            import hashlib
            content_hash = hashlib.md5(agent_response.encode()).hexdigest()[:12]
            key = f"{logs_path}::{'|'.join(kw)}::{content_hash}"
            evidence_map[key] = {
                "count": 1,
                "timestamps": [],
                "files": [logs_path],
                "sample_lines": [agent_response or "[No findings from parser agent]"],
                "variables": []
            }
        
        # Format a summary for last_logs_chunk and evidence_summary
        summary = format_evidence_for_llm(evidence_map, max_patterns=10)
        
        return {
            "evidence_map": evidence_map,
            "evidence_summary": summary,
            "last_logs_chunk": summary,
            "last_generated_keywords": [],
        }
    
    except Exception as e:
        # Handle errors gracefully
        import hashlib
        error_content = f"[ERROR] Parser agent failed: {str(e)}\nLogs path: {logs_path}\nKeywords: {kw}"
        content_hash = hashlib.md5(error_content.encode()).hexdigest()[:12]
        key = f"{logs_path}::error::{content_hash}"
        
        # Merge error into existing evidence map
        evidence_map = state.get("evidence_map", {}).copy()
        evidence_map[key] = {
            "count": 1,
            "timestamps": [],
            "files": [logs_path],
            "sample_lines": [error_content],
            "variables": []
        }
        
        error_summary = format_evidence_for_llm(evidence_map, max_patterns=10)
        
        return {
            "evidence_map": evidence_map,
            "evidence_summary": error_summary,
            "last_logs_chunk": error_content,
            "last_generated_keywords": []
        }

