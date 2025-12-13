"""
MLflow Experiment Tracking for Spark RCA Multi-Agent System.

This package provides experiment tracking utilities and individual agent test harnesses
for evaluating agent performance in Databricks.

Experiments:
- spark-rca/supervisor-agent: Supervisor routing decisions
- spark-rca/reasoning-agent: Hypothesis generation and RCA summarization
- spark-rca/analyzer-agent: Keyword generation from hypotheses
- spark-rca/parser-agent: Log search and evidence extraction
- spark-rca/critic-agent: Draft validation and confidence adjustment
- spark-rca/full-workflow: End-to-end RCA workflow
"""

from experiments.mlflow_setup import (
    setup_experiment,
    get_experiment_name,
    log_agent_metrics,
    create_agent_run,
    EXPERIMENT_NAMES,
)

__all__ = [
    "setup_experiment",
    "get_experiment_name",
    "log_agent_metrics",
    "create_agent_run",
    "EXPERIMENT_NAMES",
]
