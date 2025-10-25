"""
Custom exceptions for the multi-agent system.
"""


class MultiAgentSystemError(Exception):
    """Base exception for multi-agent system errors."""
    pass


class LLMError(MultiAgentSystemError):
    """Exception raised when LLM operations fail."""
    pass


class ConfigurationError(MultiAgentSystemError):
    """Exception raised when configuration is invalid."""
    pass


class StateError(MultiAgentSystemError):
    """Exception raised when agent state is invalid."""
    pass


class GraphError(MultiAgentSystemError):
    """Exception raised when graph operations fail."""
    pass
