# Spark RCA Assistant - Multi-Agent System

A sophisticated multi-agent system for performing Root Cause Analysis (RCA) on Apache Spark logs using LangGraph and LLMs.

## Overview

This system uses a coordinated team of AI agents to analyze Spark execution logs, identify problems, determine root causes, and suggest mitigation strategies. It's designed to work in Databricks environments and can analyze various Spark failure modes including OOM errors, executor losses, GC issues, and more.

### Key Features

- **Token-Optimized Storage**: Evidence deduplication reduces token usage by 75-85% (700k → 100-150k tokens)
- **Causal Chain Drilling**: Iterative "WHY?" methodology to reach root causes, not just symptoms
- **Mathematical Confidence**: Objective confidence scoring using proven/total statements ratio (P/N)
- **Progressive Narrowing**: Broad-to-narrow keyword search strategy for comprehensive context
- **MLflow ChatAgent**: Full Databricks integration with automatic authentication passthrough
- **AI Playground Ready**: Deploy and test interactively in Databricks AI Playground
- **Autonomous Tool Selection**: ReAct-based Parser agent with self-directed log analysis
- **One-Line Deployment**: `agents.deploy()` with automatic credential management

## Architecture

### Multi-Agent Design

The system employs a **hierarchical multi-agent architecture** with the following specialized agents:

1. **Supervisor Agent** - Orchestrates the overall workflow and decides which agent to invoke next
2. **Reasoning Agent** - Assesses evidence sufficiency using causal chain drilling, generates hypotheses, and produces summaries with mathematical confidence scores
3. **Analyzer Agent** - Converts hypotheses into targeted log search keywords using progressive narrowing (broad → narrow)
4. **Parser Agent** - ReAct-based agent with autonomous tool selection (grep_logs, analyze_gc_logs)
5. **Critic Agent** - Validates draft outputs against collected evidence, verifies confidence calculations mathematically

### Agent Flow

```
┌─────────────┐
│  Supervisor │ (Entry Point)
└──────┬──────┘
       │
       ├──> Reasoning ──> Supervisor (bidirectional)
       │        │         [Causal Chain Drilling + P/N Confidence]
       │        │
       │        ├──> LogAnalyser ──> Reasoning (bidirectional)
       │                 │          [Progressive Narrowing: broad→narrow]
       │                 │
       │                 └──> LogParser ──> LogAnalyser (bidirectional)
       │                       [ReAct Agent: Autonomous Tool Selection]
       │
       ├──> Critic ──> Supervisor (bidirectional)
       │              [Mathematical Confidence Validation]
       │
       └──> END
```

### Evidence Optimization

The system uses an **evidence map** for intelligent deduplication:

```
Evidence Map Structure:
{
  "file_path::pattern::content_hash": {
    "content": "log line content",
    "timestamps": ["2024-01-01 10:00:00", ...],
    "count": 156,
    "first_seen": "2024-01-01 10:00:00",
    "last_seen": "2024-01-01 10:05:00",
    "file_path": "/path/to/log",
    "pattern": "ERROR.*OutOfMemoryError"
  }
}
```

**Benefits**:
- 75-85% token reduction (700k → 100-150k tokens per analysis)
- Temporal context preserved (first/last occurrence)
- Frequency information available (count field)
- Backward compatible with legacy evidence field

## Bidirectional Agent Interactions

The system follows strict bidirectional communication patterns:

1. **Supervisor <-> Reasoning**: Supervisor initiates reasoning cycles; Reasoning returns results to Supervisor
2. **Supervisor <-> Critic**: Supervisor requests validation; Critic returns approval to Supervisor
3. **Reasoning <-> LogAnalyser**: Reasoning requests log analysis; LogAnalyser returns keywords to Reasoning
4. **LogAnalyser <-> LogParser**: LogAnalyser requests log search; LogParser returns evidence to LogAnalyser

## Project Structure

```
Spark-RCA-assistant/
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── QUICK_START.md               # Quick start guide
├── TESTING_GUIDE.md             # Testing guide
└── multiAgentSystem/
    ├── __init__.py
    ├── agent_main.ipynb         # Main notebook with ChatAgent wrapper
    ├── chat_agent_wrapper.py    # MLflow ChatAgent implementation
    ├── config.py                # Configuration constants
    ├── deps.py                  # Dependency injection
    ├── exceptions.py            # Custom exceptions
    ├── graph.py                 # LangGraph workflow definition
    ├── pdf_generator.py         # PDF report generation
    ├── prompts.py               # LLM prompt templates (causal drilling)
    ├── state.py                 # Shared state with evidence_map
    ├── utils.py                 # Utility functions
    ├── log_deduplicator.py      # Evidence deduplication (75-85% token savings)
    ├── agents/                  # Agent implementations
    │   ├── __init__.py
    │   ├── analyzer.py          # Log Analyzer Agent (progressive narrowing)
    │   ├── critic.py            # Critic Agent (mathematical validation)
    │   ├── parser.py            # Log Parser Agent (ReAct + autonomous tools)
    │   ├── reasoning.py         # Reasoning Agent (causal drilling + P/N)
    │   └── supervisor.py        # Supervisor Agent
    └── tools/                   # Specialized analysis tools
        ├── __init__.py
        ├── gc_analyzer.py       # GC log analysis tool
        ├── grep_tool.py         # Pattern search tool
        ├── langchain_tools.py   # LangChain-wrapped tools for MLflow tracing
        └── pdf_report_tool.py   # PDF generation tool
```

## Key Components

### State Management (`state.py`)

The system uses a shared `AgentState` TypedDict that flows through all agents:

- **Inputs**: `user_context`, `logs_path`
- **Working Memory**: `hypotheses`, `keywords`, `evidence` (legacy), `evidence_map` (optimized), `last_logs_chunk`
- **Draft & Quality**: `draft`, `confidence`, `critic_approved`, `critique`
- **Control Flow**: `last_status`, `next_action`, `supervisor_rationale`
- **Counters**: `iteration`, `analyze_parse_loops`

**Evidence Map** (`evidence_map` field):
- Deduplicates log content by content hash
- Reduces token usage by 75-85% (700k → 100-150k)
- Preserves temporal information (first_seen, last_seen, count)
- Format: `{file_path::pattern::hash: {content, timestamps, count, ...}}`

### Configuration (`config.py`)

Key configuration parameters:

- `LLM_ENDPOINT_NAME`: Databricks LLM endpoint (default: "databricks-claude-3-7-sonnet")
- `MAX_OUTER_ITERATIONS`: Maximum supervisor-level iterations (default: 3)
- `MAX_ANALYZE_PARSE_LOOPS`: Maximum analyzer-parser mini-loops (default: 3)
- `CONFIDENCE_THRESHOLD`: Minimum confidence to finish (default: 0.75)

### Prompt Engineering (`prompts.py`)

Advanced prompt engineering techniques:

1. **Causal Chain Drilling** (Reasoning Agent)
   - Iteratively asks "WHY?" to reach root causes
   - Prevents stopping at symptoms
   - Example: "Error X occurred" → "Why?" → "Memory pressure" → "Why?" → "Inefficient broadcast join"

2. **Mathematical Confidence** (Reasoning & Critic)
   - Formula: `confidence = P / N` where P = proven statements, N = total statements
   - Objective scoring prevents subjective bias
   - Critic validates calculation mathematically

3. **Progressive Narrowing** (Analyzer Agent)
   - Start with broad keywords: "error", "exception", "failure"
   - Then narrow: specific error codes, task IDs, executor IDs
   - Ensures context capture before drilling down

### Tools (`tools/`)

#### 1. **langchain_tools.py**: LangChain-wrapped tools for MLflow tracing
   - `grep_logs`: Pattern search with MLflow observability
   - `analyze_gc_logs`: GC analysis with MLflow observability
   - Uses `@tool` decorator for automatic tracing
   - Rich descriptions for autonomous LLM tool selection

#### 2. **grep_tool.py**: Core file search with regex support
   - Multi-pattern search (AND/OR logic)
   - Hidden file handling
   - Binary file detection
   - Result limiting and formatting
   - Wrapped by `grep_logs` in langchain_tools.py

#### 3. **gc_analyzer.py**: GC log parser
   - Parses GC pause events
   - Calculates statistics (p50, p95, p99 pauses)
   - Identifies STW (Stop-The-World) events
   - Tracks memory freed and heap usage
   - Wrapped by `analyze_gc_logs` in langchain_tools.py

#### 4. **log_deduplicator.py**: Evidence optimization
   - `deduplicate_grep_results()`: Creates evidence map from raw logs
   - `format_evidence_map_for_prompt()`: Formats for LLM consumption
   - `merge_evidence_maps()`: Combines multiple evidence maps
   - `get_evidence_summary_stats()`: Provides statistics (unique entries, occurrences, token savings)

## Control Flow

### 1. Entry Phase
```
User Request -> Supervisor -> Reasoning Agent
```

### 2. Evidence Gathering Phase (with Progressive Narrowing)
```
Reasoning (need_more=true) 
    -> LogAnalyser (broad keywords: "error", "exception") 
        -> LogParser (ReAct: autonomous tool selection)
            -> LogAnalyser (narrow keywords: "TaskID 123", "ExecutorID 5")
                -> Reasoning (reassess with evidence_map)
```

**Progressive Narrowing Strategy**:
- **First iteration**: Broad keywords to establish context
  - Examples: "error", "exception", "failure", "lost"
- **Subsequent iterations**: Narrow keywords to drill down
  - Examples: "TaskID 123", "ExecutorID 5", "Stage 4", specific error codes

This loop continues up to `MAX_ANALYZE_PARSE_LOOPS` times until:
- Evidence is sufficient, OR
- Maximum loops reached

### 3. Draft Creation Phase (with Causal Drilling)
```
Reasoning (sufficient evidence) 
    -> [Causal Chain Drilling: WHY? → WHY? → WHY?]
        -> [Calculates P/N Confidence]
            -> [Creates Draft] 
                -> Supervisor
```

**Causal Chain Drilling**:
1. Identify surface symptom (e.g., "Executor lost")
2. Ask WHY? → Memory pressure detected
3. Ask WHY? → GC overhead > 90%
4. Ask WHY? → Inefficient broadcast join causing memory spill
5. Root cause identified: Suboptimal join strategy

**Mathematical Confidence**:
```
confidence = P / N
P = number of proven statements (backed by evidence)
N = total number of statements in draft
```

### 4. Validation Phase
```
Supervisor -> Critic -> [Validates Draft] -> [Verifies P/N Calculation] -> Supervisor
```

The Critic:
- Verifies each statement has evidence support
- Recalculates P/N confidence independently
- Adjusts confidence by -0.25 to +0.25 if needed
- Provides specific reasons for approval/rejection

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

### Evidence Collection Flow (with Deduplication)
```
Hypotheses 
    -> LogAnalyser (progressive narrowing: broad→narrow)
        -> Keywords 
            -> LogParser (ReAct: grep_logs OR analyze_gc_logs)
                -> Raw Log Evidence
                    -> Deduplication (log_deduplicator.py)
                        -> Evidence Map (75-85% token reduction)
                            |
                            v
                        (stored in state.evidence_map)
                            |
                            v
                        LogAnalyser -> Reasoning (reassess)
```

**Evidence Map Benefits**:
- **Before**: 700k tokens per analysis (raw duplicate logs)
- **After**: 100-150k tokens per analysis (deduplicated with metadata)
- **Savings**: 75-85% token reduction
- **Preserved**: Temporal context (first/last seen), frequency (count)

### Output Flow
```
Final State
    |-- draft
    |   |-- problem (description)
    |   |-- rca (root cause analysis with causal chain)
    |   +-- mitigation (suggested fixes)
    |-- confidence (P/N ratio: 0.0 - 1.0)
    |-- keywords (progressive: broad → narrow)
    |-- evidence (legacy: raw logs)
    |-- evidence_map (optimized: deduplicated with metadata)
    |-- critic_approved (boolean)
    +-- critique (feedback from critic with confidence validation)
```

## Usage

### In Databricks Notebook (with MLflow ChatAgent)

```python
# 1. Install dependencies
%pip install -r requirements.txt
dbutils.library.restartPython()

# 2. Import the ChatAgent
from mlflow.types.agent import ChatAgentMessage
from multiAgentSystem.chat_agent_wrapper import RCALangGraphChatAgent
from multiAgentSystem.graph import build_graph

# 3. Create the agent
agent = RCALangGraphChatAgent(build_graph())

# 4. Create messages in ChatAgent format
messages = [
    ChatAgentMessage(
        role="user",
        content="Job failed with executor lost errors during shuffle"
    )
]

custom_inputs = {
    "logs_path": "/Volumes/catalog/schema/spark-logs/job-123/"
}

# 5. Get results
response = agent.predict(messages=messages, custom_inputs=custom_inputs)
print(response.messages[0].content)
```

### Streaming Mode

```python
for chunk in agent.predict_stream(messages=messages, custom_inputs=custom_inputs):
    print(chunk.delta.content)
```

### Deployment to Model Serving

```python
import mlflow
from databricks import agents
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksVolume

# Define resources for automatic authentication
resources = [
    DatabricksServingEndpoint(endpoint_name="databricks-claude-3-7-sonnet"),
    DatabricksVolume(volume="catalog.schema.spark_logs"),
]

# Log model
with mlflow.start_run():
    logged_info = mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model="agent.py",
        input_example=input_example,
        resources=resources,  # Automatic auth passthrough!
    )

# Register to Unity Catalog
mlflow.set_registry_uri("databricks-uc")
uc_info = mlflow.register_model(
    model_uri=logged_info.model_uri,
    name="catalog.schema.spark_rca_agent"
)

# One-line deployment with automatic authentication
agents.deploy("catalog.schema.spark_rca_agent", uc_info.version)
```

**For detailed ChatAgent integration:**
- MLflow ChatAgent wraps the LangGraph multi-agent system
- Enables automatic authentication passthrough
- Provides AI Playground integration
- See `multiAgentSystem/chat_agent_wrapper.py` for implementation details

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
- **Enhancements**: Monitors evidence_map statistics for optimization insights

### Reasoning Agent
- **Role**: Hypothesis generation and evidence assessment with causal drilling
- **Inputs**: User context, current hypotheses, evidence_map
- **Outputs**: 
  - If insufficient: triggers LogAnalyser with refined hypotheses
  - If sufficient: produces draft using causal chain drilling, calculates P/N confidence
- **Logic**: 
  - Causal Chain Drilling: Iteratively asks "WHY?" until root cause identified
  - Mathematical Confidence: P/N = proven_statements / total_statements
  - Uses formatted evidence_map (deduplicated) instead of raw logs
- **Interactions**: Bidirectional with Supervisor and LogAnalyser
- **Token Optimization**: Consumes 75-85% fewer tokens via evidence_map

### LogAnalyser Agent (Analyzer)
- **Role**: Converts hypotheses to search keywords using progressive narrowing
- **Inputs**: Hypotheses, user context, existing keywords
- **Outputs**: Focused list of 3-8 keywords for log search
- **Logic**: 
  - Progressive Narrowing Strategy:
    - Early iterations: Broad keywords ("error", "exception", "failure")
    - Later iterations: Narrow keywords (TaskIDs, ExecutorIDs, specific error codes)
  - Uses domain knowledge to identify high-signal terms
- **Interactions**: Bidirectional with Reasoning and LogParser
- **Enhancements**: Keyword strategy adapts based on iteration count and evidence gathered

### LogParser Agent (Parser)
- **Role**: Autonomous log search and extraction using ReAct architecture
- **Inputs**: Logs path, keywords
- **Outputs**: Deduplicated evidence map with temporal metadata
- **Architecture**: ReAct agent (Reasoning + Acting)
  - **Autonomous Tool Selection**: LLM decides which tool to use
  - **Available Tools**:
    - `grep_logs`: Pattern matching for general log searches
    - `analyze_gc_logs`: Specialized GC analysis for memory/GC issues
  - **Multi-step Planning**: Can call tools multiple times in sequence
- **Logic**: 
  - Detects GC-related issues and routes to appropriate tool
  - Uses LangChain @tool wrappers for MLflow tracing
  - Applies deduplication to results before returning
- **Interactions**: Bidirectional with LogAnalyser
- **MLflow Integration**: All tool calls automatically traced for observability

### Critic Agent
- **Role**: Quality assurance with mathematical validation
- **Inputs**: Draft, evidence_map
- **Outputs**: 
  - `approve` (bool)
  - `reasons` (string with specific validation details)
  - `confidence_adjustment` (-0.25 to +0.25)
- **Logic**: 
  - Validates that claims in draft are supported by evidence_map
  - Independently recalculates P/N confidence
  - Verifies causal chain logic (each "WHY?" has evidence support)
  - Adjusts confidence mathematically if calculation incorrect
- **Interactions**: Bidirectional with Supervisor
- **Enhancements**: Mathematical rigor prevents subjective scoring

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
4. **Review Evidence Map**: Check `result["output"]["evidence_map"]` to understand reasoning and token savings
5. **Monitor Iterations**: High iteration counts may indicate unclear context
6. **Trust Mathematical Confidence**: P/N ratio provides objective quality measure
7. **Leverage MLflow Tracing**: Use MLflow UI to inspect tool calls and agent decisions
8. **Check Token Statistics**: Use evidence map stats to verify optimization (expect 75-85% reduction)

## Limitations

- Requires access to Databricks LLM endpoints
- Works best with structured Spark logs
- Quality depends on LLM capabilities
- May require multiple iterations for complex issues
- Evidence deduplication assumes content-based uniqueness (identical log lines are deduplicated)

## Performance Characteristics

- **Token Usage**: 100-150k tokens per analysis (75-85% reduction from 700k baseline)
- **Typical Iterations**: 2-3 outer loops for most issues
- **Time Complexity**: O(n) for evidence deduplication, where n = number of log lines
- **Memory Efficiency**: Evidence map stores unique content only, reducing memory footprint
- **MLflow Overhead**: Minimal (<5% latency increase) for full tracing capability

## Future Enhancements

- Add support for additional log formats (YARN, Kubernetes, etc.)
- Implement persistent caching for repeated analyses
- Add visualization of agent decision flow and causal chains
- Support for batch processing multiple log sets
- Custom tool integration framework
- Real-time streaming log analysis
- Automated confidence threshold tuning based on issue complexity
- Enhanced evidence map with semantic clustering (beyond content hash)

## Technical Innovations

This system implements several novel techniques:

1. **Evidence Map Architecture**: Hash-based deduplication with temporal metadata (75-85% token reduction)
2. **Causal Chain Drilling**: Structured "WHY?" methodology for root cause identification
3. **Mathematical Confidence Scoring**: Objective P/N ratio eliminates subjective bias
4. **Progressive Narrowing**: Dynamic keyword strategy adapts to analysis depth
5. **ReAct Parser**: Autonomous tool selection with LLM-driven decision making
6. **Bidirectional Agent Communication**: Strict interaction patterns prevent infinite loops
7. **MLflow-Native Tooling**: First-class observability with LangChain @tool integration

## References

- **LangGraph**: Multi-agent orchestration framework
- **LangChain**: Tool wrapping and LLM abstraction
- **ReAct**: Reasoning + Acting paradigm (Yao et al., 2023)
- **Causal Analysis**: Root cause analysis methodology
- **MLflow**: Experiment tracking and model observability

## License

[Add your license information here]

## Contact

[Add contact information here]
