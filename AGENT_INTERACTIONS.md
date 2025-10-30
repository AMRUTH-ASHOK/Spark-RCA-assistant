# Agent Interaction Specification

## Bidirectional Communication Pattern

The Spark RCA Assistant follows a strict bidirectional communication pattern between agent pairs:

### 1. Supervisor <-> Reasoning

```
Supervisor                          Reasoning
    |                                   |
    |------- routing command --------->|
    |       (next_action="reasoning")  |
    |                                   |
    |                      [Reasoning processes]
    |                      [Assesses evidence]
    |                      [Generates hypotheses]
    |                                   |
    |<------ state update -------------|
    |    (hypotheses, draft, status)   |
```

**Flow:**
- Supervisor initiates reasoning cycles
- Reasoning assesses evidence and generates hypotheses
- Reasoning returns results to Supervisor
- Supervisor decides next action based on results

### 2. Supervisor <-> Critic

```
Supervisor                          Critic
    |                                   |
    |------- routing command --------->|
    |       (next_action="critic")     |
    |                                   |
    |                      [Critic validates]
    |                      [Checks draft vs evidence]
    |                                   |
    |<------ validation result --------|
    |   (critic_approved, confidence)  |
```

**Flow:**
- Supervisor requests validation when draft is ready
- Critic validates claims against evidence
- Critic returns approval and confidence adjustment to Supervisor
- Supervisor uses validation to decide termination

### 3. Reasoning <-> LogAnalyser

```
Reasoning                        LogAnalyser
    |                                   |
    |------- analysis request -------->|
    |   (next_action="analyzer",       |
    |    hypotheses)                    |
    |                                   |
    |                      [LogAnalyser processes]
    |                      [Converts to keywords]
    |                                   |
    |<------ keywords list ------------|
    |   (keywords, rationale)          |
```

**Flow:**
- Reasoning determines need for log analysis
- LogAnalyser converts hypotheses to search keywords
- LogAnalyser passes keywords to LogParser
- After LogParser completes, flow returns to Reasoning for reassessment

### 4. LogAnalyser <-> LogParser

```
LogAnalyser                      LogParser
    |                                   |
    |------- search request --------->|
    |   (keywords, logs_path)          |
    |                                   |
    |                      [LogParser searches]
    |                      [Uses grep/GC tools]
    |                                   |
    |<------ evidence snippets --------|
    |   (log_snippets, evidence)       |
    |                                   |
    |---- acknowledgment ------------->|
    |                                   |
    |<---- flow back to LogAnalyser ---|
    |                                   |
    v
Back to Reasoning
```

**Flow:**
- LogAnalyser provides keywords to LogParser
- LogParser searches logs using specialized tools
- LogParser returns evidence to LogAnalyser
- LogAnalyser confirms receipt
- Flow returns to Reasoning with accumulated evidence

## Complete Interaction Sequence

### Initial Phase
```
User Request
    |
    v
Supervisor (iteration=0)
    |
    v
Reasoning (assess: need_more=true)
    |
    v
LogAnalyser (generate keywords)
    |
    v
LogParser (search logs)
    |
    v
LogAnalyser (receive evidence)
    |
    v
Reasoning (reassess with evidence)
```

### Evidence Gathering Loop
```
Reasoning (still need_more AND loops < MAX)
    |
    v
LogAnalyser (refine keywords)
    |
    v
LogParser (deeper search)
    |
    v
LogAnalyser (more evidence)
    |
    v
Reasoning (reassess again)
```

### Draft and Validation Phase
```
Reasoning (sufficient evidence -> create draft)
    |
    v
Supervisor (receives draft)
    |
    v
Critic (validate draft)
    |
    v
Supervisor (receives validation)
    |
    v
Decision: END or continue
```

## State Flow Through Bidirectional Paths

### Forward Path (Command)
- Supervisor sets `next_action`
- Graph router directs to appropriate agent
- Agent receives full state

### Return Path (Results)
- Agent processes and updates relevant state fields
- Returns partial state update
- Graph router directs back to calling agent
- Calling agent merges updates into state

## Router Functions

### supervisor_router
```python
def supervisor_router(state: AgentState) -> NodeType:
    nxt = state.get("next_action", "")
    if nxt == "critic": return "critic"
    if nxt == "reasoning": return "reasoning"
    return "__end__"
```

### reasoning_router
```python
def reasoning_router(state: AgentState) -> str:
    next_action = state.get("next_action", "")
    if next_action == "analyzer": return "analyzer"
    return "supervisor"
```

### analyzer_router
```python
def analyzer_router(state: AgentState) -> str:
    # Always goes to parser first
    return "parser"
```

### parser_router
```python
def parser_router(state: AgentState) -> str:
    # Returns to reasoning to reassess
    return "reasoning"
```

## Loop Boundaries

### Outer Loop: Supervisor <-> Reasoning <-> Critic
- Controlled by `iteration` counter
- Maximum: `MAX_OUTER_ITERATIONS` (default: 3)
- Terminates when confidence threshold met OR max reached

### Inner Loop: Reasoning <-> LogAnalyser <-> LogParser
- Controlled by `analyze_parse_loops` counter
- Maximum: `MAX_ANALYZE_PARSE_LOOPS` (default: 3)
- Nested within Reasoning agent's decision
- Terminates when evidence sufficient OR max reached

## Communication Protocol

### Command Messages
- `next_action`: Specifies target agent
- `iteration`: Outer loop counter
- `analyze_parse_loops`: Inner loop counter

### Data Messages
- `hypotheses`: From Reasoning to LogAnalyser
- `keywords`: From LogAnalyser to LogParser
- `evidence`: From LogParser back through LogAnalyser to Reasoning
- `draft`: From Reasoning to Supervisor to Critic
- `critic_approved`: From Critic to Supervisor

## Error Handling in Bidirectional Flow

Each agent in a bidirectional pair:
1. Validates inputs received
2. Processes with error handling
3. Returns partial state (success or error info)
4. Never blocks the flow
5. Ensures return path is always taken

## State Synchronization

LangGraph manages state synchronization:
- Agents return partial state updates
- Graph merges updates into global state
- Next agent receives updated state
- Bidirectional paths maintain consistency
- No race conditions due to sequential execution

## Advantages of Bidirectional Pattern

1. **Clear Responsibility**: Each agent pair has defined roles
2. **Explicit Routing**: Graph structure shows all possible paths
3. **State Integrity**: Partial updates prevent overwrites
4. **Error Isolation**: Errors in one direction don't affect return path
5. **Testability**: Each direction can be tested independently
6. **Modularity**: Agents can be replaced without changing others
7. **Debugging**: Flow is traceable through state history
