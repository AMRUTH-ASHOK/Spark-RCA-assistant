# Spark RCA Assistant - Multi-Agent System

A multi-agent system for performing Root Cause Analysis (RCA) on Apache Spark logs using LangGraph and LLMs, optimized for Databricks environments.

## Overview

This system uses a coordinated team of AI agents to analyze Spark execution logs, identify problems, determine root causes, and suggest mitigation strategies. It features intelligent log deduplication, full MLflow tracing, and automated PDF report generation.

## Key Features

- **Multi-Agent Orchestration**: 5 specialized agents working in coordination
- **Intelligent Evidence Storage**: Automatic log deduplication with occurrence tracking
- **Full Observability**: MLflow tracing for all tools and agent interactions
- **Causal Chain Analysis**: Deep root cause drilling with evidence validation
- **PDF Report Generation**: Automated professional reports
- **Databricks Optimized**: Native integration with Databricks LLM endpoints

## Architecture

### Agent Workflow

```
┌─────────────┐
│  Supervisor │ ← Entry Point & Orchestration
└──────┬──────┘
       │
       ├──> Reasoning ← Hypothesis generation & evidence assessment
       │        │
       │        ├──> Analyzer ← Keyword generation
       │        │       │
       │        │       └──> Parser ← Log search with tools
       │        │              │
       │        └──────────────┘ (Inner feedback loop)
       │
       ├──> Critic ← Validation & quality assurance
       │
       └──> END (Generate PDF report)
```

### Agent Roles

1. **Supervisor Agent** - Orchestrates workflow, manages iterations, generates final PDF
2. **Reasoning Agent** - Assesses evidence, generates hypotheses, creates RCA drafts
3. **Analyzer Agent** - Converts hypotheses to search keywords
4. **Parser Agent** - Searches logs and populates evidence map
5. **Critic Agent** - Validates claims against evidence

## Project Structure

```
Spark-RCA-assistant/
├── README.md
├── requirements.txt
├── multiAgentSystem/
│   ├── agent_main.ipynb          # Main entry point & RCAAgent class
│   ├── config.py                 # Configuration & constants
│   ├── deps.py                   # Dependency injection
│   ├── graph.py                  # LangGraph workflow definition
│   ├── prompts.py                # LLM prompt templates
│   ├── state.py                  # Shared state with EvidenceEntry
│   ├── utils.py                  # Utility functions
│   ├── evidence_manager.py       # Evidence deduplication & formatting
│   ├── pdf_generator.py          # PDF report generation
│   ├── exceptions.py             # Custom exceptions
│   ├── agents/                   # Agent implementations
│   │   ├── supervisor.py
│   │   ├── reasoning.py
│   │   ├── analyzer.py
│   │   ├── parser.py
│   │   └── critic.py
│   ├── tools/                    # MLflow-traced tools
│   │   ├── grep_tool.py          # Pattern search with deduplication
│   │   ├── gc_analyzer.py        # GC log analysis
│   │   └── pdf_report_tool.py    # PDF generation wrapper
│   └── Reports/                  # Generated PDF reports
└── examples/                     # Example scripts
```

## Key Components

### Evidence Storage (NEW)

The system uses an optimized evidence storage structure that eliminates duplicate log entries:

```python
# Evidence Map Structure
evidence_map = {
    "OutOfMemoryError: Java heap space": {
        "count": 15,                      # Total occurrences
        "timestamps": ["25/10/08 06:23:27", ...],
        "files": ["/Volumes/logs/executor-1.log", ...],
        "sample_lines": ["Full log line 1", "Full log line 2"]
    },
    "Executor lost failure": {
        "count": 3,
        "timestamps": [...],
        "files": [...],
        "sample_lines": [...]
    }
}
```

**Benefits:**
- Automatic deduplication by error pattern
- Occurrence counting
- Timestamp and file tracking
- Memory efficient (stores samples, not all duplicates)
- Better LLM context through summaries

### MLflow Tracing

All tools are decorated with `@mlflow.trace` for full observability:

- **grep_path_tool**: Search patterns and results traced
- **gc_analyzer_tool**: GC analysis steps traced
- **generate_rca_report_tool**: PDF generation traced

View traces in Databricks MLflow UI → Traces tab

### Configuration

Edit `config.py` or use environment variables:

```python
# LLM Configuration
LLM_ENDPOINT_NAME = "databricks-claude-3-7-sonnet"

# Loop Control
MAX_OUTER_ITERATIONS = 6          # Supervisor cycles
MAX_ANALYZE_PARSE_LOOPS = 6       # Evidence gathering loops
CONFIDENCE_THRESHOLD = 0.75       # Minimum confidence to finish

# Default search keywords (always included)
DEFAULT_KEYWORDS = [
    "ERROR",
    "Exception",
    "Executor lost",
    "OutOfMemoryError",
    "GC overhead",
    "Container exited"
]
```

## Usage

### Quick Start (Databricks Notebook)

```python
# 1. Install dependencies
%pip install -r requirements.txt
dbutils.library.restartPython()

# 2. Import the agent
from multiAgentSystem.agent_main import AGENT

# 3. Run analysis
request = {
    "user_context": "Job failed with executor losses during shuffle phase",
    "logs_path": "/Volumes/catalog/schema/spark-logs/job-12345/"
}

result = AGENT.predict(request)

# 4. Access results
print("Problem:", result["output"]["problem"])
print("Root Cause:", result["output"]["rca"])
print("Mitigation:", result["output"]["mitigation"])
print(f"Confidence: {result['output']['confidence']:.2f}")
print(f"PDF Report: {result['output']['pdf_report_path']}")
```

### Access Evidence Map (NEW)

```python
# View deduplicated evidence
evidence_map = result["output"]["evidence_map"]

for pattern, entry in evidence_map.items():
    print(f"\n{pattern}:")
    print(f"  Occurrences: {entry['count']}")
    print(f"  First seen: {entry['timestamps'][0] if entry['timestamps'] else 'N/A'}")
    print(f"  Files: {', '.join(entry['files'][:3])}")
```

### Streaming Mode

```python
for event in AGENT.predict_stream(request):
    if event['type'] == 'node':
        print(f"Running: {event['node']}")
    elif event['type'] == 'final':
        result = event['data']
```

## How It Works

### Phase 1: Evidence Collection

The system iteratively searches logs and builds the evidence map:

1. **Reasoning** generates hypotheses (e.g., "OOM caused executor failure")
2. **Analyzer** converts to keywords (e.g., "OutOfMemoryError", "executor lost")
3. **Parser** searches logs and updates evidence_map
4. **Reasoning** reassesses with new evidence

This loop continues until sufficient evidence is gathered (max 6 iterations).

### Phase 2: Draft Creation

**Reasoning** agent creates the RCA draft:

```
Draft = {
  "problem": "Clear problem description",
  "rca": "Causal chain with [PROVEN] or [INFERRED] markers",
  "mitigation": "Actionable steps with Spark configs"
}
```

**Confidence Calculation:**
```
confidence = proven_statements / total_statements
```

### Phase 3: Validation

**Critic** agent validates the draft:
- Checks each [PROVEN] claim has supporting evidence
- Verifies confidence calculation
- Validates causal chain logic
- Adjusts confidence if needed

### Phase 4: Termination

**Supervisor** decides to:
- **End** if: approved AND confidence ≥ 0.75
- **End** if: max iterations reached
- **Continue** if: more analysis needed

On termination, generates PDF report automatically.

## Output Structure

```python
result = {
    "output": {
        "problem": str,              # Problem description
        "rca": str,                  # Root cause analysis
        "mitigation": str,           # Suggested fixes
        "confidence": float,         # 0.0-1.0
        "iterations": int,           # Cycles completed

        # NEW: Evidence map
        "evidence_map": {
            "error_pattern": {
                "count": int,
                "timestamps": List[str],
                "files": List[str],
                "sample_lines": List[str]
            }
        },
        "evidence_summary": str,     # Formatted for reading

        # Legacy
        "evidence": List[str],       # Raw evidence list

        # Metadata
        "keywords": List[str],       # Keywords used
        "critic_approved": bool,
        "critique": str,
        "pdf_report_path": str       # Path to PDF
    }
}
```

## Advanced Configuration

### Environment Variables

```bash
export LLM_ENDPOINT_NAME="databricks-claude-3-7-sonnet"
export MAX_OUTER_ITERATIONS="6"
export MAX_ANALYZE_PARSE_LOOPS="6"
export CONFIDENCE_THRESHOLD="0.75"

# Per-agent LLM endpoints (optional)
export REASONING_LLM_ENDPOINT="custom-endpoint"
export ANALYZER_LLM_ENDPOINT="custom-endpoint"
export PARSER_LLM_ENDPOINT="custom-endpoint"
export CRITIC_LLM_ENDPOINT="custom-endpoint"
export SUPERVISOR_LLM_ENDPOINT="custom-endpoint"
```

### Customizing Prompts

Edit `multiAgentSystem/prompts.py` to customize agent behavior:

- `REASON_DECIDE_PROMPT` - Evidence assessment logic
- `SUMMARIZE_PROMPT` - RCA draft format
- `ANALYZER_PROMPT` - Keyword generation strategy
- `CRITIC_PROMPT` - Validation criteria
- `SUPERVISOR_PROMPT` - Orchestration logic

## Tools

### grep_path_tool

Pattern search with advanced features:
- Regex support
- AND/OR logic
- Automatic deduplication
- MLflow traced

### gc_analyzer_tool

GC log parser:
- Parses pause events
- Calculates p50/p95/p99 statistics
- Identifies Stop-The-World events
- Memory analysis
- MLflow traced

### generate_rca_report_tool

PDF generator:
- Professional formatting
- Includes evidence and metadata
- Timestamped filenames
- MLflow traced

## Dependencies

```
langgraph-supervisor==0.0.29    # Multi-agent orchestration
mlflow[databricks]              # Experiment tracking & tracing
databricks-langchain            # LLM integration
databricks-agents               # Agent framework
reportlab                       # PDF generation
```

## Best Practices

1. **Provide Specific Context**: Include job IDs, query IDs, failure timestamps
2. **Use Correct Log Paths**: Point to `/Volumes/` directory with Spark logs
3. **Review Evidence Map**: Check occurrence counts to understand failure patterns
4. **Monitor Confidence**: Low confidence may indicate insufficient logs or unclear issue
5. **Check PDF Reports**: Stored in `multiAgentSystem/Reports/` directory

## Troubleshooting

### Low Confidence (<0.5)
- Provide more specific user_context
- Ensure logs_path contains relevant logs
- Check if logs have actual error messages

### No Evidence Found
- Verify logs_path is correct
- Check log format (must be text files)
- Ensure logs contain error keywords

### High Iterations
- May indicate complex multi-stage failure
- Review hypotheses in output to understand investigation path
- Consider providing more initial context

## Limitations

- Requires Databricks environment with LLM endpoints
- Works with text-based Spark logs (not binary formats)
- Limited to logs in `/Volumes/` directory
- Quality depends on log detail and LLM capabilities

## Recent Updates

### v2.0 (Latest)
- ✅ Optimized evidence storage with deduplication
- ✅ MLflow tracing for all tools
- ✅ Evidence occurrence tracking
- ✅ Timestamp and file path tracking
- ✅ Memory-efficient sample storage
- ✅ Backward compatibility maintained

### v1.0
- Initial multi-agent implementation
- Basic evidence collection
- PDF report generation

## License

[Add your license information]

## Support

For issues or questions:
- Check Databricks documentation
- Review MLflow traces for debugging
- Examine generated PDF reports

---

**Built with LangGraph, MLflow, and Databricks Agent Framework**
