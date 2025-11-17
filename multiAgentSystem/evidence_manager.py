"""
Evidence Manager - Utilities for managing optimized evidence storage.

This module provides functions to extract error patterns, deduplicate evidence,
and format evidence for LLM consumption.
"""

import re
import json
from typing import Dict, List, Optional
from .state import EvidenceEntry


def extract_error_pattern(log_line: str) -> str:
    """
    Extract the error message pattern from a log line.

    Log format expected: TIMESTAMP LEVEL CLASS: MESSAGE
    Example: "25/10/08 06:23:27 WARN DriverCorral$: Short-term memory (STM) sync requested"
    Returns: "Short-term memory (STM) sync requested"

    Args:
        log_line: Full log line from grep results

    Returns:
        Extracted error pattern (message part)
    """
    if not log_line or not log_line.strip():
        return log_line.strip()

    # Try to find message after common log level patterns
    # Pattern: TIMESTAMP LEVEL LOGGER: MESSAGE
    for level in ['FATAL', 'ERROR', 'WARN', 'WARNING', 'INFO', 'DEBUG', 'TRACE']:
        if level in log_line:
            # Find the message after the logger/class name (after colon)
            parts = log_line.split(':', 1)
            if len(parts) > 1:
                message = parts[1].strip()
                # Remove common variable parts for better deduplication
                message = normalize_error_pattern(message)
                return message

    # Fallback: return the whole line stripped if no pattern matches
    return log_line.strip()


def extract_timestamp(log_line: str) -> Optional[str]:
    """
    Extract timestamp from log line.

    Supports common formats:
    - 25/10/08 06:23:27
    - 2025-10-08 06:23:27
    - [2025-10-08T06:23:27]

    Args:
        log_line: Full log line

    Returns:
        Extracted timestamp string or None
    """
    # Pattern 1: YY/MM/DD HH:MM:SS or YYYY-MM-DD HH:MM:SS
    match = re.match(r'^(\d{2,4}[/-]\d{2}[/-]\d{2}\s+\d{2}:\d{2}:\d{2})', log_line)
    if match:
        return match.group(1)

    # Pattern 2: [YYYY-MM-DDTHH:MM:SS]
    match = re.search(r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\]]*)\]', log_line)
    if match:
        return match.group(1)

    # Pattern 3: Timestamp at start (seconds since epoch or similar)
    match = re.match(r'^(\d{10,}\.\d+)s?\s', log_line)
    if match:
        return match.group(1)

    return None


def normalize_error_pattern(message: str) -> str:
    """
    Normalize error message by removing variable parts for better deduplication.

    Removes:
    - Executor IDs (executor 12 -> executor *)
    - Task IDs (task 123 -> task *)
    - Stage IDs (stage 5 -> stage *)
    - Memory addresses (0x7f8b...)
    - Thread IDs (Thread-123)

    Args:
        message: Error message to normalize

    Returns:
        Normalized message
    """
    # Replace executor IDs
    message = re.sub(r'\bexecutor\s+\d+\b', 'executor *', message, flags=re.IGNORECASE)

    # Replace task IDs
    message = re.sub(r'\btask\s+\d+\b', 'task *', message, flags=re.IGNORECASE)
    message = re.sub(r'\bTID\s+\d+\b', 'TID *', message, flags=re.IGNORECASE)

    # Replace stage IDs
    message = re.sub(r'\bstage\s+\d+\b', 'stage *', message, flags=re.IGNORECASE)

    # Replace partition IDs
    message = re.sub(r'\bpartition\s+\d+\b', 'partition *', message, flags=re.IGNORECASE)

    # Replace memory addresses
    message = re.sub(r'\b0x[0-9a-fA-F]+\b', '0x*', message)

    # Replace thread IDs
    message = re.sub(r'\bThread-\d+\b', 'Thread-*', message)

    return message


def add_evidence_to_map(
    evidence_map: Dict[str, EvidenceEntry],
    log_line: str,
    file_path: Optional[str] = None
) -> Dict[str, EvidenceEntry]:
    """
    Add a log line to the evidence map with deduplication.

    Args:
        evidence_map: Current evidence map
        log_line: Log line to add
        file_path: File path where this log line was found

    Returns:
        Updated evidence map
    """
    if not log_line or not log_line.strip():
        return evidence_map

    # Extract error pattern and timestamp
    error_pattern = extract_error_pattern(log_line)
    timestamp = extract_timestamp(log_line)

    if not error_pattern:
        return evidence_map

    # Initialize or update entry
    if error_pattern not in evidence_map:
        evidence_map[error_pattern] = {
            "count": 0,
            "timestamps": [],
            "files": [],
            "sample_lines": []
        }

    entry = evidence_map[error_pattern]

    # Update count
    entry["count"] += 1

    # Add timestamp if available
    if timestamp and timestamp not in entry["timestamps"]:
        entry["timestamps"].append(timestamp)

    # Add file path if available and not already present
    if file_path and file_path not in entry["files"]:
        entry["files"].append(file_path)

    # Add sample line (keep max 3 samples)
    if len(entry["sample_lines"]) < 3:
        if log_line not in entry["sample_lines"]:
            entry["sample_lines"].append(log_line)

    return evidence_map


def process_grep_results(
    evidence_map: Dict[str, EvidenceEntry],
    grep_output: str
) -> Dict[str, EvidenceEntry]:
    """
    Process grep tool output and add to evidence map.

    Handles both JSON array format from grep_tool and plain text.

    Args:
        evidence_map: Current evidence map
        grep_output: Output from grep_path_tool (JSON or plain text)

    Returns:
        Updated evidence map
    """
    try:
        # Try to parse as JSON (grep_tool output format)
        results = json.loads(grep_output)

        if isinstance(results, list):
            for result in results:
                if isinstance(result, dict):
                    log_line = result.get("line_text", "")
                    file_path = result.get("path")
                    evidence_map = add_evidence_to_map(evidence_map, log_line, file_path)

    except (json.JSONDecodeError, ValueError):
        # Fallback: treat as plain text (one log line per line)
        lines = grep_output.split('\n')
        for line in lines:
            if line.strip():
                evidence_map = add_evidence_to_map(evidence_map, line.strip())

    return evidence_map


def format_evidence_for_llm(evidence_map: Dict[str, EvidenceEntry], max_patterns: int = 50) -> str:
    """
    Format evidence map into a human-readable summary for LLM consumption.

    Args:
        evidence_map: Evidence map to format
        max_patterns: Maximum number of unique patterns to include

    Returns:
        Formatted string for LLM prompts
    """
    if not evidence_map:
        return "No evidence collected yet."

    # Sort by occurrence count (most frequent first)
    sorted_patterns = sorted(
        evidence_map.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )

    lines = [
        f"=== Evidence Summary ({len(evidence_map)} unique error patterns) ===\n"
    ]

    for idx, (pattern, entry) in enumerate(sorted_patterns[:max_patterns], 1):
        # Format timestamps
        ts_str = ", ".join(entry["timestamps"][:5])  # Show first 5 timestamps
        if len(entry["timestamps"]) > 5:
            ts_str += f" ... (+{len(entry['timestamps']) - 5} more)"

        # Format files
        files_str = ", ".join(entry["files"][:3])  # Show first 3 files
        if len(entry["files"]) > 3:
            files_str += f" ... (+{len(entry['files']) - 3} more)"

        lines.append(f"\n[{idx}] Error Pattern: {pattern}")
        lines.append(f"    Occurrences: {entry['count']}")
        if entry["timestamps"]:
            lines.append(f"    Timestamps: {ts_str}")
        if entry["files"]:
            lines.append(f"    Files: {files_str}")
        if entry["sample_lines"]:
            lines.append(f"    Sample: {entry['sample_lines'][0][:200]}...")

    if len(sorted_patterns) > max_patterns:
        lines.append(f"\n... and {len(sorted_patterns) - max_patterns} more error patterns")

    return "\n".join(lines)


def get_evidence_stats(evidence_map: Dict[str, EvidenceEntry]) -> Dict[str, int]:
    """
    Get statistics about the evidence map.

    Args:
        evidence_map: Evidence map to analyze

    Returns:
        Dictionary with stats (total_patterns, total_occurrences, etc.)
    """
    if not evidence_map:
        return {
            "total_unique_patterns": 0,
            "total_occurrences": 0,
            "total_files": 0,
            "avg_occurrences_per_pattern": 0
        }

    total_occurrences = sum(entry["count"] for entry in evidence_map.values())
    all_files = set()
    for entry in evidence_map.values():
        all_files.update(entry["files"])

    return {
        "total_unique_patterns": len(evidence_map),
        "total_occurrences": total_occurrences,
        "total_files": len(all_files),
        "avg_occurrences_per_pattern": total_occurrences // len(evidence_map) if evidence_map else 0
    }
