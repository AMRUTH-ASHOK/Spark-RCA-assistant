"""
Dependency injection container and LLM factory for the multi-agent system.
"""

from typing import Optional, Any
from databricks_langchain import ChatDatabricks
from langchain_core.output_parsers import StrOutputParser

from multiAgentSystem.config import LLM_ENDPOINT_NAME
from multiAgentSystem.exceptions import ConfigurationError, LLMError

# Global dependencies instance
_deps: Optional['Dependencies'] = None


def make_llm(use_responses_api: bool = False, **kwargs) -> ChatDatabricks:
    """
    Create a configured ChatDatabricks LLM instance.
    
    Args:
        use_responses_api: Whether to use responses API
        **kwargs: Additional arguments to pass to ChatDatabricks
        
    Returns:
        Configured ChatDatabricks instance
        
    Raises:
        LLMError: If LLM creation fails
    """
    try:
        return ChatDatabricks(
            endpoint=LLM_ENDPOINT_NAME,
            use_responses_api=use_responses_api,
            **kwargs
        )
    except Exception as e:
        raise LLMError(f"Failed to create LLM: {e}") from e


def create_str_parser() -> StrOutputParser:
    """Create a string output parser."""
    return StrOutputParser()


class Dependencies:
    """Container for all system dependencies."""
    
    def __init__(self):
        self.llm = make_llm()
        self.str_parser = create_str_parser()
        self._mlflow = None
        self._has_mlflow = False
        
        # Initialize MLflow if available
        try:
            import mlflow
            self._mlflow = mlflow
            self._has_mlflow = True
        except ImportError:
            self._has_mlflow = False
    
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
