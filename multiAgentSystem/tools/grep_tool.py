"""
Grep Path Tool for searching files for patterns.

This tool provides a powerful file search capability for finding patterns in log files
and other text files. It supports multiple search patterns with AND/OR logic, and can
return detailed information about matches.
"""

import os
import re
import json
from pathlib import Path
from typing import List, Tuple, Union, Iterator, Optional, Sequence


def grep_path_tool(
    target: Union[str, os.PathLike],
    pattern: Optional[str] = None,                 # single pattern (legacy)
    *,
    patterns: Optional[Sequence[str]] = None,      # multiple patterns
    mode: str = "any",                             # "any" (OR) or "all" (AND)
    fixed: bool = False,
    ignore_case: bool = False,
    recursive: bool = True,
    include_hidden: bool = False,
    include_binary: bool = False,
    follow_symlinks: bool = False,
    restrict_to_volumes: bool = True,
    max_results: int = 1000,
    max_bytes_per_file: int = 64 * 1024 * 1024,
    return_which: bool = False                     # include which patterns matched per line
) -> str:
    """
    Search files under a path for one or more patterns.

    Args:
        target: Path to search in
        pattern: Single search pattern (legacy)
        patterns: Multiple search patterns
        mode: "any" for OR logic, "all" for AND logic
        fixed: If True, treat patterns as fixed strings, not regexes
        ignore_case: If True, perform case-insensitive search
        recursive: If True, search subdirectories
        include_hidden: If True, include hidden files and directories
        include_binary: If True, search binary files
        follow_symlinks: If True, follow symbolic links
        restrict_to_volumes: If True, only search within /Volumes/
        max_results: Maximum number of results to return
        max_bytes_per_file: Maximum file size to search
        return_which: If True, include which patterns matched each line

    Returns:
        JSON string with search results, each containing path, line_no, line_text, spans
    """
    def should_skip_path(p: Path) -> bool:
        if include_hidden: return False
        parts = p.parts
        if p.is_absolute():
            parts = [part for part in parts if part not in (p.anchor, "/", "\\")]
        return any(part.startswith(".") for part in parts if part not in (".", ".."))

    def iter_files(root: Path) -> Iterator[Path]:
        if root.is_file():
            if not should_skip_path(root): yield root
            return
        if root.is_dir():
            if should_skip_path(root): return
            if not recursive:
                for name in os.listdir(root):
                    f = root / name
                    if f.is_file() and (include_hidden or not name.startswith(".")): yield f
                return
            for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
                if not include_hidden:
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                dpath = Path(dirpath)
                for name in filenames:
                    if not include_hidden and name.startswith("."): continue
                    yield dpath / name

    def is_binary_file(p: Path, sniff_bytes: int = 4096) -> bool:
        try:
            with p.open("rb") as fh:
                return b"\x00" in fh.read(sniff_bytes)
        except Exception:
            return True

    def open_text_safely(p: Path):
        try:    return p.open("r", encoding="utf-8", errors="ignore")
        except: return p.open("r", encoding="latin-1", errors="ignore")

    # -------- pattern prep --------
    if restrict_to_volumes and not str(target).startswith("/Volumes/"):
        return json.dumps([], ensure_ascii=False)
    if ".." in str(target):
        return json.dumps([], ensure_ascii=False)

    pats: List[str] = []
    if pattern: pats.append(pattern)
    if patterns: pats.extend(list(patterns))
    if not pats:
        return json.dumps([], ensure_ascii=False)

    flags = re.MULTILINE | (re.IGNORECASE if ignore_case else 0)

    def _compile(p: str) -> re.Pattern:
        return re.compile(re.escape(p) if fixed else p, flags=flags)

    # compile list for AND checks or "which" reporting
    rx_list = []
    try:
        rx_list = [_compile(p) for p in pats]
    except re.error:
        return json.dumps([], ensure_ascii=False)

    # combined regex for fast ANY-span scanning
    if mode.lower() == "any":
        try:
            combined = "|".join(f"(?:{re.escape(p) if fixed else p})" for p in pats)
            rx_any = re.compile(combined, flags=flags)
        except re.error:
            return json.dumps([], ensure_ascii=False)
    else:
        rx_any = None  # not used in ALL mode

    results: List[dict] = []
    root = Path(target)

    for f in iter_files(root):
        try:
            if f.stat().st_size > max_bytes_per_file: continue
        except Exception:
            continue
        if not include_binary and is_binary_file(f): continue

        try:
            with open_text_safely(f) as fh:
                for idx, raw_line in enumerate(fh, start=1):
                    line = raw_line.rstrip("\n\r")

                    if mode.lower() == "any":
                        spans = [m.span() for m in rx_any.finditer(line)]
                        if spans:
                            record = {"path": str(f), "line_no": idx, "line_text": line, "spans": spans}
                            if return_which:
                                which = [p for p, rx in zip(pats, rx_list) if rx.search(line)]
                                record["which"] = which
                            results.append(record)
                    else:  # ALL
                        # Every pattern must match at least once
                        which = []
                        all_spans: List[Tuple[int,int]] = []
                        ok = True
                        for p, rx in zip(pats, rx_list):
                            ms = [m.span() for m in rx.finditer(line)]
                            if not ms:
                                ok = False
                                break
                            all_spans.extend(ms)
                            if return_which: which.append(p)
                        if ok:
                            record = {"path": str(f), "line_no": idx, "line_text": line, "spans": all_spans}
                            if return_which: record["which"] = which
                            results.append(record)

                    if len(results) >= max_results:
                        print(f"Found {len(results)} results")
                        return json.dumps(results, ensure_ascii=False)
        except Exception:
            continue

    print(f"Found {len(results)} results")
    return json.dumps(results, ensure_ascii=False)
