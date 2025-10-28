"""
Dependency injection container and LLM factory for the multi-agent system.
"""

from typing import Optional, Any, Dict
from databricks_langchain import ChatDatabricks
from langchain_core.output_parsers import StrOutputParser

from multiAgentSystem.config import LLM_ENDPOINT_NAME, AGENT_LLM_ENDPOINTS
from multiAgentSystem.exceptions import ConfigurationError, LLMError

# Global dependencies instance
_deps: Optional['Dependencies'] = None


def make_llm(endpoint: Optional[str] = None, use_responses_api: bool = False, **kwargs) -> ChatDatabricks:
    """
    Create a configured ChatDatabricks LLM instance.
    
    Args:
        endpoint: Optional specific endpoint name. If None, uses LLM_ENDPOINT_NAME
        use_responses_api: Whether to use responses API
        **kwargs: Additional arguments to pass to ChatDatabricks
        
    Returns:
        Configured ChatDatabricks instance
        
    Raises:
        LLMError: If LLM creation fails
    """
    endpoint_name = endpoint or LLM_ENDPOINT_NAME
    try:
        return ChatDatabricks(
            endpoint=endpoint_name,
            use_responses_api=use_responses_api,
            **kwargs
        )
    except Exception as e:
        raise LLMError(f"Failed to create LLM with endpoint '{endpoint_name}': {e}") from e


def create_str_parser() -> StrOutputParser:
    """Create a string output parser."""
    return StrOutputParser()


class Dependencies:
    """Container for all system dependencies."""
    
    def __init__(self):
        # Default LLM for backward compatibility
        self.llm = make_llm()
        self.str_parser = create_str_parser()
        
        # Per-agent LLM instances
        self._agent_llms: Dict[str, ChatDatabricks] = {}
        self._initialize_agent_llms()
        
        self._mlflow = None
        self._has_mlflow = False
        
        # Initialize MLflow if available
        try:
            import mlflow
            self._mlflow = mlflow
            self._has_mlflow = True
        except ImportError:
            self._has_mlflow = False
    
    def _initialize_agent_llms(self):
        """Initialize LLM instances for each agent based on configuration."""
        for agent_name, endpoint in AGENT_LLM_ENDPOINTS.items():
            try:
                self._agent_llms[agent_name] = make_llm(endpoint=endpoint)
            except LLMError as e:
                # Log error but don't fail initialization
                print(f"Warning: Failed to initialize LLM for agent '{agent_name}': {e}")
                # Fall back to default LLM
                self._agent_llms[agent_name] = self.llm
    
    def get_agent_llm(self, agent_name: str) -> ChatDatabricks:
        """
        Get the LLM instance configured for a specific agent.
        
        Args:
            agent_name: Name of the agent (reasoning, analyzer, parser, critic, supervisor)
            
        Returns:
            ChatDatabricks instance for the agent
            
        Raises:
            ConfigurationError: If agent name is not recognized
        """
        if agent_name not in self._agent_llms:
            raise ConfigurationError(f"Unknown agent name: {agent_name}. Must be one of: {list(self._agent_llms.keys())}")
        return self._agent_llms[agent_name]
    
    @property
    def mlflow(self):
        """Get MLflow instance if available."""
        if not self._has_mlflow:
            raise ConfigurationError("MLflow not available")
        return self._mlflow
    
    @property
    def has_mlflow(self) -> bool:
        """Check if MLflow is available."""
        return self._has_mlflow


def get_deps() -> Dependencies:
    """Get the global dependencies instance."""
    global _deps
    if _deps is None:
        _deps = Dependencies()
    return _deps


def reset_deps():
    """Reset dependencies (useful for testing)."""
    global _deps
    _deps = None
