# Experiments

This folder contains MLflow-tracked experiment notebooks for testing individual agents and the full workflow of the Spark RCA multi-agent system.

## Setup

### Prerequisites
1. **Databricks Runtime** with MLflow support
2. **Unity Catalog Volumes** with Spark log files
3. **LLM Endpoint** configured in `multiAgentSystem/config.py`

### Configuration

Update the logs path in each notebook to point to your actual Spark logs:

```python
REAL_LOGS_PATH = "/Volumes/<catalog>/<schema>/<volume>/logs/"
```

## MLflow Experiments

Each notebook creates a dedicated MLflow experiment under `/Shared/spark-rca/`:

| Experiment | Path | Description |
|------------|------|-------------|
| Supervisor | `/Shared/spark-rca/supervisor-agent` | Tests task orchestration and routing decisions |
| Reasoning | `/Shared/spark-rca/reasoning-agent` | Tests hypothesis generation and RCA summarization |
| Analyzer | `/Shared/spark-rca/analyzer-agent` | Tests keyword extraction for log searches |
| Parser | `/Shared/spark-rca/parser-agent` | Tests log search and evidence extraction |
| Critic | `/Shared/spark-rca/critic-agent` | Tests draft validation and confidence scoring |
| Full Workflow | `/Shared/spark-rca/full-workflow` | Tests end-to-end RCA workflow |

## Notebooks

### Individual Agent Tests

- **[test_supervisor_agent.ipynb](test_supervisor_agent.ipynb)** - Tests supervisor routing logic
  - Initial routing based on evidence state
  - Routing after log collection
  - Max iteration handling
  - High confidence early exit

- **[test_reasoning_agent.ipynb](test_reasoning_agent.ipynb)** - Tests reasoning capabilities
  - Initial hypothesis generation
  - RCA with evidence
  - Draft revision after critic feedback
  - Summary consolidation

- **[test_analyzer_agent.ipynb](test_analyzer_agent.ipynb)** - Tests analyzer output
  - OOM error keyword extraction
  - GC-related keyword extraction
  - Executor loss keyword extraction

- **[test_parser_agent.ipynb](test_parser_agent.ipynb)** - Tests log parsing
  - Valid log search with real files
  - Error handling: missing path
  - Error handling: missing keywords
  - GC analysis trigger detection

- **[test_critic_agent.ipynb](test_critic_agent.ipynb)** - Tests critic evaluation
  - Well-supported draft (high confidence)
  - Unsupported claims (low confidence)
  - Missing analysis areas feedback

### Full Workflow Test

- **[test_full_workflow.ipynb](test_full_workflow.ipynb)** - End-to-end workflow tests
  - OOM investigation scenario
  - Executor loss investigation scenario
  - GC pressure investigation scenario

## Metrics Logged

### Common Metrics
- `latency_ms` - Agent execution time
- `success` - Whether agent completed without error
- `test_passed` - Whether test assertions passed

### Agent-Specific Metrics

**Supervisor:**
- `routing_decision` - Next agent selected

**Reasoning:**
- `hypothesis_count` - Number of hypotheses generated
- `draft_length` - Length of RCA draft

**Analyzer:**
- `keyword_count` - Number of search keywords

**Parser:**
- `evidence_patterns` - Unique patterns found
- `evidence_occurrences` - Total occurrences

**Critic:**
- `confidence` - Draft confidence (0.0-1.0)
- `critic_approved` - Whether draft is approved
- `critique_length` - Length of critique text

**Full Workflow:**
- `total_agent_transitions` - Number of agent calls
- `iteration_count` - Outer loop iterations
- `final_confidence` - Final report confidence
- `pdf_generated` - Whether PDF was created

## Running Tests

### In Databricks

1. Upload the entire `experiments/` folder to your workspace
2. Open a notebook (e.g., `test_supervisor_agent.ipynb`)
3. Attach to a cluster with the required dependencies
4. Update `REAL_LOGS_PATH` if needed
5. Run all cells

### Locally (Limited)

Some tests work locally with mock data:
```bash
cd experiments
jupyter notebook test_supervisor_agent.ipynb
```

Note: Tests requiring actual log files will fail locally.

## Files

| File | Description |
|------|-------------|
| `mlflow_setup.py` | MLflow experiment configuration utilities |
| `mock_data.py` | Test fixtures and mock states for all agents |
| `__init__.py` | Package exports |

## Viewing Results

After running tests, view results in the MLflow UI:

1. Navigate to **Experiments** in Databricks
2. Find experiments under `/Shared/spark-rca/`
3. Compare runs across scenarios
4. View logged metrics, parameters, and artifacts

## Adding New Tests

1. Add test scenarios to `mock_data.py`:
```python
AGENT_TEST_STATES["new_scenario"] = {
    "description": "Description of test",
    "state": { ... },
    "expected": { ... }
}
```

2. Add test cell to the relevant notebook:
```python
result, passed, latency = run_agent_test("new_scenario")
```
