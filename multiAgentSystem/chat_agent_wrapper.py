"""
MLflow ChatAgent wrapper for the Spark RCA Multi-Agent System.

This wrapper enables:
1. Automatic authentication passthrough for Databricks resources
2. AI Playground integration
3. Standardized message format for deployment
4. Native streaming support
5. One-line deployment with agents.deploy()

See: https://mlflow.org/docs/latest/python_api/mlflow.pyfunc.html#mlflow.pyfunc.ChatAgent
"""

from typing import Any, Generator, Optional
from langgraph.graph.state import CompiledStateGraph

from mlflow.pyfunc import ChatAgent
from mlflow.types.agent import (
    ChatAgentChunk,
    ChatAgentMessage,
    ChatAgentResponse,
    ChatContext,
)

from multiAgentSystem.state import AgentState
from multiAgentSystem.graph import build_graph


class RCALangGraphChatAgent(ChatAgent):
    """
    MLflow ChatAgent wrapper for the Spark RCA LangGraph multi-agent system.
    
    This enables:
    - Automatic authentication passthrough for Unity Catalog Volumes, Model Serving
    - AI Playground integration for testing and feedback
    - Standard message format for Databricks deployment
    - Native streaming support in Databricks UI
    
    Architecture:
        User Query → ChatAgent → LangGraph StateGraph → Multi-Agent System → Response
        
    The wrapper converts between:
    - ChatAgentMessage (Databricks standard) ↔ AgentState (internal format)
    - ChatAgentResponse (Databricks standard) ↔ Final output (internal format)
    """
    
    def __init__(self, agent: Optional[CompiledStateGraph] = None):
        """
        Initialize the ChatAgent wrapper.
        
        Args:
            agent: Compiled LangGraph StateGraph. If None, builds from scratch.
        """
        self.agent = agent or build_graph()
    
    def _messages_to_state(
        self, 
        messages: list[ChatAgentMessage],
        custom_inputs: Optional[dict[str, Any]] = None
    ) -> AgentState:
        """
        Convert ChatAgent messages to internal AgentState format.
        
        Extracts:
        - user_context: from user messages
        - logs_path: from custom_inputs or message content
        
        Args:
            messages: List of ChatAgentMessage objects
            custom_inputs: Optional custom parameters (e.g., logs_path)
            
        Returns:
            AgentState initialized for processing
        """
        # Extract user context from messages
        user_messages = [
            msg.content 
            for msg in messages 
            if msg.role == "user" and msg.content
        ]
        user_context = "\n\n".join(user_messages) if user_messages else ""
        
        # Extract logs_path from custom_inputs or try to parse from message
        logs_path = ""
        if custom_inputs:
            logs_path = custom_inputs.get("logs_path", "") or custom_inputs.get("path", "")
        
        # If not in custom_inputs, try to extract from message content
        # (handles cases like "analyze logs at /Volumes/...")
        if not logs_path and user_context:
            import re
            # Look for /Volumes/ paths or other log paths
            path_match = re.search(r'(/Volumes/[^\s]+|/[^\s]+/logs?[^\s]*)', user_context)
            if path_match:
                logs_path = path_match.group(1)
        
        return AgentState(
            user_context=user_context,
            logs_path=logs_path,
            iteration=0,
            hypotheses=[],
            keywords=[],
            evidence=[],
            evidence_map={},
            last_logs_chunk="",
            analyzer_satisfied=False,
            last_generated_keywords=[],
            draft={"problem": "", "rca": "", "mitigation": ""},
            confidence=0.0,
            critic_approved=False,
            critique="",
            last_status="",
            next_action="",
            supervisor_rationale="",
            analyze_parse_loops=0,
            pdf_report_path=None,
        )
    
    def _state_to_response(self, final_state: AgentState) -> ChatAgentResponse:
        """
        Convert final AgentState to ChatAgentResponse format.
        
        Formats the multi-agent system output as a structured assistant message.
        
        Args:
            final_state: Final state after agent execution
            
        Returns:
            ChatAgentResponse with formatted RCA results
        """
        draft = final_state.get("draft", {})
        problem = draft.get("problem", "")
        rca = draft.get("rca", "")
        mitigation = draft.get("mitigation", "")
        confidence = float(final_state.get("confidence", 0.0))
        iterations = int(final_state.get("iteration", 0))
        critic_approved = bool(final_state.get("critic_approved", False))
        
        # Format output as structured message
        content = f"""## Root Cause Analysis Results

### Problem Summary
{problem}

### Root Cause Analysis
{rca}

### Recommended Mitigation
{mitigation}

---
**Analysis Confidence:** {confidence:.2%}  
**Iterations:** {iterations}  
**Critic Approved:** {'✅ Yes' if critic_approved else '❌ No'}
"""
        
        # Add critique if not approved
        critique = final_state.get("critique", "")
        if critique and not critic_approved:
            content += f"\n\n**Critic Feedback:**\n{critique}"
        
        # Create assistant message
        message = ChatAgentMessage(
            role="assistant",
            content=content
        )
        
        return ChatAgentResponse(messages=[message])
    
    def predict(
        self,
        messages: list[ChatAgentMessage],
        context: Optional[ChatContext] = None,
        custom_inputs: Optional[dict[str, Any]] = None,
    ) -> ChatAgentResponse:
        """
        Process messages through the multi-agent system (non-streaming).
        
        Flow:
        1. Convert ChatAgent messages → AgentState
        2. Run LangGraph multi-agent system
        3. Convert final state → ChatAgentResponse
        
        Args:
            messages: User messages in ChatAgent format
            context: Optional chat context (not used currently)
            custom_inputs: Optional parameters like logs_path
            
        Returns:
            ChatAgentResponse with RCA results
        """
        # Convert to internal format
        initial_state = self._messages_to_state(messages, custom_inputs)
        
        # Run multi-agent system
        final_state = self.agent.invoke(initial_state)
        
        # Convert back to ChatAgent format
        return self._state_to_response(final_state)
    
    def predict_stream(
        self,
        messages: list[ChatAgentMessage],
        context: Optional[ChatContext] = None,
        custom_inputs: Optional[dict[str, Any]] = None,
    ) -> Generator[ChatAgentChunk, None, None]:
        """
        Process messages through the multi-agent system with streaming.
        
        Yields progress updates as the multi-agent system executes.
        
        Flow:
        1. Convert ChatAgent messages → AgentState
        2. Stream LangGraph execution updates
        3. Yield intermediate progress as ChatAgentChunks
        4. Yield final response as final chunk
        
        Args:
            messages: User messages in ChatAgent format
            context: Optional chat context (not used currently)
            custom_inputs: Optional parameters like logs_path
            
        Yields:
            ChatAgentChunk objects with delta updates
        """
        # Convert to internal format
        initial_state = self._messages_to_state(messages, custom_inputs)
        
        # Stream multi-agent execution
        for event in self.agent.stream(initial_state, stream_mode="updates"):
            # Extract node information from event
            for node_name, node_data in event.items():
                # Create progress update message
                status_update = f"🔄 **{node_name}** agent processing..."
                
                # Add specific details based on node
                if node_name == "reasoning":
                    if node_data.get("last_status") == "summarized":
                        status_update = "✅ **Reasoning** complete - draft generated"
                    else:
                        status_update = "🔍 **Reasoning** assessing evidence..."
                elif node_name == "analyzer":
                    new_kws = node_data.get("last_generated_keywords", [])
                    if new_kws:
                        status_update = f"🔎 **Analyzer** generated keywords: {', '.join(new_kws[:3])}"
                elif node_name == "parser":
                    status_update = "📄 **Parser** searching logs..."
                elif node_name == "critic":
                    approved = node_data.get("critic_approved")
                    if approved:
                        status_update = "✅ **Critic** approved draft"
                    else:
                        status_update = "❌ **Critic** requesting revisions"
                elif node_name == "supervisor":
                    next_action = node_data.get("next_action", "")
                    if next_action:
                        status_update = f"🎯 **Supervisor** routing to {next_action}"
                
                # Yield progress chunk
                yield ChatAgentChunk(
                    delta=ChatAgentMessage(
                        role="assistant",
                        content=status_update
                    )
                )
        
        # Get final state and yield final response
        final_state = self.agent.invoke(initial_state)
        final_response = self._state_to_response(final_state)
        
        # Yield final message as chunk
        for message in final_response.messages:
            yield ChatAgentChunk(delta=message)
