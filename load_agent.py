"""Helper script to load the RCA agent components for use in notebooks."""

import os
import sys

# Add the repository root so absolute imports resolve when running from notebooks
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multiAgentSystem.agent import (
    RCAAgent,
    AGENT,
    sample_request,
    MLFLOW_ENABLED,
    MAX_OUTER_ITERATIONS,
    MAX_ANALYZE_PARSE_LOOPS,
    CONFIDENCE_THRESHOLD,
)
from multiAgentSystem.types import AgentState
from multiAgentSystem.graph import build_graph
from multiAgentSystem.deps import get_deps


__all__ = [
    "RCAAgent",
    "AGENT",
    "sample_request",
    "AgentState",
    "build_graph",
    "get_deps",
    "MLFLOW_ENABLED",
    "MAX_OUTER_ITERATIONS",
    "MAX_ANALYZE_PARSE_LOOPS",
    "CONFIDENCE_THRESHOLD",
]


print("RCA Agent loaded successfully!")
print(f"Configuration: MAX_OUTER_ITERATIONS={MAX_OUTER_ITERATIONS}, CONFIDENCE_THRESHOLD={CONFIDENCE_THRESHOLD}")
print("Use AGENT.predict(request) to run analysis")
