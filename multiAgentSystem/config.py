"""
Configuration constants and environment overrides for the multi-agent system.
"""

import os
from typing import Optional


# LLM Configuration
LLM_ENDPOINT_NAME = os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")

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
