import os
from typing import Optional, Dict


# LLM Configuration
# Default LLM endpoint for backward compatibility
LLM_ENDPOINT_NAME = os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")

# Per-Agent LLM Configuration
# Each agent can have its own LLM endpoint configured via environment variables
# or using the dictionary below. Environment variables take precedence.
AGENT_LLM_ENDPOINTS: Dict[str, str] = {
    "reasoning": os.getenv("REASONING_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-gpt-5")),
    "analyzer": os.getenv("ANALYZER_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
    "parser": os.getenv("PARSER_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
    "critic": os.getenv("CRITIC_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
    "supervisor": os.getenv("SUPERVISOR_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-3-7-sonnet")),
}

# Runtime LLM configuration (set via configure_agent_llms)
_RUNTIME_LLM_CONFIG: Dict[str, str] = {}


def configure_agent_llms(llm_config: Dict[str, str]) -> None:
    """
    Configure LLM endpoints for specific agents at runtime.

    This allows you to customize which LLM each agent uses without environment variables.
    Call this BEFORE creating the RCAAgent instance.

    Args:
        llm_config: Dictionary mapping agent names to LLM endpoint names

    Example:
        from multiAgentSystem.config import configure_agent_llms

        configure_agent_llms({
            "reasoning": "databricks-claude-sonnet-4-5",
            "supervisor": "databricks-claude-opus",
            "analyzer": "databricks-claude-haiku",
            "parser": "databricks-claude-haiku",
            "critic": "databricks-claude-sonnet-4-5"
        })

        from multiAgentSystem.agent_main import AGENT
        # AGENT will now use the configured LLMs

    Valid agent names: reasoning, analyzer, parser, critic, supervisor
    """
    global _RUNTIME_LLM_CONFIG

    valid_agents = {"reasoning", "analyzer", "parser", "critic", "supervisor"}

    for agent_name, endpoint in llm_config.items():
        if agent_name not in valid_agents:
            print(f"Warning: Unknown agent '{agent_name}'. Valid agents: {valid_agents}")
            continue
        _RUNTIME_LLM_CONFIG[agent_name] = endpoint
        print(f"✓ Configured {agent_name} agent to use: {endpoint}")


def get_agent_llm_endpoint(agent_name: str) -> str:
    """
    Get the LLM endpoint for a specific agent.

    Priority order:
    1. Runtime configuration (set via configure_agent_llms)
    2. AGENT_LLM_ENDPOINTS dictionary
    3. Default LLM_ENDPOINT_NAME

    Args:
        agent_name: Name of the agent (reasoning, analyzer, parser, critic, supervisor)

    Returns:
        LLM endpoint name
    """
    # Check runtime config first
    if agent_name in _RUNTIME_LLM_CONFIG:
        return _RUNTIME_LLM_CONFIG[agent_name]

    # Check AGENT_LLM_ENDPOINTS
    if agent_name in AGENT_LLM_ENDPOINTS:
        return AGENT_LLM_ENDPOINTS[agent_name]

    # Fallback to default
    return LLM_ENDPOINT_NAME


def show_llm_configuration() -> None:
    """
    Display the current LLM configuration for all agents.

    Useful for debugging and verification.
    """
    print("=" * 60)
    print("Current LLM Configuration:")
    print("=" * 60)

    for agent_name in ["reasoning", "analyzer", "parser", "critic", "supervisor"]:
        endpoint = get_agent_llm_endpoint(agent_name)
        source = "runtime" if agent_name in _RUNTIME_LLM_CONFIG else "default"
        print(f"  {agent_name:12s} -> {endpoint:40s} [{source}]")

    print("=" * 60)

# Loop controls
MAX_OUTER_ITERATIONS = int(os.getenv("MAX_OUTER_ITERATIONS", "6"))
MAX_ANALYZE_PARSE_LOOPS = int(os.getenv("MAX_ANALYZE_PARSE_LOOPS", "6"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# Graph recursion limit - controls max iterations through the agent workflow
# Increase this if you get GraphRecursionError for complex analyses
GRAPH_RECURSION_LIMIT = int(os.getenv("GRAPH_RECURSION_LIMIT", "200"))

# MLflow Configuration
MLFLOW_ENABLED = os.getenv("MLFLOW_ENABLED", "true").lower() == "true"

# Default keywords - ALWAYS included in log searches
# These core keywords are mandatory and will always be searched along with 
# any LLM-suggested keywords from the analyzer agent
DEFAULT_KEYWORDS = [
    "ERROR", 
    "Exception", 
    "Executor lost", 
    "OutOfMemoryError", 
    "GC overhead", 
    "Container exited"
]
