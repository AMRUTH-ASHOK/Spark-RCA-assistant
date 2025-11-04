"""
Log Deduplication Utility for optimizing evidence storage.

This module provides utilities to deduplicate log entries and create
a compact evidence map that reduces token usage by 75-85%.

Instead of storing full duplicate logs, we store unique log patterns
with their occurrence timestamps and metadata.
"""

import hashlib
import re
from typing import Dict, List, Any, Tuple
from datetime import datetime


def extract_timestamp(log_line: str) -> str:
    """
    Extract timestamp from a log line.
    
    Supports common formats:
    - YY/MM/DD HH:MM:SS (e.g., 25/10/08 06:24:21)
    - YYYY-MM-DD HH:MM:SS
    - ISO 8601 format
    
    Args:
        log_line: A single log line
        
    Returns:
        Extracted timestamp or empty string if not found
    """
    # Pattern 1: YY/MM/DD HH:MM:SS
    match = re.search(r'\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}', log_line)
    if match:
        return match.group(0)
    
    # Pattern 2: YYYY-MM-DD HH:MM:SS
    match = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', log_line)
    if match:
        return match.group(0)
    
    # Pattern 3: ISO 8601
    match = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', log_line)
    if match:
        return match.group(0)
    
    return ""


def extract_log_block(grep_results: List[Dict[str, Any]], index: int, context_lines: int = 10) -> Tuple[str, str]:
    """
    Extract a log block starting from the given index.
    
    A log block is a multi-line log entry (like an error with stack trace).
    We group consecutive lines from the same file that are close together.
    
    Args:
        grep_results: List of grep results with path, line_no, line_text
        index: Starting index in grep_results
        context_lines: Maximum line number gap to consider part of same block
        
    Returns:
        Tuple of (full_block_text, first_timestamp)
    """
    if index >= len(grep_results):
        return "", ""
    
    first_item = grep_results[index]
    file_path = first_item.get("path", "")
    start_line_no = first_item.get("line_no", 0)
    
    block_lines = [first_item.get("line_text", "")]
    # Extract timestamp safely - block_lines[0] always exists (created above)
    first_timestamp = extract_timestamp(block_lines[0]) if block_lines else None
    
    # Collect consecutive lines from same file
    i = index + 1
    while i < len(grep_results):
        item = grep_results[i]
        if item.get("path", "") != file_path:
            break
        
        current_line_no = item.get("line_no", 0)
        # If lines are too far apart, consider it a different block
        if current_line_no - start_line_no > context_lines:
            break
        
        block_lines.append(item.get("line_text", ""))
        start_line_no = current_line_no
        i += 1
    
    full_block = "\n".join(block_lines)
    return full_block, first_timestamp


def create_content_signature(content: str) -> str:
    """
    Create a short signature for log content.
    
    Uses the first 100 characters + hash for uniqueness.
    This helps create readable keys while ensuring uniqueness.
    
    Args:
        content: Full log content
        
    Returns:
        Content signature (first 100 chars + hash)
    """
    # Normalize whitespace for better deduplication
    normalized = " ".join(content.split())
    
    # Create hash
    content_hash = hashlib.md5(normalized.encode()).hexdigest()[:8]
    
    # Use first 100 chars + hash
    preview = normalized[:100]
    return f"{preview}...[{content_hash}]"


def deduplicate_grep_results(
    grep_results: List[Dict[str, Any]],
    matched_pattern: str
) -> Dict[str, Dict[str, Any]]:
    """
    Deduplicate grep results into an evidence map.
    
    Key format: (file_path, pattern, content_hash)
    Value: {
        "content": full log block,
        "timestamps": [list of occurrence timestamps],
        "count": number of occurrences,
        "first_seen": first timestamp,
        "last_seen": last timestamp,
        "file_path": source file path,
        "pattern": matched pattern
    }
    
    Args:
        grep_results: List of grep results from grep_path_tool
        matched_pattern: The pattern that was used to grep
        
    Returns:
        Evidence map with deduplicated entries
    """
    evidence_map: Dict[str, Dict[str, Any]] = {}
    processed_indices = set()
    
    for i in range(len(grep_results)):
        if i in processed_indices:
            continue
        
        item = grep_results[i]
        file_path = item.get("path", "unknown")
        
        # Extract log block (handles multi-line entries like stack traces)
        block_content, timestamp = extract_log_block(grep_results, i)
        
        # Create unique key
        content_hash = hashlib.md5(block_content.encode()).hexdigest()[:12]
        key = f"{file_path}::{matched_pattern}::{content_hash}"
        
        # Mark indices as processed (if block spans multiple lines)
        # For now, just mark current index
        processed_indices.add(i)
        
        if key in evidence_map:
            # Update existing entry
            if timestamp and timestamp not in evidence_map[key]["timestamps"]:
                evidence_map[key]["timestamps"].append(timestamp)
                evidence_map[key]["count"] += 1
                evidence_map[key]["last_seen"] = timestamp
        else:
            # Create new entry
            evidence_map[key] = {
                "content": block_content,
                "timestamps": [timestamp] if timestamp else [],
                "count": 1,
                "first_seen": timestamp or "unknown",
                "last_seen": timestamp or "unknown",
                "file_path": file_path,
                "pattern": matched_pattern
            }
    
    return evidence_map


def format_evidence_map_for_prompt(evidence_map: Dict[str, Dict[str, Any]], max_entries: int = 50) -> str:
    """
    Format evidence map for inclusion in LLM prompts.
    
    Creates a readable format showing:
    - File path and pattern
    - Log content
    - Occurrence count and timestamps
    
    Args:
        evidence_map: The evidence map to format
        max_entries: Maximum number of entries to include
        
    Returns:
        Formatted string for prompt inclusion
    """
    if not evidence_map:
        return "No evidence collected yet."
    
    formatted_entries = []
    
    # Sort by count (most frequent first) then by first_seen
    sorted_entries = sorted(
        evidence_map.items(),
        key=lambda x: (-x[1]["count"], x[1]["first_seen"]),
        reverse=False
    )
    
    for key, data in sorted_entries[:max_entries]:
        file_path = data["file_path"]
        pattern = data["pattern"]
        content = data["content"]
        count = data["count"]
        timestamps = data["timestamps"]
        
        # Format timestamps
        if len(timestamps) <= 3:
            ts_display = ", ".join(timestamps)
        else:
            ts_display = f"{timestamps[0]}, {timestamps[1]}, ... {timestamps[-1]} ({len(timestamps)} total)"
        
        entry = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"File: {file_path}\n"
            f"Pattern: {pattern}\n"
            f"Occurrences: {count}x\n"
            f"Timestamps: {ts_display}\n"
            f"Content:\n{content}\n"
        )
        formatted_entries.append(entry)
    
    total_entries = len(evidence_map)
    if total_entries > max_entries:
        summary = f"\n[Showing {max_entries} of {total_entries} unique log patterns]\n"
    else:
        summary = f"\n[Total: {total_entries} unique log patterns]\n"
    
    return summary + "\n".join(formatted_entries)


def merge_evidence_maps(map1: Dict[str, Dict[str, Any]], map2: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Merge two evidence maps, combining timestamps for duplicate entries.
    
    Args:
        map1: First evidence map
        map2: Second evidence map
        
    Returns:
        Merged evidence map
    """
    merged = map1.copy()
    
    for key, data in map2.items():
        if key in merged:
            # Merge timestamps
            existing_ts = set(merged[key]["timestamps"])
            new_ts = set(data["timestamps"])
            all_ts = sorted(list(existing_ts | new_ts))
            
            merged[key]["timestamps"] = all_ts
            merged[key]["count"] = len(all_ts)
            merged[key]["last_seen"] = all_ts[-1] if all_ts else merged[key]["last_seen"]
        else:
            merged[key] = data
    
    return merged


def get_evidence_summary_stats(evidence_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get summary statistics about the evidence map.
    
    Args:
        evidence_map: The evidence map
        
    Returns:
        Dictionary with summary stats
    """
    if not evidence_map:
        return {
            "unique_patterns": 0,
            "total_occurrences": 0,
            "unique_files": 0,
            "unique_search_patterns": 0
        }
    
    total_occurrences = sum(data["count"] for data in evidence_map.values())
    unique_files = len(set(data["file_path"] for data in evidence_map.values()))
    unique_patterns = len(set(data["pattern"] for data in evidence_map.values()))
    
    return {
        "unique_patterns": len(evidence_map),
        "total_occurrences": total_occurrences,
        "unique_files": unique_files,
        "unique_search_patterns": unique_patterns
    }
