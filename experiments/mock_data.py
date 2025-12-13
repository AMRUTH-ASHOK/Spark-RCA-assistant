"""
Mock Data Fixtures for Agent Testing.

This module provides realistic mock data for testing individual agents
without requiring actual Spark logs.
"""

from typing import Dict, Any, List


def create_mock_evidence_map() -> Dict[str, Dict[str, Any]]:
    """
    Create a realistic mock evidence map with common Spark error patterns.
    
    Returns:
        Evidence map with OOM errors, executor losses, and stage failures
    """
    return {
        "OutOfMemoryError: Java heap space": {
            "count": 15,
            "timestamps": [
                "25/10/08 06:23:27",
                "25/10/08 06:23:35", 
                "25/10/08 06:23:42",
                "25/10/08 06:24:01",
                "25/10/08 06:24:15"
            ],
            "files": [
                "/Volumes/logs/service=executor/executor-1.log",
                "/Volumes/logs/service=executor/executor-2.log",
                "/Volumes/logs/service=executor/executor-3.log"
            ],
            "sample_lines": [
                "25/10/08 06:23:27 ERROR Executor: Exception in task 47.0 in stage 3.0 (TID 1234): java.lang.OutOfMemoryError: Java heap space",
                "25/10/08 06:23:35 ERROR Executor: Exception in task 48.0 in stage 3.0 (TID 1235): java.lang.OutOfMemoryError: Java heap space at shuffle"
            ],
            "variables": ["executor 1", "executor 2", "executor 3", "stage 3", "task 47", "task 48", "TID 1234"]
        },
        "Lost executor * on *: Container killed by YARN": {
            "count": 3,
            "timestamps": ["25/10/08 06:24:01", "25/10/08 06:25:12"],
            "files": ["/Volumes/logs/service=driver/driver.log"],
            "sample_lines": [
                "25/10/08 06:24:01 WARN TaskSetManager: Lost executor 1 on worker-1: Container killed by YARN for exceeding memory limits. 8.5 GB of 8 GB physical memory used.",
                "25/10/08 06:25:12 WARN TaskSetManager: Lost executor 2 on worker-2: Container killed by YARN for exceeding memory limits."
            ],
            "variables": ["executor 1", "executor 2", "worker-1", "worker-2"]
        },
        "Stage * failed after * task failures": {
            "count": 2,
            "timestamps": ["25/10/08 06:26:00"],
            "files": ["/Volumes/logs/service=driver/driver.log"],
            "sample_lines": [
                "25/10/08 06:26:00 ERROR DAGScheduler: Stage 3 (collect at Query.scala:42) failed after 4 task failures"
            ],
            "variables": ["stage 3"]
        }
    }


def create_mock_evidence_summary(evidence_map: Dict = None) -> str:
    """
    Create a formatted evidence summary string for LLM consumption.
    
    Args:
        evidence_map: Optional evidence map to format. If None, uses default.
        
    Returns:
        Formatted evidence summary string
    """
    if evidence_map is None:
        evidence_map = create_mock_evidence_map()
    
    lines = [
        f"=== Evidence Summary ({len(evidence_map)} unique error patterns) ===\n"
    ]
    
    for idx, (pattern, entry) in enumerate(evidence_map.items(), 1):
        ts_str = ", ".join(entry["timestamps"][:3])
        if len(entry["timestamps"]) > 3:
            ts_str += f" ... (+{len(entry['timestamps']) - 3} more)"
        
        files_str = ", ".join([f.split("/")[-1] for f in entry["files"][:2]])
        if len(entry["files"]) > 2:
            files_str += f" ... (+{len(entry['files']) - 2} more)"
        
        lines.append(f"\n[{idx}] Error Pattern: {pattern}")
        lines.append(f"    Occurrences: {entry['count']}")
        lines.append(f"    Timestamps: {ts_str}")
        lines.append(f"    Files: {files_str}")
        if entry["sample_lines"]:
            lines.append(f"    Sample: {entry['sample_lines'][0][:150]}...")
    
    return "\n".join(lines)


# =============================================================================
# Supervisor Agent Test States
# =============================================================================

SUPERVISOR_TEST_STATES = {
    "initial_state": {
        "description": "First iteration, no prior work done",
        "state": {
            "iteration": 0,
            "last_status": "",
            "confidence": 0.0,
            "critic_approved": False,
            "draft": {},
            "evidence_map": {},
            "evidence_summary": "",
            "critique": ""
        },
        "expected": {
            "next_action": "reasoning"
        }
    },
    "after_summarization": {
        "description": "Reasoning completed with draft, needs critic validation",
        "state": {
            "iteration": 1,
            "last_status": "summarized",
            "confidence": 0.72,
            "critic_approved": False,
            "draft": {
                "problem": "Spark job failed due to executor OOM during shuffle phase",
                "rca": "[PROVEN] Executors exhausted heap memory during shuffle\n[PROVEN] YARN killed containers for exceeding limits\n[INFERRED] Data skew caused uneven memory pressure",
                "mitigation": "Increase spark.executor.memory to 12g, enable adaptive execution"
            },
            "evidence_map": create_mock_evidence_map(),
            "evidence_summary": create_mock_evidence_summary(),
            "critique": ""
        },
        "expected": {
            "next_action": "critic"
        }
    },
    "critic_approved_high_confidence": {
        "description": "Critic approved with high confidence - should end",
        "state": {
            "iteration": 2,
            "last_status": "summarized",
            "confidence": 0.85,
            "critic_approved": True,
            "draft": {
                "problem": "Spark job failed due to executor OOM",
                "rca": "[PROVEN] Memory exhaustion with clear evidence",
                "mitigation": "Increase executor memory"
            },
            "evidence_map": create_mock_evidence_map(),
            "evidence_summary": create_mock_evidence_summary(),
            "critique": "Analysis is well-supported by evidence"
        },
        "expected": {
            "next_action": "end"
        }
    },
    "critic_rejected_low_confidence": {
        "description": "Critic rejected or low confidence - needs more reasoning",
        "state": {
            "iteration": 2,
            "last_status": "summarized",
            "confidence": 0.45,
            "critic_approved": False,
            "draft": {
                "problem": "Job failed",
                "rca": "[INFERRED] Possible memory issue",
                "mitigation": "Check logs"
            },
            "evidence_map": {},
            "evidence_summary": "(no evidence)",
            "critique": "Insufficient evidence to support claims"
        },
        "expected": {
            "next_action": "reasoning"
        }
    },
    "max_iterations_reached": {
        "description": "Maximum iterations reached - force end",
        "state": {
            "iteration": 6,
            "last_status": "summarized",
            "confidence": 0.55,
            "critic_approved": False,
            "draft": {
                "problem": "Partial analysis",
                "rca": "Incomplete due to iteration limit",
                "mitigation": "Manual investigation needed"
            },
            "evidence_map": create_mock_evidence_map(),
            "evidence_summary": create_mock_evidence_summary(),
            "critique": "Analysis incomplete"
        },
        "expected": {
            "next_action": "end"
        }
    }
}


# =============================================================================
# Reasoning Agent Test States
# =============================================================================

REASONING_TEST_STATES = {
    "no_evidence": {
        "description": "Initial state with no evidence - should request analyzer",
        "state": {
            "user_context": "Spark job failed with executor losses during shuffle phase. Query ID: abc123",
            "logs_path": "/Volumes/test/spark-logs/",
            "hypotheses": [],
            "evidence_map": {},
            "evidence_summary": "",
            "keywords": [],
            "iteration": 0,
            "analyze_parse_loops": 0,
            "last_logs_chunk": ""
        },
        "expected": {
            "next_action": "analyzer",
            "has_hypotheses": True
        }
    },
    "partial_evidence": {
        "description": "Some evidence but not sufficient - should request more",
        "state": {
            "user_context": "Spark job failed with OOM errors",
            "logs_path": "/Volumes/test/spark-logs/",
            "hypotheses": ["Memory exhaustion during shuffle"],
            "evidence_map": {
                "OutOfMemoryError": {
                    "count": 2,
                    "timestamps": ["06:23:27"],
                    "files": ["/logs/executor.log"],
                    "sample_lines": ["OOM error"],
                    "variables": []
                }
            },
            "evidence_summary": "[1] OutOfMemoryError (2 occurrences)",
            "keywords": ["ERROR", "OutOfMemoryError"],
            "iteration": 1,
            "analyze_parse_loops": 1,
            "last_logs_chunk": "Found OOM errors"
        },
        "expected": {
            "next_action": "analyzer"
        }
    },
    "sufficient_evidence": {
        "description": "Rich evidence available - should summarize",
        "state": {
            "user_context": "Spark job failed with executor OOM",
            "logs_path": "/Volumes/test/spark-logs/",
            "hypotheses": [
                "Memory exhaustion during shuffle",
                "Insufficient executor memory allocation",
                "Data skew causing memory pressure"
            ],
            "evidence_map": create_mock_evidence_map(),
            "evidence_summary": create_mock_evidence_summary(),
            "keywords": ["ERROR", "OutOfMemoryError", "executor lost", "Container killed"],
            "iteration": 2,
            "analyze_parse_loops": 3,
            "last_logs_chunk": "Detailed logs showing OOM and container kills"
        },
        "expected": {
            "last_status": "summarized",
            "has_draft": True
        }
    },
    "max_loops_reached": {
        "description": "Max analyze-parse loops reached - force summarize",
        "state": {
            "user_context": "Job failed",
            "logs_path": "/Volumes/test/spark-logs/",
            "hypotheses": ["Unknown failure"],
            "evidence_map": {},
            "evidence_summary": "(minimal evidence)",
            "keywords": ["ERROR"],
            "iteration": 3,
            "analyze_parse_loops": 6,  # MAX_ANALYZE_PARSE_LOOPS
            "last_logs_chunk": ""
        },
        "expected": {
            "last_status": "summarized"
        }
    }
}


# =============================================================================
# Analyzer Agent Test States
# =============================================================================

ANALYZER_TEST_STATES = {
    "initial_keywords": {
        "description": "Generate initial keywords from hypotheses",
        "state": {
            "user_context": "Job failed with OOM errors during shuffle",
            "hypotheses": [
                "Memory exhaustion during shuffle",
                "Data skew causing memory pressure"
            ],
            "keywords": [],
            "last_logs_chunk": "",
            "analyze_parse_loops": 0
        },
        "expected": {
            "has_keywords": True,
            "includes_default_keywords": True
        }
    },
    "refined_keywords": {
        "description": "Refine keywords based on previous results",
        "state": {
            "user_context": "Job failed with GC overhead errors",
            "hypotheses": [
                "GC pauses too long",
                "Stop-the-world events causing timeouts"
            ],
            "keywords": ["ERROR", "Exception", "OutOfMemoryError"],
            "last_logs_chunk": "Found multiple GC overhead limit exceeded errors in executor logs",
            "analyze_parse_loops": 1
        },
        "expected": {
            "has_keywords": True,
            "should_include_gc_keywords": True
        }
    },
    "convergence_test": {
        "description": "Test keyword generation convergence",
        "state": {
            "user_context": "Complete investigation",
            "hypotheses": ["Root cause identified"],
            "keywords": ["ERROR", "Exception", "OutOfMemoryError", "executor lost", "GC", "heap"],
            "last_logs_chunk": "All relevant errors found",
            "analyze_parse_loops": 4
        },
        "expected": {
            "minimal_new_keywords": True
        }
    }
}


# =============================================================================
# Parser Agent Test States
# =============================================================================

PARSER_TEST_STATES = {
    "valid_search": {
        "description": "Valid logs path with keywords",
        "state": {
            "logs_path": "/Volumes/amruthcatalogtest/default/testsparklogs/sample/",
            "last_generated_keywords": ["ERROR", "Exception", "OutOfMemoryError"],
            "keywords": ["ERROR"],
            "evidence_map": {},
            "evidence_summary": ""
        },
        "expected": {
            "has_evidence_map": True,
            "has_summary": True
        }
    },
    "no_path_error": {
        "description": "Missing logs path should error",
        "state": {
            "logs_path": "",
            "last_generated_keywords": ["ERROR"],
            "keywords": ["ERROR"],
            "evidence_map": {},
            "evidence_summary": ""
        },
        "expected": {
            "has_error": True
        }
    },
    "no_keywords_error": {
        "description": "Missing keywords should error",
        "state": {
            "logs_path": "/Volumes/test/logs/",
            "last_generated_keywords": [],
            "keywords": [],
            "evidence_map": {},
            "evidence_summary": ""
        },
        "expected": {
            "has_error": True
        }
    },
    "gc_analysis_trigger": {
        "description": "GC-related keywords should trigger GC analysis",
        "state": {
            "logs_path": "/Volumes/amruthcatalogtest/default/testsparklogs/sample/",
            "last_generated_keywords": ["GC", "heap", "pause", "memory"],
            "keywords": ["GC", "OutOfMemoryError"],
            "evidence_map": {},
            "evidence_summary": ""
        },
        "expected": {
            "may_include_gc_analysis": True
        }
    }
}


# =============================================================================
# Critic Agent Test States
# =============================================================================

CRITIC_TEST_STATES = {
    "well_supported_draft": {
        "description": "Draft with strong evidence support",
        "state": {
            "draft": {
                "problem": "Spark job failed due to executor memory exhaustion during shuffle phase",
                "rca": """1. [PROVEN] Job failed at stage 3 during shuffle (Evidence: Stage 3 failed after 4 task failures)
2. [PROVEN] Executors ran out of heap memory (Evidence: 15 OutOfMemoryError occurrences)
3. [PROVEN] YARN killed containers for memory limits (Evidence: Container killed by YARN messages)
4. [INFERRED] Memory configuration insufficient for data volume""",
                "mitigation": """1. Increase executor memory from 8GB to 12GB (spark.executor.memory=12g)
2. Enable adaptive query execution (spark.sql.adaptive.enabled=true)
3. Add memory overhead (spark.executor.memoryOverhead=2g)"""
            },
            "evidence_summary": create_mock_evidence_summary(),
            "confidence": 0.75
        },
        "expected": {
            "should_approve": True,
            "confidence_stable": True
        }
    },
    "unsupported_claims": {
        "description": "Draft with claims not supported by evidence",
        "state": {
            "draft": {
                "problem": "Job failed due to network issues",
                "rca": """1. [PROVEN] Network latency caused timeouts
2. [PROVEN] AWS experienced outage in us-west-2
3. [PROVEN] Shuffle service was unreachable""",
                "mitigation": "Use different availability zone"
            },
            "evidence_summary": create_mock_evidence_summary(),  # Only has OOM evidence
            "confidence": 0.90
        },
        "expected": {
            "should_approve": False,
            "confidence_lowered": True
        }
    },
    "low_confidence_draft": {
        "description": "Draft with low confidence should be rejected",
        "state": {
            "draft": {
                "problem": "Job failed",
                "rca": "[INFERRED] Something went wrong",
                "mitigation": "Check logs"
            },
            "evidence_summary": "(no evidence)",
            "confidence": 0.40
        },
        "expected": {
            "should_approve": False,
            "reason_mentions_confidence": True
        }
    },
    "confidence_calculation_error": {
        "description": "Draft with incorrect confidence calculation",
        "state": {
            "draft": {
                "problem": "Executor OOM",
                "rca": """1. [PROVEN] OOM occurred
2. [INFERRED] Due to data skew
3. [INFERRED] Shuffle was large
4. [INFERRED] Config was wrong""",
                "mitigation": "Fix config"
            },
            "evidence_summary": "[1] OutOfMemoryError (5 occurrences)",
            "confidence": 0.90  # Wrong: should be 1/4 = 0.25
        },
        "expected": {
            "confidence_adjusted": True
        }
    }
}


# =============================================================================
# Full Workflow Test Scenarios
# =============================================================================

WORKFLOW_TEST_SCENARIOS = {
    "oom_investigation": {
        "description": "Investigate OOM errors in Spark job",
        "issue_type": "OutOfMemoryError",
        "initial_state": {
            "user_context": """Our Spark job (Query ID: test-query-001) failed with OutOfMemoryError.
The job was processing a large shuffle operation when executors started failing.
We need to understand why memory ran out and how to fix it.""",
            "logs_path": "/Volumes/amruthcatalogtest/default/testsparklogs/sample/",
            "iteration": 0,
            "hypotheses": [],
            "keywords": [],
            "evidence_map": {},
            "evidence_summary": "",
            "last_logs_chunk": "",
            "analyze_parse_loops": 0,
            "draft": {},
            "confidence": 0.0,
            "critic_approved": False,
            "critique": "",
            "last_status": "",
            "next_action": ""
        },
        "expected": {
            "min_confidence": 0.5,
            "has_evidence": True,
            "has_final_report": True
        }
    },
    "executor_loss_investigation": {
        "description": "Investigate executor losses",
        "issue_type": "ExecutorLost",
        "initial_state": {
            "user_context": """Multiple executors were lost during job execution.
The job keeps retrying but eventually fails.
Need to find the root cause of executor losses.""",
            "logs_path": "/Volumes/amruthcatalogtest/default/testsparklogs/sample/",
            "iteration": 0,
            "hypotheses": [],
            "keywords": [],
            "evidence_map": {},
            "evidence_summary": "",
            "last_logs_chunk": "",
            "analyze_parse_loops": 0,
            "draft": {},
            "confidence": 0.0,
            "critic_approved": False,
            "critique": "",
            "last_status": "",
            "next_action": ""
        },
        "expected": {
            "min_confidence": 0.5,
            "has_evidence": True,
            "has_final_report": True
        }
    },
    "gc_pressure_investigation": {
        "description": "Investigate GC pressure and pauses",
        "issue_type": "GCPressure",
        "initial_state": {
            "user_context": """Job is running slowly with frequent GC pauses.
Suspect memory pressure is causing performance issues.
Need GC log analysis.""",
            "logs_path": "/Volumes/amruthcatalogtest/default/testsparklogs/sample/",
            "iteration": 0,
            "hypotheses": [],
            "keywords": [],
            "evidence_map": {},
            "evidence_summary": "",
            "last_logs_chunk": "",
            "analyze_parse_loops": 0,
            "draft": {},
            "confidence": 0.0,
            "critic_approved": False,
            "critique": "",
            "last_status": "",
            "next_action": ""
        },
        "expected": {
            "min_confidence": 0.5,
            "has_evidence": True,
            "has_final_report": True
        }
    }
}


def get_workflow_scenario(scenario: str) -> Dict[str, Any]:
    """
    Get a workflow test scenario.
    
    Args:
        scenario: Scenario name from WORKFLOW_TEST_SCENARIOS
        
    Returns:
        Workflow scenario dictionary with initial_state, expected, description, issue_type
        
    Raises:
        ValueError: If scenario not found
    """
    if scenario not in WORKFLOW_TEST_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}. Valid: {list(WORKFLOW_TEST_SCENARIOS.keys())}")
    
    return WORKFLOW_TEST_SCENARIOS[scenario]


def get_test_state(agent: str, scenario: str) -> Dict[str, Any]:
    """
    Get a test state for a specific agent and scenario.
    
    Args:
        agent: Agent name (supervisor, reasoning, analyzer, parser, critic)
        scenario: Scenario name from the test states
        
    Returns:
        Test state dictionary
        
    Raises:
        ValueError: If agent or scenario not found
    """
    state_maps = {
        "supervisor": SUPERVISOR_TEST_STATES,
        "reasoning": REASONING_TEST_STATES,
        "analyzer": ANALYZER_TEST_STATES,
        "parser": PARSER_TEST_STATES,
        "critic": CRITIC_TEST_STATES,
    }
    
    if agent not in state_maps:
        raise ValueError(f"Unknown agent: {agent}. Valid: {list(state_maps.keys())}")
    
    agent_states = state_maps[agent]
    if scenario not in agent_states:
        raise ValueError(f"Unknown scenario '{scenario}' for {agent}. Valid: {list(agent_states.keys())}")
    
    return agent_states[scenario]
