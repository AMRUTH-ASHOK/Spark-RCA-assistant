"""
Helper script to load the RCA agent components for use in notebooks.
This script uses absolute imports to avoid relative import issues.
"""

import sys
import os
from typing import Dict, Any, Generator

# Add the parent directory to the path so we can use absolute imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import components with absolute imports
from multiAgentSystem.types import AgentState
from multiAgentSystem.graph import build_graph
from multiAgentSystem.deps import get_deps
from multiAgentSystem.config import MLFLOW_ENABLED, MAX_OUTER_ITERATIONS, MAX_ANALYZE_PARSE_LOOPS, CONFIDENCE_THRESHOLD

# Create the RCA Agent class
class RCAAgent:
    """Thin wrapper exposing predict() and predict_stream()."""

    def __init__(self, graph=None):
        self.graph = graph or build_graph()

    def _init_state(self, request: Dict[str, Any]) -> AgentState:
        """Initialize agent state from request."""
        user_context = request.get("user_context")
        if not user_context:
            msgs = request.get("input") or []
            if isinstance(msgs, list):
                user_parts = [m.get("content", "") for m in msgs if isinstance(m, dict) and m.get("role") == "user"]
                user_context = "\n\n".join([p for p in user_parts if p]) or ""
        
        logs_path = request.get("logs_path", "") or request.get("path", "") or ""
        
        return AgentState(
            user_context=user_context or "",
            logs_path=logs_path,
            iteration=0,
            hypotheses=[],
            keywords=[],
            evidence=[],
            last_logs_chunk="",
            analyzer_satisfied=False,
            draft={"problem": "", "rca": "", "mitigation": ""},
            confidence=0.0,
            critic_approved=False,
            critique="",
            last_status="",
            next_action="",
            supervisor_rationale="",
            analyze_parse_loops=0,
        )

    def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Run the multi-agent system and return final results."""
        final_state: AgentState = self.graph.invoke(self._init_state(request))
        return {
            "output": {
                "problem": final_state.get("draft", {}).get("problem", ""),
                "rca": final_state.get("draft", {}).get("rca", ""),
                "mitigation": final_state.get("draft", {}).get("mitigation", ""),
                "confidence": float(final_state.get("confidence", 0.0)),
                "iterations": int(final_state.get("iteration", 0)),
                "keywords": final_state.get("keywords", []),
                "evidence": final_state.get("evidence", []),
                "critic_approved": bool(final_state.get("critic_approved", False)),
                "critique": final_state.get("critique", ""),
                "supervisor_rationale": final_state.get("supervisor_rationale", ""),
            }
        }

    def predict_stream(self, request: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """Run the multi-agent system and yield progress events."""
        state = self._init_state(request)
        for ev in self.graph.stream(state, stream_mode="updates"):
            event_type = ev.get("event")
            node = ev.get("name")
            data = ev.get("data", {}) or {}
            yield {"type": event_type, "node": node, "data": data}
        
        yield {"type": "final", "node": None, "data": self.predict(request)}

# Initialize MLflow if enabled
if MLFLOW_ENABLED:
    try:
        deps = get_deps()
        if deps.has_mlflow:
            deps.mlflow.langchain.autolog()
    except Exception:
        pass

# Create singleton instance
AGENT = RCAAgent()

# Optional MLflow model registration
if MLFLOW_ENABLED:
    try:
        deps = get_deps()
        if deps.has_mlflow:
            deps.mlflow.models.set_model(AGENT)
    except Exception:
        pass

# Create a sample request for testing
sample_request = {
    "user_context": (
        "After increasing executor memory and enabling AQE, the nightly ETL job intermittently fails. "
        "Symptoms include long GC pauses and 'executor lost' messages around the shuffle stage."
    ),
    "logs_path": "s3://company-bucket/prod/spark-logs/job-1234/"
}

print("RCA Agent loaded successfully!")
print(f"Configuration: MAX_OUTER_ITERATIONS={MAX_OUTER_ITERATIONS}, CONFIDENCE_THRESHOLD={CONFIDENCE_THRESHOLD}")
print("Use AGENT.predict(request) to run analysis")
