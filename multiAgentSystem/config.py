"""
Configuration constants and environment overrides for the multi-agent system.
"""

import os
from typing import Optional, Dict


# LLM Configuration
# Default LLM endpoint for backward compatibility
LLM_ENDPOINT_NAME = os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")

# Per-Agent LLM Configuration
# Each agent can have its own LLM endpoint configured via environment variables
# or using the dictionary below. Environment variables take precedence.
AGENT_LLM_ENDPOINTS: Dict[str, str] = {
    "reasoning": os.getenv("REASONING_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
    "analyzer": os.getenv("ANALYZER_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
    "parser": os.getenv("PARSER_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
    "critic": os.getenv("CRITIC_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
    "supervisor": os.getenv("SUPERVISOR_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
}

# You can override the above by directly editing this dictionary:
# AGENT_LLM_ENDPOINTS = {
#     "reasoning": "databricks-claude-sonnet-3.7",
#     "analyzer": "databricks-llama-4-maverick",
#     "parser": "databricks-gpt-4",
#     "critic": "databricks-claude-sonnet-3.7",
#     "supervisor": "databricks-claude-sonnet-3.7",
# }

# Loop controls
MAX_OUTER_ITERATIONS = int(os.getenv("MAX_OUTER_ITERATIONS", "3"))
MAX_ANALYZE_PARSE_LOOPS = int(os.getenv("MAX_ANALYZE_PARSE_LOOPS", "3"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# MLflow Configuration
MLFLOW_ENABLED = os.getenv("MLFLOW_ENABLED", "true").lower() == "true"

# Default keywords for fallback analysis
DEFAULT_KEYWORDS = [
    "ERROR", 
    "Exception", 
    "Executor lost", 
    "OutOfMemoryError", 
    "GC overhead", 
    "Container exited"
]
