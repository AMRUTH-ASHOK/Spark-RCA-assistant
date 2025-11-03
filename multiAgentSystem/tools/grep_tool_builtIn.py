"""
Built-in Grep Tool using system grep command via subprocess.

This tool provides faster file search capability by leveraging the native Unix grep
command instead of Python-based regex matching. It's significantly faster for large
files and directories, especially on Databricks where logs can be massive.

Key Differences from grep_tool.py:
1. Uses subprocess to call system grep command (much faster)
2. Simpler implementation - delegates complexity to battle-tested grep
3. Works in Databricks notebooks when called from Python cells
4. Better performance on large log files (10-100x faster)
5. More accurate pattern matching (uses grep's optimized engine)
"""

import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Union


def grep_path_tool_builtIn(
    target: Union[str, os.PathLike],
    pattern: Optional[str] = None,
    *,
    patterns: Optional[List[str]] = None,
    mode: str = "any",
    fixed: bool = False,
    ignore_case: bool = False,
    recursive: bool = True,
    include_hidden: bool = False,
    max_results: int = 10000,
    context_before: int = 0,
    context_after: int = 0,
    restrict_to_volumes: bool = True,
    timeout: int = 300
) -> str:
    """
    Search files using system grep command for better performance.
    
    Args:
        target: Path to search in (file or directory)
        pattern: Single search pattern
        patterns: Multiple search patterns (for AND/OR logic)
        mode: "any" for OR logic, "all" for AND logic
        fixed: If True, treat pattern as fixed string (grep -F)
        ignore_case: If True, case-insensitive search (grep -i)
        recursive: If True, search subdirectories (grep -r)
        include_hidden: If True, include hidden files
        max_results: Maximum number of results to return
        context_before: Lines of context before match (grep -B)
        context_after: Lines of context after match (grep -A)
        restrict_to_volumes: If True, only search within /Volumes/
        timeout: Command timeout in seconds
        
    Returns:
        JSON string with search results matching grep_tool.py format:
        [{"path": "...", "line_no": N, "line_text": "...", "spans": [[start, end], ...]}, ...]
    """
    # Security checks
    if restrict_to_volumes and not str(target).startswith("/Volumes/"):
        return json.dumps([], ensure_ascii=False)
    
    if ".." in str(target):
        return json.dumps([], ensure_ascii=False)
    
    # Validate target exists
    target_path = Path(target)
    if not target_path.exists():
        return json.dumps([], ensure_ascii=False)
    
    # Collect patterns
    pats: List[str] = []
    if pattern:
        pats.append(pattern)
    if patterns:
        pats.extend(patterns)
    
    if not pats:
        return json.dumps([], ensure_ascii=False)
    
    try:
        if mode.lower() == "any":
            # OR logic: combine patterns with grep -E
            grep_results = _grep_or_mode(
                target_path, pats, fixed, ignore_case, recursive, 
                include_hidden, context_before, context_after, timeout
            )
        else:
            # AND logic: pipe multiple greps
            grep_results = _grep_and_mode(
                target_path, pats, fixed, ignore_case, recursive,
                include_hidden, context_before, context_after, timeout
            )
        
        # Limit results
        if len(grep_results) > max_results:
            grep_results = grep_results[:max_results]
        
        print(f"Found {len(grep_results)} results")
        return json.dumps(grep_results, ensure_ascii=False)
    
    except subprocess.TimeoutExpired:
        print(f"Grep command timed out after {timeout} seconds")
        return json.dumps([], ensure_ascii=False)
    except Exception as e:
        print(f"Grep error: {e}")
        return json.dumps([], ensure_ascii=False)


def _grep_or_mode(
    target: Path,
    patterns: List[str],
    fixed: bool,
    ignore_case: bool,
    recursive: bool,
    include_hidden: bool,
    context_before: int,
    context_after: int,
    timeout: int
) -> List[Dict[str, Any]]:
    """Execute grep with OR logic (multiple patterns, any match)."""
    
    # Build grep command
    cmd = ["grep"]
    
    # Add flags
    if ignore_case:
        cmd.append("-i")
    if recursive and target.is_dir():
        cmd.append("-r")
    if not include_hidden:
        cmd.extend(["--exclude-dir=.*"])  # Exclude hidden directories
    if fixed:
        cmd.append("-F")  # Fixed string, not regex
    else:
        cmd.append("-E")  # Extended regex
    
    # Add context
    if context_before > 0:
        cmd.append(f"-B{context_before}")
    if context_after > 0:
        cmd.append(f"-A{context_after}")
    
    # Line numbers
    cmd.append("-n")
    
    # Combine patterns for OR logic
    if len(patterns) == 1:
        combined_pattern = patterns[0]
    else:
        # For OR: pattern1|pattern2|pattern3
        combined_pattern = "|".join(patterns)
    
    cmd.append(combined_pattern)
    cmd.append(str(target))
    
    # Execute grep
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    # Parse output
    return _parse_grep_output(result.stdout, patterns, ignore_case, fixed)


def _grep_and_mode(
    target: Path,
    patterns: List[str],
    fixed: bool,
    ignore_case: bool,
    recursive: bool,
    include_hidden: bool,
    context_before: int,
    context_after: int,
    timeout: int
) -> List[Dict[str, Any]]:
    """Execute grep with AND logic (multiple patterns, all must match)."""
    
    # For AND logic, we need to filter lines that match ALL patterns
    # Strategy: First grep gets all lines matching first pattern,
    # then we filter in Python for other patterns
    
    # Get results for first pattern
    first_results = _grep_or_mode(
        target, [patterns[0]], fixed, ignore_case, recursive,
        include_hidden, context_before, context_after, timeout
    )
    
    if len(patterns) == 1:
        return first_results
    
    # Filter for remaining patterns
    import re
    
    flags = re.IGNORECASE if ignore_case else 0
    remaining_patterns = [
        re.compile(re.escape(p) if fixed else p, flags) 
        for p in patterns[1:]
    ]
    
    filtered = []
    for item in first_results:
        line_text = item["line_text"]
        # Check if ALL remaining patterns match
        if all(rx.search(line_text) for rx in remaining_patterns):
            # Recalculate spans for all patterns
            all_spans = []
            for p in patterns:
                rx = re.compile(re.escape(p) if fixed else p, flags)
                all_spans.extend([m.span() for m in rx.finditer(line_text)])
            item["spans"] = all_spans
            filtered.append(item)
    
    return filtered


def _parse_grep_output(
    output: str,
    patterns: List[str],
    ignore_case: bool,
    fixed: bool
) -> List[Dict[str, Any]]:
    """Parse grep output into structured format matching grep_tool.py."""
    
    import re
    
    results = []
    if not output or not output.strip():
        return results
    
    # Compile patterns for span calculation
    flags = re.IGNORECASE if ignore_case else 0
    compiled_patterns = [
        re.compile(re.escape(p) if fixed else p, flags)
        for p in patterns
    ]
    
    for line in output.splitlines():
        if not line.strip():
            continue
        
        # Parse grep output format: filepath:line_number:line_text
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        
        filepath = parts[0]
        try:
            line_no = int(parts[1])
        except ValueError:
            continue
        
        line_text = parts[2]
        
        # Calculate spans (character positions of matches)
        spans = []
        for rx in compiled_patterns:
            spans.extend([m.span() for m in rx.finditer(line_text)])
        
        # Remove duplicate spans and sort
        spans = sorted(list(set(spans)))
        
        results.append({
            "path": filepath,
            "line_no": line_no,
            "line_text": line_text,
            "spans": spans
        })
    
    return results


# Alias for backward compatibility
grep_tool_builtIn = grep_path_tool_builtIn
