# Spark RCA Assistant - Multi-Agent System

A sophisticated multi-agent system for performing Root Cause Analysis (RCA) on Apache Spark logs using LangGraph and LLMs.

## Overview

This system uses a coordinated team of AI agents to analyze Spark execution logs, identify problems, determine root causes, and suggest mitigation strategies. It's designed to work in Databricks environments and can analyze various Spark failure modes including OOM errors, executor losses, GC issues, and more.

## Architecture

### Multi-Agent Design

The system employs a **hierarchical multi-agent architecture** with the following specialized agents:

1. **Supervisor Agent** - Orchestrates the overall workflow and decides which agent to invoke next
2. **Reasoning Agent** - Assesses evidence sufficiency, generates hypotheses, and produces summaries
3. **Analyzer Agent** - Converts hypotheses into targeted log search keywords
4. **Parser Agent** - Searches logs using specialized tools (grep, GC analyzer)
5. **Critic Agent** - Validates draft outputs against collected evidence

### Agent Flow

```
┌─────────────┐
│  Supervisor │ (Entry Point)
└──────┬──────┘
       │
       ├──> Reasoning ──> Supervisor (bidirectional)
       │        │
       │        ├──> LogAnalyser ──> Reasoning (bidirectional)
       │                 │
       │                 └──> LogParser ──> LogAnalyser (bidirectional)
       │
       ├──> Critic ──> Supervisor (bidirectional)
       │
       └──> END
```

## Bidirectional Agent Interactions

The system follows strict bidirectional communication patterns:

1. **Supervisor <-> Reasoning**: Supervisor initiates reasoning cycles; Reasoning returns results to Supervisor
2. **Supervisor <-> Critic**: Supervisor requests validation; Critic returns approval to Supervisor
3. **Reasoning <-> LogAnalyser**: Reasoning requests log analysis; LogAnalyser returns keywords to Reasoning
4. **LogAnalyser <-> LogParser**: LogAnalyser requests log search; LogParser returns evidence to LogAnalyser

## Project Structure

```
Spark-RCA-assistant/
├── requirements.txt           # Python dependencies
└── multiAgentSystem/
    ├── __init__.py
    ├── agent_main.ipynb      # Main notebook with RCAAgent class
    ├── config.py             # Configuration constants
    ├── deps.py               # Dependency injection
    ├── exceptions.py         # Custom exceptions
    ├── graph.py              # LangGraph workflow definition
    ├── prompts.py            # LLM prompt templates
    ├── state.py              # Shared state definitions
    ├── utils.py              # Utility functions
    ├── agents/               # Agent implementations
    │   ├── __init__.py
    │   ├── analyzer.py       # Log Analyzer Agent
    │   ├── critic.py         # Critic Agent
    │   ├── parser.py         # Log Parser Agent
    │   ├── reasoning.py      # Reasoning Agent
    │   └── supervisor.py     # Supervisor Agent
    └── tools/                # Specialized analysis tools
        ├── __init__.py
        ├── gc_analyzer.py    # GC log analysis tool
        └── grep_tool.py      # Pattern search tool
```

## Key Components

### State Management (`state.py`)

The system uses a shared `AgentState` TypedDict that flows through all agents:

- **Inputs**: `user_context`, `logs_path`
- **Working Memory**: `hypotheses`, `keywords`, `evidence`, `last_logs_chunk`
- **Draft & Quality**: `draft`, `confidence`, `critic_approved`, `critique`
- **Control Flow**: `last_status`, `next_action`, `supervisor_rationale`
- **Counters**: `iteration`, `analyze_parse_loops`

### Configuration (`config.py`)

Key configuration parameters:

- `LLM_ENDPOINT_NAME`: Databricks LLM endpoint (default: "databricks-claude-3-7-sonnet")
- `MAX_OUTER_ITERATIONS`: Maximum supervisor-level iterations (default: 3)
- `MAX_ANALYZE_PARSE_LOOPS`: Maximum analyzer-parser mini-loops (default: 3)
- `CONFIDENCE_THRESHOLD`: Minimum confidence to finish (default: 0.75)

### Tools (`tools/`)

1. **grep_tool.py**: file search with regex support
   - Multi-pattern search (AND/OR logic)
   - Hidden file handling
   - Binary file detection
   - Result limiting and formatting

2. **gc_analyzer.py**: GC log parser
   - Parses GC pause events
   - Calculates statistics (p50, p95, p99 pauses)
   - Identifies STW (Stop-The-World) events
   - Tracks memory freed and heap usage

## Control Flow

### 1. Entry Phase
```
User Request -> Supervisor -> Reasoning Agent
```

### 2. Evidence Gathering Phase
```
Reasoning (need_more=true) -> LogAnalyser -> LogParser -> LogAnalyser -> Reasoning (reassess)
```
This loop continues up to `MAX_ANALYZE_PARSE_LOOPS` times until:
- Evidence is sufficient, OR
- Maximum loops reached

### 3. Draft Creation Phase
```
Reasoning (sufficient evidence) -> [Creates Draft] -> Supervisor
```

### 4. Validation Phase
```
Supervisor -> Critic -> [Validates Draft] -> Supervisor
```

### 5. Termination Phase
```
Supervisor decides:
- END if: critic_approved AND confidence >= threshold
- END if: iteration >= MAX_OUTER_ITERATIONS
- Reasoning again if: more analysis needed
```

## Data Flow

### Input Flow
```
User Request
    |-- user_context (problem description)
    +-- logs_path (path to Spark logs)
        |
        v
    Initial State
        |
        v
    Supervisor
```

### Evidence Collection Flow
```
Hypotheses -> LogAnalyser -> Keywords -> LogParser -> Log Evidence
                                                        |
                                                        v
                                                   (appended to state.evidence)
                                                        |
                                                        v
                                                   LogAnalyser -> Reasoning (reassess)
```

### Output Flow
```
Final State
    |-- draft
    |   |-- problem (description)
    |   |-- rca (root cause analysis)
    |   +-- mitigation (suggested fixes)
    |-- confidence (0.0 - 1.0)
    |-- keywords (used for search)
    |-- evidence (collected log snippets)
    |-- critic_approved (boolean)
    +-- critique (feedback from critic)
```

## Usage

### In Databricks Notebook

```python
# 1. Install dependencies
%pip install -r requirements.txt
dbutils.library.restartPython()

# 2. Run the RCAAgent definition cell in agent_main.ipynb

# 3. Use the AGENT instance
from multiAgentSystem.agent_main import AGENT

request = {
    "user_context": "Job failed with executor lost errors during shuffle",
    "logs_path": "/Volumes/catalog/schema/spark-logs/job-123/"
}

result = AGENT.predict(request)

# Access results
print(result["output"]["problem"])
print(result["output"]["rca"])
print(result["output"]["mitigation"])
```

### Streaming Mode

```python
for event in AGENT.predict_stream(request):
    print(f"{event['type']}: {event['node']}")
    if event['type'] == 'final':
        print(event['data'])
```

## Configuration via Environment Variables

```bash
export LLM_ENDPOINT_NAME="databricks-claude-3-7-sonnet"
export MAX_OUTER_ITERATIONS="3"
export MAX_ANALYZE_PARSE_LOOPS="3"
export CONFIDENCE_THRESHOLD="0.75"
export MLFLOW_ENABLED="true"
```

## Agent Details

### Supervisor Agent
- **Role**: Orchestration and decision-making
- **Inputs**: Current state, iteration count, confidence level
- **Outputs**: `next_action` (reasoning/critic/end)
- **Logic**: Enforces iteration limits, confidence thresholds, validation requirements
- **Interactions**: Bidirectional with Reasoning and Critic

### Reasoning Agent
- **Role**: Hypothesis generation and evidence assessment
- **Inputs**: User context, current hypotheses, evidence
- **Outputs**: 
  - If insufficient: triggers LogAnalyser with refined hypotheses
  - If sufficient: produces draft (problem/RCA/mitigation)
- **Logic**: Uses LLM to assess evidence sufficiency, generates/refines hypotheses
- **Interactions**: Bidirectional with Supervisor and LogAnalyser

### LogAnalyser Agent (Analyzer)
- **Role**: Converts hypotheses to search keywords
- **Inputs**: Hypotheses, user context, existing keywords
- **Outputs**: Focused list of 3-8 keywords for log search
- **Logic**: Uses domain knowledge to identify high-signal terms (error codes, exception types, etc.)
- **Interactions**: Bidirectional with Reasoning and LogParser

### LogParser Agent (Parser)
- **Role**: Log search and extraction
- **Inputs**: Logs path, keywords
- **Outputs**: Relevant log snippets
- **Tools**: 
  - grep_path_tool for pattern matching
  - GC_analyzer_tool for GC-specific analysis
- **Logic**: Detects GC-related issues and routes to appropriate tool
- **Interactions**: Bidirectional with LogAnalyser

### Critic Agent
- **Role**: Quality assurance
- **Inputs**: Draft, evidence
- **Outputs**: `approve` (bool), `reasons` (string), `confidence_adjustment` (-0.25 to +0.25)
- **Logic**: Validates that claims in draft are supported by evidence
- **Interactions**: Bidirectional with Supervisor

## Loop Control Mechanisms

1. **Outer Loop** (Supervisor-level)
   - Controlled by `iteration` counter
   - Maximum: `MAX_OUTER_ITERATIONS` (default: 3)
   - Each reasoning cycle increments this

2. **Inner Loop** (LogAnalyser-LogParser)
   - Controlled by `analyze_parse_loops` counter
   - Maximum: `MAX_ANALYZE_PARSE_LOOPS` (default: 3)
   - Each LogAnalyser run increments this
   - Resets implicitly on next outer iteration

3. **Confidence Threshold**
   - System terminates when `confidence >= CONFIDENCE_THRESHOLD` AND `critic_approved = true`
   - Default threshold: 0.75

## Error Handling

The system includes comprehensive error handling:

- **LLMError**: LLM invocation failures
- **ConfigurationError**: Invalid configuration
- **StateError**: Invalid state transitions
- **GraphError**: Graph execution failures

All tools return graceful error messages rather than raising exceptions, ensuring the workflow continues even if individual operations fail.

## MLflow Integration

When running in Databricks with MLflow available:
- Automatic logging of LangChain operations
- Model registration via `mlflow.models.set_model()`
- Trace tracking for debugging

## Dependencies

Key dependencies (see `requirements.txt`):
- `langgraph-supervisor==0.0.29` - Multi-agent orchestration
- `mlflow[databricks]` - Experiment tracking
- `databricks-langchain` - LLM integration
- `databricks-agents` - Agent framework

## Best Practices

1. **Provide Clear Context**: The more specific the `user_context`, the better the analysis
2. **Use Valid Paths**: Ensure `logs_path` points to actual Spark logs
3. **Tune Configuration**: Adjust iterations and confidence based on complexity
4. **Review Evidence**: Check `result["output"]["evidence"]` to understand reasoning
5. **Monitor Iterations**: High iteration counts may indicate unclear context

## Limitations

- Requires access to Databricks LLM endpoints
- Works best with structured Spark logs
- Quality depends on LLM capabilities
- May require multiple iterations for complex issues

## Future Enhancements

- Add support for additional log formats
- Implement caching for repeated analyses
- Add visualization of agent decision flow
- Support for batch processing multiple log sets
- Custom tool integration framework

## License

[Add your license information here]

## Contact

[Add contact information here]
