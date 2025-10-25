# Multi-Agent System for Root Cause Analysis

A supervisor-centric multi-agent system for analyzing Spark logs and performing root cause analysis using LangGraph and Databricks LLM.

## Architecture

The system uses a modular architecture with specialized tools for log analysis:

```
multiAgentSystem/
├── __init__.py           # Main exports
├── config.py             # Configuration constants and environment overrides
├── types.py              # Type definitions (including AgentState)
├── utils.py              # General utility and JSON functions
├── prompts.py            # ChatPromptTemplate objects for all agents
├── deps.py               # Dependency injection and LLM factory
├── exceptions.py         # Custom exception classes
├── graph.py              # StateGraph building and compilation
├── agent_main.ipynb      # RCAAgent wrapper and MLflow integration
├── agents/               # Individual agent implementations
│   ├── __init__.py
│   ├── supervisor.py     # Supervisor agent + routing logic
│   ├── reasoning.py      # Reasoning agent for evidence assessment
│   ├── analyzer.py       # Log analyzer for keyword generation
│   ├── parser.py         # Log parser with specialized tools
│   └── critic.py         # Critic agent for validation
└── tools/                # Specialized analysis tools
    ├── __init__.py
    ├── gc_analyzer.py    # GC log analysis tool
    └── grep_tool.py      # Log search tool
```

## Key Features

- **Modular Design**: Clear separation of concerns with dedicated modules for each component
- **Specialized Tools**: Dedicated tools for log analysis and pattern searching
- **Dependency Injection**: Centralized dependency management for better testability
- **Type Safety**: Comprehensive type definitions using TypedDict and Literal types
- **Configuration Management**: Environment-based configuration with sensible defaults
- **Error Handling**: Custom exception hierarchy for better error management
- **Reusable Components**: Utility functions and helpers for common operations

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Using the Jupyter Notebook

The system includes a Jupyter notebook (`agent_main.ipynb`) that uses the `%run` magic command to load the agent:

1. Open the notebook: `jupyter notebook multiAgentSystem/agent_main.ipynb`
2. Run the cells to load and use the agent
3. The notebook automatically loads all components using `%run ../load_agent.py`

### Using the Python API

```python
from multiAgentSystem import AGENT

# Prepare request
req = {
    "user_context": "After increasing executor memory and enabling AQE, the nightly ETL job intermittently fails. Symptoms include long GC pauses and 'executor lost' messages around the shuffle stage.",
    "logs_path": "s3://company-bucket/prod/spark-logs/job-1234/"
}

# Run analysis
result = AGENT.predict(req)

# Access results
print(f"Problem: {result['output']['problem']}")
print(f"Root Cause: {result['output']['rca']}")
print(f"Mitigation: {result['output']['mitigation']}")
print(f"Confidence: {result['output']['confidence']}")
```

## Streaming Usage

```python
# Stream progress events
for event in AGENT.predict_stream(req):
    if event['type'] == 'final':
        result = event['data']
        break
    print(f"Step: {event['node']} - {event['type']}")
```

## Configuration

The system can be configured via environment variables:

- `LLM_ENDPOINT_NAME`: Databricks LLM endpoint (default: "databricks-claude-3-7-sonnet")
- `MAX_OUTER_ITERATIONS`: Maximum outer iterations (default: 3)
- `MAX_ANALYZE_PARSE_LOOPS`: Maximum inner analysis loops (default: 3)
- `CONFIDENCE_THRESHOLD`: Confidence threshold for completion (default: 0.75)
- `MLFLOW_ENABLED`: Enable MLflow integration (default: true)

## Agent Workflow

1. **Supervisor**: Orchestrates the workflow and decides next actions
2. **Reasoning**: Assesses evidence sufficiency and generates hypotheses
3. **Analyzer**: Converts hypotheses into searchable keywords
4. **Parser**: Extracts and analyzes relevant log snippets using specialized tools
5. **Critic**: Validates draft outputs against evidence

## Specialized Tools

The system includes specialized tools for log analysis:

1. **GC Analyzer Tool**: Analyzes garbage collection logs to identify memory issues
   - Parses GC log formats and extracts key metrics
   - Provides summary statistics (events, pauses, memory freed)
   - Identifies problematic patterns (long pauses, full GCs)
   - Generates formatted tables for visualization

2. **Grep Path Tool**: Searches log files for specific patterns
   - Supports multiple search patterns with AND/OR logic
   - Handles large files efficiently
   - Returns structured results with line numbers and context

## Development

The modular structure makes it easy to:

- Add new agents by implementing them in the `agents/` directory
- Add new analysis tools in the `tools/` directory
- Modify prompts in `prompts.py`
- Adjust configuration in `config.py`
- Add new utilities in `utils.py`
- Extend error handling in `exceptions.py`