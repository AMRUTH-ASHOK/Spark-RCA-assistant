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
from multiAgentSystem.tools.grep_tool import grep_logs_tool
from multiAgentSystem.tools.gc_analyzer import analyze_gc_logs_tool
from multiAgentSystem.state import AgentState
from multiAgentSystem.evidence_manager import (
    process_grep_results,
    format_evidence_for_llm
)
from multiAgentSystem.exceptions import StateError

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


# LangChain tools for the parser agent
log_analysis_tools = [grep_logs_tool, analyze_gc_logs_tool]


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


@_trace_agent("parser_agent")
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
        # Create explicit error message for user context
        error_msg = (
            "[CRITICAL ERROR] No logs path provided in the initial state.\n"
            "The system cannot analyze logs without a valid path.\n\n"
            "USER ACTION REQUIRED:\n"
            "- Please provide 'logs_path' in the initial state\n"
            "- Format: '/Volumes/catalog/schema/volume/path/to/logs/'\n"
            "- Ensure the path is accessible and contains Spark log files\n\n"
            "Example initial state:\n"
            f"  logs_path: '/Volumes/amruthcatalogtest/default/testsparklogs/sample/'\n"
            f"  user_context: '{state.get('user_context', 'Your issue description...')}'"
        )
        
        evidence_map = state.get("evidence_map", {}).copy()
        evidence_map["CRITICAL_ERROR_NO_LOGS_PATH"] = {
            "count": 1,
            "timestamps": [],
            "files": [],
            "sample_lines": [error_msg],
            "variables": []
        }
        error_summary = format_evidence_for_llm(evidence_map, max_patterns=10)
        return {
            "evidence_map": evidence_map,
            "evidence_summary": error_summary,
            "last_logs_chunk": error_msg,
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
        
        # The agent may have used grep_logs_tool (enhanced format) or other tools
        # Look for tool call results in messages
        evidence_map = state.get("evidence_map", {}).copy()
        found_evidence = False
        tool_extraction_errors = []
        
        for msg in messages:
            if hasattr(msg, 'type') and msg.type == 'tool':
                try:
                    tool_output = msg.content
                    parsed = json.loads(tool_output)
                    
                    # Handle enhanced grep_logs_tool format (with evidence_map)
                    if isinstance(parsed, dict) and "evidence_map" in parsed:
                        # Merge the evidence_map from tool output
                        tool_evidence_map = parsed.get("evidence_map", {})
                        if isinstance(tool_evidence_map, dict) and tool_evidence_map:
                            # Merge evidence maps, combining counts for duplicate keys
                            for pattern_key, entry in tool_evidence_map.items():
                                if pattern_key in evidence_map:
                                    # Merge existing entry
                                    existing = evidence_map[pattern_key]
                                    existing["count"] += entry.get("count", 0)
                                    existing["timestamps"].extend(entry.get("timestamps", []))
                                    existing["files"].extend(entry.get("files", []))
                                    existing["variables"].extend(entry.get("variables", []))
                                    # Keep only first 3 sample lines
                                    if len(existing["sample_lines"]) < 3:
                                        existing["sample_lines"].extend(entry.get("sample_lines", []))
                                    # Deduplicate lists
                                    existing["timestamps"] = sorted(list(set(existing["timestamps"])))[:10]
                                    existing["files"] = list(set(existing["files"]))[:5]
                                    existing["variables"] = list(set(existing["variables"]))[:10]
                                    existing["sample_lines"] = existing["sample_lines"][:3]
                                else:
                                    # Add new entry
                                    evidence_map[pattern_key] = entry
                            found_evidence = True
                    
                    # Handle GC analyzer output (dict with stats/tables)
                    elif isinstance(parsed, dict) and ("summary" in parsed or "stats" in parsed):
                        # Store GC analysis as special evidence entry
                        gc_key = "GC_Analysis"
                        gc_summary = parsed.get("summary", "")
                        gc_driver_table = parsed.get("driver_gc_table", "")
                        gc_executor_table = parsed.get("executor_summary_table", "")
                        
                        combined_gc = f"{gc_summary}\n\n{gc_driver_table}\n\n{gc_executor_table}"
                        
                        evidence_map[gc_key] = {
                            "count": 1,
                            "timestamps": [],
                            "files": [logs_path],
                            "sample_lines": [combined_gc[:500]],  # Limit to 500 chars
                            "variables": []
                        }
                        found_evidence = True
                    
                    # Handle old format (list of grep results) - fallback for compatibility
                    elif isinstance(parsed, list):
                        grep_output = json.dumps(parsed)
                        evidence_map = process_grep_results(evidence_map, grep_output)
                        found_evidence = True
                        
                except json.JSONDecodeError as e:
                    tool_extraction_errors.append(f"JSON decode error: {str(e)}")
                except Exception as e:
                    tool_extraction_errors.append(f"Error parsing tool output: {str(e)}")
        
        # If no evidence found from tools, store agent's response
        if not found_evidence:
            import hashlib
            content_hash = hashlib.md5(agent_response.encode()).hexdigest()[:12]
            key = f"Parser_Response_{content_hash}"
            evidence_map[key] = {
                "count": 1,
                "timestamps": [],
                "files": [logs_path],
                "sample_lines": [agent_response[:500] if agent_response else "[No findings from parser agent]"],
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

