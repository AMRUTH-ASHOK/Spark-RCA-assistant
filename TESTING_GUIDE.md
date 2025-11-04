# Testing Guide: Validating the Implementation

## Pre-Test Checklist

- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] LangChain and LangGraph versions compatible
- [ ] MLflow configured and running
- [ ] Have access to sample Spark logs
- [ ] Environment variables set (if needed)

---

## Test 1: Basic Functionality Test

### Objective
Verify the system runs end-to-end with the new evidence_map.

### Steps

```python
from multiAgentSystem import build_graph

# Build the graph
graph = build_graph()

# Test with minimal input
result = graph.invoke({
    "user_context": "Test run - verify system works",
    "logs_path": "/path/to/sample/logs",
    "iteration": 0,
    "hypotheses": [],
    "keywords": [],
    "evidence_map": {},
})

# Validate results
assert "draft" in result
assert "problem" in result["draft"]
assert "rca" in result["draft"]
assert "mitigation" in result["draft"]
assert "confidence" in result
assert "evidence_map" in result

print("✅ Test 1 PASSED: System runs successfully")
```

**Expected Outcome:**
- No errors during execution
- `draft` contains problem/rca/mitigation
- `evidence_map` is populated (not empty)
- `confidence` is between 0.0 and 1.0

---

## Test 2: Evidence Map Validation

### Objective
Verify evidence deduplication is working correctly.

### Steps

```python
from multiAgentSystem import get_evidence_summary_stats, format_evidence_map_for_prompt

# Run analysis
result = graph.invoke({
    "user_context": "Executor failures with memory issues",
    "logs_path": "/path/to/logs/with/repeated/errors",
    "iteration": 0,
    "hypotheses": [],
    "keywords": [],
    "evidence_map": {},
})

# Check evidence_map structure
evidence_map = result["evidence_map"]
assert isinstance(evidence_map, dict), "evidence_map should be a dictionary"

# Check statistics
stats = get_evidence_summary_stats(evidence_map)
print(f"Unique patterns: {stats['unique_patterns']}")
print(f"Total occurrences: {stats['total_occurrences']}")
print(f"Unique files: {stats['unique_files']}")

# Validate deduplication
assert stats['total_occurrences'] >= stats['unique_patterns'], \
    "Total occurrences should be >= unique patterns (deduplication working)"

# Check each entry structure
for key, entry in evidence_map.items():
    assert "content" in entry
    assert "timestamps" in entry
    assert "count" in entry
    assert "file_path" in entry
    assert "pattern" in entry
    assert isinstance(entry["timestamps"], list)
    assert entry["count"] == len(entry["timestamps"]) or entry["count"] >= 1

# Verify formatting works
formatted = format_evidence_map_for_prompt(evidence_map, max_entries=5)
assert len(formatted) > 0
assert "━━━" in formatted  # Check separator is present

print("✅ Test 2 PASSED: Evidence map structure is correct")
```

**Expected Outcome:**
- `evidence_map` is a properly structured dictionary
- Each entry has all required fields
- `total_occurrences >= unique_patterns` (deduplication happening)
- Formatting produces readable output

---

## Test 3: Token Reduction Validation

### Objective
Measure actual token savings from evidence_map.

### Steps

```python
import tiktoken

def count_tokens(text: str, model="gpt-4") -> int:
    """Count tokens in text."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Run analysis
result = graph.invoke({
    "user_context": "Performance degradation in stage 3",
    "logs_path": "/path/to/large/log/directory",
    "iteration": 0,
    "hypotheses": [],
    "keywords": [],
    "evidence_map": {},
})

# Compare token counts
evidence_map = result.get("evidence_map", {})
legacy_evidence = result.get("evidence", [])

if evidence_map:
    # Tokens in evidence_map
    evidence_map_str = format_evidence_map_for_prompt(evidence_map)
    evidence_map_tokens = count_tokens(evidence_map_str)
    
    # Simulate legacy format tokens (if we stored all logs separately)
    # This is an estimate based on total occurrences
    stats = get_evidence_summary_stats(evidence_map)
    estimated_legacy_tokens = evidence_map_tokens * (stats['total_occurrences'] / stats['unique_patterns'])
    
    reduction_pct = ((estimated_legacy_tokens - evidence_map_tokens) / estimated_legacy_tokens) * 100
    
    print(f"Evidence map tokens: {evidence_map_tokens:,}")
    print(f"Estimated legacy tokens: {estimated_legacy_tokens:,.0f}")
    print(f"Token reduction: {reduction_pct:.1f}%")
    
    # Validate savings
    assert reduction_pct > 50, f"Expected >50% reduction, got {reduction_pct:.1f}%"
    print("✅ Test 3 PASSED: Token reduction validated")
else:
    print("⚠️  Test 3 SKIPPED: No evidence_map in result")
```

**Expected Outcome:**
- Token reduction > 50% (ideally 75-85%)
- Evidence map tokens significantly lower than estimated legacy
- No token count overflow errors

---

## Test 4: MLflow Tracing Validation

### Objective
Verify tool calls appear in MLflow traces.

### Steps

```python
import mlflow

# Enable autologging
mlflow.langchain.autolog()

# Run with MLflow tracking
with mlflow.start_run() as run:
    result = graph.invoke({
        "user_context": "Executor OOM errors",
        "logs_path": "/path/to/logs",
        "iteration": 0,
        "hypotheses": [],
        "keywords": [],
        "evidence_map": {},
    })
    
    run_id = run.info.run_id
    experiment_id = run.info.experiment_id

print(f"\n{'='*60}")
print(f"MLflow Run ID: {run_id}")
print(f"Experiment ID: {experiment_id}")
print(f"{'='*60}")
print("\nManual Verification Steps:")
print("1. Open MLflow UI")
print(f"2. Navigate to experiment {experiment_id}")
print(f"3. Open run {run_id}")
print("4. Click on 'Traces' tab")
print("\nVerify you see:")
print("  ✓ Supervisor node calls")
print("  ✓ Reasoning node calls")
print("  ✓ Parser agent calls")
print("  ✓ Tool calls (grep_logs, analyze_gc_logs)")
print("  ✓ Input/output for each tool")
print(f"{'='*60}\n")

print("✅ Test 4 SETUP COMPLETE: Check MLflow UI manually")
```

**Expected Outcome (in MLflow UI):**
```
Trace:
├─ supervisor_node
├─ reasoning_node
├─ analyzer_node  
├─ parser_node
│  ├─ grep_logs (tool call)
│  │  ├─ Input: {logs_path: "...", keywords: [...]}
│  │  └─ Output: [{path: "...", line_no: 123, ...}]
│  └─ (possibly) analyze_gc_logs (tool call)
│     ├─ Input: {log_content: "...", ...}
│     └─ Output: {summary: "...", top_pauses: "..."}
└─ critic_node
```

---

## Test 5: Parser Agent Tool Selection

### Objective
Verify parser agent autonomously chooses correct tools.

### Steps

```python
# Test 5a: Should use grep_logs for general errors
result_a = graph.invoke({
    "user_context": "Find executor failures",
    "logs_path": "/path/to/logs",
    "iteration": 0,
    "hypotheses": ["Executor lost during shuffle"],
    "keywords": [],
    "evidence_map": {},
})

# Test 5b: Should use both grep_logs AND analyze_gc_logs for memory issues
result_b = graph.invoke({
    "user_context": "Memory issues causing executor crashes",
    "logs_path": "/path/to/logs",
    "iteration": 0,
    "hypotheses": ["OOM in executor", "GC pauses too long"],
    "keywords": [],
    "evidence_map": {},
})

print("Test 5a (general errors):")
print("  - Check MLflow trace shows 'grep_logs' tool call")
print("  - Evidence_map should contain executor failure logs")

print("\nTest 5b (memory issues):")
print("  - Check MLflow trace shows 'grep_logs' AND 'analyze_gc_logs'")
print("  - Evidence_map should contain GC-related logs")

print("\n✅ Test 5 SETUP COMPLETE: Verify tool selection in MLflow UI")
```

**Expected Outcome:**
- Test 5a: Only `grep_logs` tool call in trace
- Test 5b: Both `grep_logs` and `analyze_gc_logs` tool calls in trace
- Evidence_map contains relevant logs for each scenario

---

## Test 6: Backward Compatibility

### Objective
Verify system works with legacy `evidence` format.

### Steps

```python
# Test with legacy evidence list (instead of evidence_map)
result_legacy = graph.invoke({
    "user_context": "Test backward compatibility",
    "logs_path": "/path/to/logs",
    "iteration": 0,
    "hypotheses": [],
    "keywords": [],
    "evidence": [],  # Legacy format
    # Note: NOT including evidence_map
})

# System should still work
assert "draft" in result_legacy
assert "confidence" in result_legacy

# Should gracefully upgrade to evidence_map
if "evidence_map" in result_legacy:
    print("✅ System upgraded to evidence_map automatically")
else:
    print("⚠️  System using legacy evidence format")

print("✅ Test 6 PASSED: Backward compatibility maintained")
```

**Expected Outcome:**
- System runs without errors
- May automatically create evidence_map from evidence
- All outputs present and valid

---

## Test 7: Stress Test (Large Logs)

### Objective
Test performance with large log volumes.

### Steps

```python
import time

# Test with large log directory
start_time = time.time()

result = graph.invoke({
    "user_context": "Performance issues in production job",
    "logs_path": "/path/to/very/large/logs",  # >100MB of logs
    "iteration": 0,
    "hypotheses": [],
    "keywords": [],
    "evidence_map": {},
})

end_time = time.time()
duration = end_time - start_time

# Check performance
stats = get_evidence_summary_stats(result["evidence_map"])
print(f"Processed in: {duration:.2f} seconds")
print(f"Unique patterns found: {stats['unique_patterns']}")
print(f"Total occurrences: {stats['total_occurrences']}")
print(f"Deduplication ratio: {stats['total_occurrences'] / stats['unique_patterns']:.2f}x")

# Performance assertions
assert duration < 300, f"Processing took too long: {duration:.2f}s"
assert stats['unique_patterns'] > 0, "Should find some patterns"

print("✅ Test 7 PASSED: Large log processing successful")
```

**Expected Outcome:**
- Completes in reasonable time (<5 minutes)
- Evidence map populated with deduplicated entries
- High deduplication ratio for repeated errors

---

## Test 8: Confidence Calculation Validation

### Objective
Verify mathematical confidence calculation is correct.

### Steps

```python
import re

result = graph.invoke({
    "user_context": "Job failed with stage materialization error",
    "logs_path": "/path/to/logs",
    "iteration": 0,
    "hypotheses": [],
    "keywords": [],
    "evidence_map": {},
})

# Extract RCA and confidence
rca = result["draft"]["rca"]
confidence = result["confidence"]

# Count [PROVEN] and [INFERRED] statements
proven_count = len(re.findall(r'\[PROVEN\]', rca))
inferred_count = len(re.findall(r'\[INFERRED\]', rca))
total_statements = proven_count + inferred_count

# Calculate expected confidence
if total_statements > 0:
    expected_confidence = proven_count / total_statements
    
    print(f"Proven statements: {proven_count}")
    print(f"Inferred statements: {inferred_count}")
    print(f"Total statements: {total_statements}")
    print(f"Expected confidence: {expected_confidence:.2f}")
    print(f"Actual confidence: {confidence:.2f}")
    
    # Allow for rounding differences
    diff = abs(expected_confidence - confidence)
    assert diff < 0.1, f"Confidence calculation error: expected {expected_confidence:.2f}, got {confidence:.2f}"
    
    print("✅ Test 8 PASSED: Confidence calculation is correct")
else:
    print("⚠️  Test 8 SKIPPED: No [PROVEN]/[INFERRED] markers in RCA")
```

**Expected Outcome:**
- RCA contains [PROVEN] and [INFERRED] markers
- Confidence matches proven_count / total_statements (within 0.1)
- Confidence is between 0.0 and 1.0

---

## Test 9: Integration Test (Full Workflow)

### Objective
Test complete workflow from start to finish.

### Steps

```python
import json

print("="*60)
print("INTEGRATION TEST: Full RCA Workflow")
print("="*60)

# Step 1: Initialize
print("\n[Step 1] Initializing system...")
graph = build_graph()
print("✓ Graph built successfully")

# Step 2: Run analysis
print("\n[Step 2] Running RCA analysis...")
result = graph.invoke({
    "user_context": "Production Spark job failed after 2 hours with executor failures",
    "logs_path": "/path/to/production/logs",
    "iteration": 0,
    "hypotheses": [],
    "keywords": [],
    "evidence_map": {},
})
print("✓ Analysis complete")

# Step 3: Validate outputs
print("\n[Step 3] Validating outputs...")
assert "draft" in result
assert "evidence_map" in result
assert "confidence" in result
assert result.get("critic_approved") is not None
print("✓ All required outputs present")

# Step 4: Check evidence
print("\n[Step 4] Checking evidence quality...")
stats = get_evidence_summary_stats(result["evidence_map"])
print(f"  - Unique patterns: {stats['unique_patterns']}")
print(f"  - Total occurrences: {stats['total_occurrences']}")
print(f"  - Files analyzed: {stats['unique_files']}")
assert stats['unique_patterns'] > 0, "Should find evidence"
print("✓ Evidence collected and deduplicated")

# Step 5: Check draft quality
print("\n[Step 5] Checking draft quality...")
draft = result["draft"]
assert len(draft["problem"]) > 50, "Problem statement too short"
assert len(draft["rca"]) > 100, "RCA too short"
assert len(draft["mitigation"]) > 50, "Mitigation too short"
assert "[PROVEN]" in draft["rca"] or "[INFERRED]" in draft["rca"], "Missing evidence markers"
print("✓ Draft contains detailed analysis")

# Step 6: Check confidence
print("\n[Step 6] Checking confidence...")
confidence = result["confidence"]
assert 0.0 <= confidence <= 1.0, f"Invalid confidence: {confidence}"
print(f"  - Confidence: {confidence:.2f}")
print("✓ Confidence is valid")

# Step 7: Final summary
print("\n[Step 7] Generating summary...")
print("\n" + "="*60)
print("PROBLEM:")
print(draft["problem"][:200] + "...")
print("\nROOT CAUSE:")
print(draft["rca"][:300] + "...")
print("\nMITIGATION:")
print(draft["mitigation"][:200] + "...")
print(f"\nCONFIDENCE: {confidence:.2f}")
print(f"\nCRITIC APPROVED: {result.get('critic_approved')}")
print("="*60)

print("\n✅ TEST 9 PASSED: Full workflow successful!")
```

**Expected Outcome:**
- All steps complete without errors
- Evidence collected and deduplicated
- Draft contains problem/rca/mitigation with evidence markers
- Confidence is valid and calculated correctly
- Critic provides feedback

---

## Performance Benchmarks

### Target Metrics

| Metric | Target | Acceptable | Warning |
|--------|--------|------------|---------|
| Token reduction | >75% | >50% | <50% |
| Processing time (100MB logs) | <3 min | <5 min | >5 min |
| Unique patterns found | >10 | >5 | <5 |
| Confidence accuracy | ±0.05 | ±0.10 | >±0.10 |
| Memory usage | <2GB | <4GB | >4GB |

### Running Benchmarks

```python
import psutil
import time
import tiktoken

def run_benchmark(logs_path: str):
    """Run full benchmark suite."""
    
    process = psutil.Process()
    start_memory = process.memory_info().rss / 1024 / 1024  # MB
    start_time = time.time()
    
    # Run analysis
    result = graph.invoke({
        "user_context": "Benchmark test",
        "logs_path": logs_path,
        "iteration": 0,
        "hypotheses": [],
        "keywords": [],
        "evidence_map": {},
    })
    
    end_time = time.time()
    end_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Calculate metrics
    duration = end_time - start_time
    memory_used = end_memory - start_memory
    
    stats = get_evidence_summary_stats(result["evidence_map"])
    evidence_str = format_evidence_map_for_prompt(result["evidence_map"])
    
    encoding = tiktoken.encoding_for_model("gpt-4")
    tokens = len(encoding.encode(evidence_str))
    
    # Print results
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"Processing time: {duration:.2f}s")
    print(f"Memory used: {memory_used:.2f} MB")
    print(f"Unique patterns: {stats['unique_patterns']}")
    print(f"Total occurrences: {stats['total_occurrences']}")
    print(f"Deduplication ratio: {stats['total_occurrences'] / stats['unique_patterns']:.2f}x")
    print(f"Evidence tokens: {tokens:,}")
    print(f"Confidence: {result['confidence']:.2f}")
    print("="*60 + "\n")
    
    return {
        "duration": duration,
        "memory_mb": memory_used,
        "tokens": tokens,
        "unique_patterns": stats['unique_patterns'],
        "deduplication_ratio": stats['total_occurrences'] / stats['unique_patterns']
    }

# Run benchmark
benchmark_results = run_benchmark("/path/to/benchmark/logs")
```

---

## Troubleshooting Common Issues

### Issue: evidence_map is empty

**Diagnosis:**
```python
if not result.get("evidence_map"):
    # Check if parser ran
    print("Last logs chunk:", result.get("last_logs_chunk"))
    # Check if keywords were generated
    print("Keywords used:", result.get("keywords"))
    # Check logs path
    print("Logs path:", result.get("logs_path"))
```

**Solutions:**
- Verify logs_path is valid and accessible
- Check that analyzer generated keywords
- Ensure grep_tool has permissions to read logs
- Verify logs contain matching patterns

### Issue: Tool calls not in MLflow trace

**Diagnosis:**
```python
import mlflow
print("Autolog enabled:", mlflow.langchain.autolog_is_enabled())
```

**Solutions:**
- Call `mlflow.langchain.autolog()` before running
- Check LangChain version compatibility
- Verify MLflow tracking URI is set
- Check if ReAct agent is properly created

### Issue: Low token savings

**Diagnosis:**
```python
stats = get_evidence_summary_stats(result["evidence_map"])
dedup_ratio = stats['total_occurrences'] / stats['unique_patterns']
print(f"Deduplication ratio: {dedup_ratio:.2f}x")

if dedup_ratio < 2:
    print("⚠️  Low deduplication - logs may have unique errors")
```

**Solutions:**
- Check if logs actually have repeated patterns
- Verify timestamp extraction is working
- Ensure content hashing is working correctly
- May need to adjust log block extraction

---

## Continuous Integration Tests

### Recommended CI Pipeline

```yaml
# .github/workflows/test.yml
name: Test Multi-Agent System

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run unit tests
        run: |
          python -m pytest tests/test_log_deduplicator.py
          python -m pytest tests/test_langchain_tools.py
      
      - name: Run integration tests
        run: python -m pytest tests/test_integration.py
      
      - name: Check token reduction
        run: python tests/benchmark_token_reduction.py
```

---

## Success Criteria Summary

✅ **All tests pass** without errors  
✅ **Token reduction > 50%** (ideally 75-85%)  
✅ **MLflow traces show tool calls**  
✅ **Parser autonomously selects tools**  
✅ **Evidence_map properly structured**  
✅ **Confidence calculation is accurate**  
✅ **Backward compatibility maintained**  
✅ **Processing time < 5 minutes** for large logs  

---

## Next Steps After Testing

1. ✅ All tests pass → Deploy to production
2. ⚠️  Some tests fail → Review failures, iterate
3. 📊 Benchmark performance → Optimize if needed
4. 📝 Document findings → Update team
5. 🚀 Monitor in production → Track metrics

**Happy Testing! 🧪**
