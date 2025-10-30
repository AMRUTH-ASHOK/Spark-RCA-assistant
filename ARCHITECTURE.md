# Spark RCA Assistant - Control Flow and Data Flow Diagrams

## High-Level System Overview

```
+-------------------------------------------------------------------+
|                    Spark RCA Multi-Agent System                   |
|                                                                   |
|  INPUT: User Context + Logs Path                                 |
|     |                                                             |
|     v                                                             |
|  +------------------------------------------------------+         |
|  |              SUPERVISOR AGENT                        |         |
|  |  (Orchestration & Decision Making)                   |         |
|  +------------------------+-----------------------------+         |
|                           |                                       |
|            +--------------+--------------+                        |
|            |                             |                        |
|            v                             v                        |
|       +---------+                    +-------+                    |
|       |REASONING|<------------------>|CRITIC |                    |
|       +---------+                    +-------+                    |
|            |                             |                        |
|            v                             v                        |
|       +------------+               Back to Supervisor             |
|       |LogAnalyser |                                              |
|       +------------+                                              |
|            |                                                      |
|            v                                                      |
|       +---------+                                                 |
|       |LogParser|                                                 |
|       +---------+                                                 |
|            |                                                      |
|            v                                                      |
|      Back to LogAnalyser                                          |
|                                                                   |
|  OUTPUT: Problem + RCA + Mitigation + Evidence                   |
+-------------------------------------------------------------------+
```

## Agent Interaction Pattern

The system follows strict bidirectional communication:

```
Supervisor <---------> Reasoning
Supervisor <---------> Critic
Reasoning  <---------> LogAnalyser
LogAnalyser <--------> LogParser
```

## Detailed Control Flow

### Phase 1: Initialization and First Reasoning

```
+-------------+
| User Request|
| - context   |
| - logs_path |
+------+------+
       |
       v
+----------------+
| Initialize     |
| AgentState     |
| - iteration: 0 |
| - hypotheses:[]|
| - evidence: [] |
+------+---------+
       |
       v
+----------------+
| SUPERVISOR     |
| Decision:      |
| "reasoning"    |
+------+---------+
       |
       v
+----------------------------+
| REASONING AGENT            |
| 1. Assess evidence         |
| 2. need_more = true (first)|
| 3. Generate hypotheses     |
| 4. next_action="analyzer"  |
+------+---------------------+
       |
       v
```

### Phase 2: Evidence Collection

```
+-----------------------------------------------------------+
|               EVIDENCE GATHERING LOOP                     |
|          (Max: MAX_ANALYZE_PARSE_LOOPS = 3)              |
+-----------------------------------------------------------+
       |
       v
+----------------------------+
| LOGANALYSER AGENT          |
| - Input: hypotheses        |
| - Process: Generate        |
|   keywords (3-8 terms)     |
| - Output: keywords list    |
| - Increment:               |
|   analyze_parse_loops++    |
+------+---------------------+
       |
       v
+----------------------------+
| LOGPARSER AGENT            |
| - Input: keywords +        |
|   logs_path                |
| - Tools:                   |
|   * grep_path_tool         |
|   * GC_analyzer_tool       |
| - Output: log snippets     |
| - Append to: evidence[]    |
+------+---------------------+
       |
       v
+----------------------------+
| Back to LOGANALYSER        |
| then to REASONING          |
+------+---------------------+
       |
       v
+----------------------------+
| REASONING AGENT (re-assess)|
| - Input: new evidence      |
| - Check: sufficient?       |
|                            |
| IF sufficient OR           |
|    loops >= MAX:           |
|    -> Create Draft         |
|    -> Return to Supervisor |
|                            |
| IF need_more AND           |
|    loops < MAX:            |
|    ->next_action="analyzer"|
|    -> LOOP BACK            |
+------+---------------------+
       |
       v
```

### Phase 3: Draft Creation and Validation

```
+----------------------------+
| REASONING AGENT            |
| (Evidence Sufficient)      |
|                            |
| Create Draft:              |
| - problem: string          |
| - rca: string              |
| - mitigation: string       |
| - confidence: 0.0-1.0      |
|                            |
| Set:                       |
| - last_status="summarized" |
| - Return to Supervisor     |
+------+---------------------+
       |
       v
+----------------------------+
| SUPERVISOR                 |
| Check:                     |
| - last_status="summarized" |
| - critic_approved=false    |
|                            |
| Decision: "critic"         |
+------+---------------------+
       |
       v
+----------------------------+
| CRITIC AGENT               |
|                            |
| Validate:                  |
| - Draft vs Evidence        |
|                            |
| Output:                    |
| - approve: bool            |
| - reasons: string          |
| - confidence_adjustment:   |
|   (-0.25 to +0.25)         |
|                            |
| Update:                    |
| - critic_approved          |
| - confidence               |
| - Return to Supervisor     |
+------+---------------------+
       |
       v
```

### Phase 4: Termination Decision

```
+----------------------------+
| SUPERVISOR                 |
|                            |
| Check Termination:         |
|                            |
| IF iteration >=            |
|    MAX_OUTER_ITERATIONS:   |
|    -> END                  |
|                            |
| IF critic_approved AND     |
|    confidence >= THRESHOLD:|
|    -> END                  |
|                            |
| ELSE:                      |
|    -> "reasoning" (retry)  |
|    -> iteration++          |
+------+---------------------+
       |
       v
+----------------------------+
| END / RETURN RESULT        |
+----------------------------+
```

## Data Flow Diagram

### State Evolution Through the System

```
INITIAL STATE
|-- user_context: "Job failed with executor lost..."
|-- logs_path: "/Volumes/..."
|-- iteration: 0
|-- hypotheses: []
|-- keywords: []
|-- evidence: []
|-- draft: {}
|-- confidence: 0.0
|-- analyze_parse_loops: 0
+-- ...
    |
    v
AFTER REASONING (1st pass)
|-- user_context: (unchanged)
|-- logs_path: (unchanged)
|-- iteration: 0
|-- hypotheses: ["OOM in executor", "GC overhead", "Shuffle failure"]
|-- keywords: []
|-- evidence: []
|-- draft: {}
|-- confidence: 0.0
|-- analyze_parse_loops: 0
+-- next_action: "analyzer"
    |
    v
AFTER LOGANALYSER
|-- hypotheses: (unchanged)
|-- keywords: ["OutOfMemoryError", "GC overhead", "executor lost", "Container killed"]
|-- last_generated_keywords: ["OutOfMemoryError", "GC overhead", ...]
|-- analyze_parse_loops: 1
+-- (flows to LogParser)
    |
    v
AFTER LOGPARSER
|-- keywords: (unchanged)
|-- evidence: ["[LOG SEARCH] Found 15 matches...\n executor 7 exited with reason: Container killed..."]
|-- last_logs_chunk: "[LOG SEARCH]..."
|-- last_generated_keywords: []
+-- (flows back to LogAnalyser then Reasoning)
    |
    v
AFTER REASONING (2nd pass - sufficient)
|-- hypotheses: (refined)
|-- evidence: (accumulated)
|-- draft: {
|   "problem": "Executors are being killed due to memory pressure...",
|   "rca": "Analysis of GC logs shows full GC pauses exceeding 3s...",
|   "mitigation": "1. Increase executor memory\n2. Tune GC settings..."
| }
|-- confidence: 0.72
|-- last_status: "summarized"
+-- next_action: ""
    |
    v
AFTER SUPERVISOR
|-- next_action: "critic"
+-- (routes to Critic)
    |
    v
AFTER CRITIC
|-- critic_approved: true
|-- critique: "Draft is well-supported by log evidence..."
|-- confidence: 0.80  (adjusted from 0.72 + 0.08)
+-- (returns to Supervisor)
    |
    v
AFTER SUPERVISOR (final)
|-- next_action: "end"
+-- (terminates)
    |
    v
FINAL OUTPUT
{
  "output": {
    "problem": "Executors are being killed due to memory pressure...",
    "rca": "Analysis of GC logs shows full GC pauses exceeding 3s...",
    "mitigation": "1. Increase executor memory\n2. Tune GC settings...",
    "confidence": 0.80,
    "iterations": 1,
    "keywords": ["OutOfMemoryError", "GC overhead", "executor lost", ...],
    "evidence": ["[LOG SEARCH] Found 15 matches...", ...],
    "critic_approved": true,
    "critique": "Draft is well-supported by log evidence..."
  }
}
```

## Agent Communication Patterns

### 1. Supervisor to Agent (Command Pattern)

```
State {
  next_action: "reasoning"
  iteration: 1
  ...
}
    |
    v
Agent receives state
    |
    v
Agent processes
    |
    v
Agent returns partial state update back to Supervisor
```

### 2. Reasoning to LogAnalyser to LogParser (Pipeline Pattern)

```
Reasoning Agent
|-- Determines: need_more_evidence = true
|-- Sets: next_action = "analyzer"
+-- Returns partial state
    |
    v
Graph routes to LogAnalyser (via reasoning_router)
    |
    v
LogAnalyser Agent
|-- Receives: hypotheses
|-- Generates: keywords
|-- Returns: {keywords, last_generated_keywords, analyze_parse_loops++}
+-- Graph routes to LogParser
    |
    v
LogParser Agent
|-- Receives: keywords, logs_path
|-- Searches: logs using tools
|-- Returns: {evidence.append(), last_logs_chunk}
+-- Graph routes back to LogAnalyser
    |
    v
LogAnalyser receives evidence confirmation
+-- Graph routes back to Reasoning (via bidirectional path)
    |
    v
Reasoning Agent (reassess)
|-- Receives: updated evidence
|-- Assesses: sufficient?
+-- Decides: create_draft OR continue_loop OR return to Supervisor
```

### 3. Critic to Supervisor (Validation Pattern)

```
Critic Agent
|-- Receives: draft, evidence
|-- Validates: claims vs evidence
|-- Returns: {critic_approved, critique, confidence_adjustment}
+-- Graph routes to Supervisor (via bidirectional edge)
    |
    v
Supervisor Agent
|-- Receives: critic_approved
|-- Checks: confidence >= threshold
+-- Decides: END or continue
```

## Loop Control Mechanisms

### Outer Loop (Supervisor-controlled)

```
Iteration 0: Supervisor -> Reasoning -> ... -> Supervisor
              (iteration: 0 -> 1)
              
Iteration 1: Supervisor -> Reasoning -> ... -> Supervisor
              (iteration: 1 -> 2)
              
Iteration 2: Supervisor -> Reasoning -> ... -> Supervisor
              (iteration: 2 -> 3)
              
Iteration 3: MAX_OUTER_ITERATIONS reached -> END
```

### Inner Loop (LogAnalyser-LogParser)

```
Loop 0: Reasoning -> LogAnalyser -> LogParser -> LogAnalyser -> Reasoning
         (analyze_parse_loops: 0 -> 1)
         
Loop 1: Reasoning -> LogAnalyser -> LogParser -> LogAnalyser -> Reasoning
         (analyze_parse_loops: 1 -> 2)
         
Loop 2: Reasoning -> LogAnalyser -> LogParser -> LogAnalyser -> Reasoning
         (analyze_parse_loops: 2 -> 3)
         
Loop 3: MAX_ANALYZE_PARSE_LOOPS reached
         -> Reasoning creates draft regardless
```

## Tool Integration Flow

### grep_path_tool

```
LogParser Agent
    |
    v
Calls grep_path_tool(
    target=logs_path,
    pattern="OutOfMemoryError|executor lost",
    ignore_case=True,
    max_results=100
)
    |
    v
Tool searches files
    |
    v
Returns JSON: [
    {
        "path": "/path/to/log.txt",
        "line_no": 1234,
        "line_text": "ERROR: OutOfMemoryError in executor 7",
        "spans": [(7, 24)]
    },
    ...
]
    |
    v
LogParser formats results
    |
    v
Returns to LogAnalyser then to state.evidence
```

### GC_analyzer_tool

```
LogParser Agent (detects GC keywords)
    |
    v
Calls GC_analyzer_tool(
    log_text=grep_results,
    format="markdown",
    only_stw=True,
    top_n=5
)
    |
    v
Tool parses GC events
    |
    v
Returns: {
    "summary": "Total STW pause: 45.3s, p99: 3.2s",
    "top_pauses_table": "| GC | Duration | ...",
    "stats": {...}
}
    |
    v
LogParser formats as evidence
    |
    v
Returns to LogAnalyser then to state.evidence
```

## Error Handling Flow

```
Agent Operation
    |
    v
Try: Execute logic
    |
    v
Catch: Exception
    |
    v
Log error details
    |
    v
Return partial state with error info
    |
    v
Continue to next agent
    (System never crashes, always progresses)
```

## Key Insights

### Control Flow Characteristics
1. **Hierarchical**: Supervisor has ultimate control
2. **Iterative**: Multiple passes through reasoning
3. **Nested**: Inner LogAnalyser-LogParser loop within outer reasoning loop
4. **Bidirectional**: All agent pairs have two-way communication
5. **Bounded**: Hard limits on iterations prevent infinite loops
6. **Conditional**: LLM-driven decisions at each step

### Data Flow Characteristics
1. **Accumulative**: Evidence and hypotheses accumulate over time
2. **Immutable Core**: User context and logs path never change
3. **Mutable State**: Hypotheses, keywords, evidence evolve
4. **Partial Updates**: Agents return only changed fields
5. **Merge Strategy**: LangGraph merges partial states automatically

### Quality Assurance
1. **Critic Validation**: Independent verification of claims
2. **Confidence Tracking**: Numeric measure of certainty
3. **Evidence Requirements**: All claims must have supporting logs
4. **Iteration Limits**: Prevents excessive computation
5. **Graceful Degradation**: Returns best available answer

## Key Insights

### Control Flow Characteristics
1. **Hierarchical**: Supervisor has ultimate control
2. **Iterative**: Multiple passes through reasoning
3. **Nested**: Inner analyzer-parser loop within outer reasoning loop
4. **Bounded**: Hard limits on iterations prevent infinite loops
5. **Conditional**: LLM-driven decisions at each step

### Data Flow Characteristics
1. **Accumulative**: Evidence and hypotheses accumulate over time
2. **Immutable Core**: User context and logs path never change
3. **Mutable State**: Hypotheses, keywords, evidence evolve
4. **Partial Updates**: Agents return only changed fields
5. **Merge Strategy**: LangGraph merges partial states automatically

### Quality Assurance
1. **Critic Validation**: Independent verification of claims
2. **Confidence Tracking**: Numeric measure of certainty
3. **Evidence Requirements**: All claims must have supporting logs
4. **Iteration Limits**: Prevents excessive computation
5. **Graceful Degradation**: Returns best available answer

## Performance Considerations

### Typical Execution Path

```
Simple Issue (1-2 iterations):
  Supervisor -> Reasoning -> LogAnalyser -> LogParser -> LogAnalyser -> Reasoning (draft)
  -> Supervisor -> Critic -> Supervisor -> END
  Time: approximately 30-60 seconds

Complex Issue (3+ iterations):
  Multiple outer loops with nested LogAnalyser-LogParser loops
  Time: approximately 2-5 minutes

Maximum Path:
  MAX_OUTER_ITERATIONS * (1 + MAX_ANALYZE_PARSE_LOOPS)
  = 3 * (1 + 3) = 12 agent executions
  Time: approximately 5-10 minutes
```

### Optimization Strategies
1. **Keyword Reuse**: LogAnalyser merges with existing keywords
2. **Evidence Caching**: Already-collected evidence persists
3. **Early Termination**: Stops when confidence threshold met
4. **Focused Search**: LogAnalyser generates targeted keywords
5. **Parallel Tool Execution**: grep and GC analysis can run together

---

**Legend:**
- `->` : Control flow / routing
- `|` : Sequential progression / hierarchy
- `v` : Downward flow
- `[]` : List/array
- `{}` : Dictionary/object
- `()` : Parameters/values
