"""
MLflow Setup and Utilities for Spark RCA Experiments.

This module provides centralized MLflow experiment configuration and helper functions
for tracking agent performance in Databricks.
"""

import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager

try:
    import mlflow
    from mlflow.entities import SpanType
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None

# Experiment names for each agent and full workflow
EXPERIMENT_NAMES = {
    "supervisor": "/Shared/spark-rca/supervisor-agent",
    "reasoning": "/Shared/spark-rca/reasoning-agent",
    "analyzer": "/Shared/spark-rca/analyzer-agent",
    "parser": "/Shared/spark-rca/parser-agent",
    "critic": "/Shared/spark-rca/critic-agent",
    "full_workflow": "/Shared/spark-rca/full-workflow",
}


def get_experiment_name(agent_name: str) -> str:
    """
    Get the MLflow experiment name for a given agent.
    
    Args:
        agent_name: Name of the agent (supervisor, reasoning, analyzer, parser, critic, full_workflow)
        
    Returns:
        Full MLflow experiment path
        
    Raises:
        ValueError: If agent_name is not recognized
    """
    if agent_name not in EXPERIMENT_NAMES:
        raise ValueError(f"Unknown agent: {agent_name}. Valid agents: {list(EXPERIMENT_NAMES.keys())}")
    return EXPERIMENT_NAMES[agent_name]


def setup_experiment(agent_name: str, tags: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Set up MLflow experiment for a specific agent.
    
    This function should be called before running tests for each agent.
    It creates the experiment if it doesn't exist and sets it as active.
    
    Args:
        agent_name: Name of the agent (supervisor, reasoning, analyzer, parser, critic, full_workflow)
        tags: Optional tags to set on the experiment
        
    Returns:
        Experiment ID if MLflow is available, None otherwise
    """
    if not MLFLOW_AVAILABLE:
        print("Warning: MLflow not available. Experiment tracking disabled.")
        return None
    
    experiment_name = get_experiment_name(agent_name)
    
    # Create or get the experiment
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(
            experiment_name,
            tags=tags or {"system": "spark-rca", "agent": agent_name}
        )
    else:
        experiment_id = experiment.experiment_id
    
    # Set as active experiment
    mlflow.set_experiment(experiment_name)
    
    print(f"✓ MLflow experiment set: {experiment_name} (ID: {experiment_id})")
    return experiment_id


def log_agent_metrics(
    latency_ms: float,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    success: bool = True,
    additional_metrics: Optional[Dict[str, float]] = None
) -> None:
    """
    Log standard metrics for an agent invocation.
    
    Args:
        latency_ms: Time taken in milliseconds
        input_tokens: Optional input token count
        output_tokens: Optional output token count
        success: Whether the invocation was successful
        additional_metrics: Additional metrics to log
    """
    if not MLFLOW_AVAILABLE:
        return
    
    mlflow.log_metric("latency_ms", latency_ms)
    mlflow.log_metric("success", 1.0 if success else 0.0)
    
    if input_tokens is not None:
        mlflow.log_metric("input_tokens", input_tokens)
    if output_tokens is not None:
        mlflow.log_metric("output_tokens", output_tokens)
    
    if additional_metrics:
        for name, value in additional_metrics.items():
            mlflow.log_metric(name, value)


@contextmanager
def create_agent_run(
    agent_name: str,
    run_name: Optional[str] = None,
    scenario: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
):
    """
    Context manager for creating an MLflow run for agent testing.
    
    Args:
        agent_name: Name of the agent being tested
        run_name: Optional name for the run
        scenario: Optional scenario description
        tags: Additional tags for the run
        
    Yields:
        MLflow run context (or None if MLflow not available)
        
    Example:
        with create_agent_run("supervisor", scenario="initial_state") as run:
            result = supervisor_node(test_state)
            log_agent_metrics(latency_ms=100, success=True)
    """
    if not MLFLOW_AVAILABLE:
        yield None
        return
    
    # Setup experiment first
    setup_experiment(agent_name)
    
    # Prepare run tags
    run_tags = {"agent": agent_name}
    if scenario:
        run_tags["scenario"] = scenario
    if tags:
        run_tags.update(tags)
    
    # Create run name if not provided
    if not run_name:
        run_name = f"{agent_name}_{scenario or 'test'}_{int(time.time())}"
    
    with mlflow.start_run(run_name=run_name, tags=run_tags) as run:
        mlflow.log_param("agent", agent_name)
        if scenario:
            mlflow.log_param("scenario", scenario)
        yield run


def track_agent_call(agent_name: str, scenario: Optional[str] = None):
    """
    Decorator to track agent function calls with MLflow.
    
    Args:
        agent_name: Name of the agent
        scenario: Optional scenario name
        
    Returns:
        Decorated function with MLflow tracking
        
    Example:
        @track_agent_call("supervisor", scenario="test")
        def test_supervisor():
            return supervisor_node(state)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            result = None
            error_msg = None
            
            try:
                with create_agent_run(agent_name, scenario=scenario):
                    result = func(*args, **kwargs)
                    
                    # Log timing
                    latency_ms = (time.time() - start_time) * 1000
                    log_agent_metrics(latency_ms=latency_ms, success=True)
                    
                    # Log result summary if it's a dict
                    if isinstance(result, dict):
                        if MLFLOW_AVAILABLE:
                            mlflow.log_dict(result, "output.json")
                    
                    return result
                    
            except Exception as e:
                success = False
                error_msg = str(e)
                latency_ms = (time.time() - start_time) * 1000
                
                if MLFLOW_AVAILABLE:
                    log_agent_metrics(latency_ms=latency_ms, success=False)
                    mlflow.log_param("error", error_msg[:500])
                
                raise
                
        return wrapper
    return decorator


def enable_autologging():
    """
    Enable MLflow autologging for LangChain.
    
    Call this once at the start of your session/notebook.
    """
    if not MLFLOW_AVAILABLE:
        print("Warning: MLflow not available. Autologging not enabled.")
        return
    
    mlflow.langchain.autolog(
        log_input_examples=True,
        log_model_signatures=True,
        log_models=False,  # Don't log models to save space
        log_traces=True,   # Enable trace logging
    )
    print("✓ MLflow LangChain autologging enabled")


def log_state_snapshot(state: Dict[str, Any], prefix: str = "state") -> None:
    """
    Log a snapshot of agent state to MLflow.
    
    Args:
        state: Agent state dictionary
        prefix: Prefix for the artifact name
    """
    if not MLFLOW_AVAILABLE:
        return
    
    # Extract key state values as params/metrics
    if "iteration" in state:
        mlflow.log_metric(f"{prefix}_iteration", state["iteration"])
    if "confidence" in state:
        mlflow.log_metric(f"{prefix}_confidence", state["confidence"])
    if "analyze_parse_loops" in state:
        mlflow.log_metric(f"{prefix}_analyze_loops", state["analyze_parse_loops"])
    if "critic_approved" in state:
        mlflow.log_metric(f"{prefix}_critic_approved", 1.0 if state["critic_approved"] else 0.0)
    
    # Log full state as artifact
    mlflow.log_dict(state, f"{prefix}_snapshot.json")
