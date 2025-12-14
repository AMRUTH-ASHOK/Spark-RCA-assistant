"""
GC Analyzer Tool for parsing and analyzing garbage collection logs.

This tool parses GC logs and provides structured analysis including:
- Summary statistics
- Top pause events
- Memory usage patterns
- Formatted tables for visualization

MLflow Tracing: This tool is decorated with @mlflow.trace for observability in Databricks.
"""

import re
import json
from typing import List, Dict, Any, Optional

from langchain_core.tools import tool

try:
    import mlflow
    from mlflow.entities import SpanType
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    # Define a no-op decorator if mlflow is not available
    def noop_decorator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])
    mlflow = type('obj', (object,), {'trace': noop_decorator})()


@mlflow.trace(span_type=SpanType.TOOL if MLFLOW_AVAILABLE else None, name="gc_analyzer_tool")
def GC_analyzer_tool(
    log_text: str,
    format: str = "markdown",
    max_rows: int = 200,
    min_duration_ms: float = 0.0,
    only_stw: bool = False,
    top_n: int = 10,
    sort_by: str = "timestamp",
) -> dict:
    """
    Analyzes Garbage Collection logs and provides structured insights.

    This tool is traceable via MLflow for observability in Databricks agent traces.

    Arguments:
      log_text: raw GC lines OR your grep output blob (with a JSON array of objects containing line_text,path,line_no).
      format: 'markdown' or 'plain'
      max_rows: maximum rows in main table
      min_duration_ms: keep events with duration >= this
      only_stw: keep only stop-the-world events (Pauses)
      top_n: rows for top tables
      sort_by: 'timestamp' | 'duration' | 'freed' | 'service_then_time'

    Returns:
      dict with: table, top_pauses_table, top_freed_table, summary, rows, stats
    """
    # ======================= Helpers (scoped) =======================
    _UNIT_TO_BYTES = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}

    def _parse_size_to_bytes(s: Optional[str]) -> int:
        if not s: 
            return -1
        s2 = s.strip().upper().replace(",", "")
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([KMGT])B?", s2)
        if not m:
            return int(s2) if re.fullmatch(r"\d+", s2) else -1
        return int(float(m.group(1)) * _UNIT_TO_BYTES[m.group(2)])

    def _bytes_to_mb(n: int) -> str:
        return f"{max(n,0)/(1024**2):.0f}MB" if n >= 0 else "?"

    def _pct(n: float) -> str:
        return f"{n*100:.1f}%" if n >= 0 else "?"

    def _parse_duration_ms(s: Optional[str]) -> float:
        if not s: return -1.0
        s2 = s.strip().lower().replace(",", "")
        if s2.endswith("ms"): return float(s2[:-2])
        if s2.endswith("s"):  return float(s2[:-1]) * 1000.0
        try: return float(s2)  # assume ms
        except: return -1.0

    def _q(p: float, xs: List[float]) -> float:
        if not xs: return -1.0
        xs2 = sorted(xs)
        k = p*(len(xs2)-1)
        lo, hi = int(k), min(int(k)+1, len(xs2)-1)
        w = k - lo
        return xs2[lo]*(1-w) + xs2[hi]*w

    def _nice_ms(ms: float) -> str:
        if ms < 0: return "?"
        if ms < 1000: return f"{ms:,.3f}ms"
        s3 = ms/1000.0
        return f"{s3:,.3f}s"

    # ======================= Input unwrapping =======================
    def _maybe_extract_json_array(text: str) -> Optional[List[dict]]:
        """
        Accepts:
          Found N hits
          '[{...,"line_text":"..."}, {...}]'
        Extracts and json.loads that array. Handles single/double quoted wrapper.
        """
        if '"line_text"' not in text and "'line_text'" not in text:
            return None
        i, j = text.find('['), text.rfind(']')
        if i == -1 or j == -1 or j <= i:
            return None
        blob = text[i:j+1].strip()
        # Remove a single leading/trailing quote if present
        if (blob.startswith("'") and blob.endswith("'")) or (blob.startswith('"') and blob.endswith('"')):
            blob = blob[1:-1]
        # Try direct loads
        try:
            return json.loads(blob)
        except Exception:
            # Many shells escape quotes; try unescaping
            try:
                blob2 = blob.replace('\\"', '"').replace("\\'", "'")
                return json.loads(blob2)
            except Exception:
                return None

    def _derive_service_from_path(path: Optional[str]) -> Optional[str]:
        if not path: return None
        m = re.search(r"service=([^/]+)", path)
        return m.group(1) if m else None

    # ======================= Regexes =======================
    # General shapes we support:
    # A) [ts] ... GC(N) ... <before>-><after>(<heap>) ... <dur>
    _RX_MEM_THEN_DUR = re.compile(
        r"(?P<ts>\d+(?:\.\d+)?)s.*?(?P<event>GC\((?P<id>\d+)\))"
        r"(?P<desc>.*?)"
        r"(?P<before>\d[\d,\.]*[KMGT])\s*->\s*(?P<after>\d[\d,\.]*[KMGT])\s*\(\s*(?P<heap>\d[\d,\.]*[KMGT])\s*\)"
        r".*?(?P<dur>\d[\d,\.]*\s*(?:ms|s))",
        flags=re.IGNORECASE
    )

    # B) [ts] ... GC(N) ... <dur> ... <before>-><after>(<heap>)
    _RX_DUR_THEN_MEM = re.compile(
        r"(?P<ts>\d+(?:\.\d+)?)s.*?(?P<event>GC\((?P<id>\d+)\))"
        r"(?P<desc>.*?)"
        r"(?P<dur>\d[\d,\.]*\s*(?:ms|s)).*?"
        r"(?P<before>\d[\d,\.]*[KMGT])\s*->\s*(?P<after>\d[\d,\.]*[KMGT])\s*\(\s*(?P<heap>\d[\d,\.]*[KMGT])\s*\)",
        flags=re.IGNORECASE
    )

    # C) [ts] ... GC(N) ... <dur>  (no mem triple)
    _RX_DUR_ONLY = re.compile(
        r"(?P<ts>\d+(?:\.\d+)?)s.*?(?P<event>GC\((?P<id>\d+)\))(?P<desc>.*?)(?P<dur>\d[\d,\.]*\s*(?:ms|s))",
        flags=re.IGNORECASE
    )

    def _classify_desc(desc: str) -> Dict[str, Any]:
        """
        Extracts class (pause_young, pause_full, remark, cleanup, concurrent, other),
        cause(s) inside parentheses, and a cleaned short kind string.
        """
        d = desc.strip()
        kind = "other"
        stw = False
        full = False

        # Normalize
        l = d.lower()
        if "pause young" in l:
            kind, stw = "pause_young", True
        elif "pause full" in l or "(full gc" in l or "pause full gc" in l:
            kind, stw, full = "pause_full", True, True
        elif "pause remark" in l:
            kind, stw = "remark", True
        elif "pause cleanup" in l:
            kind, stw = "cleanup", True
        elif "concurrent" in l:
            kind, stw = "concurrent", False
        # Pull cause strings in parentheses
        causes = re.findall(r"\(([^)]+)\)", d)
        cause = " | ".join(causes) if causes else None

        # Short printable kind
        if kind == "pause_young": short = "Young"
        elif kind == "pause_full": short = "Full"
        elif kind == "remark": short = "Remark"
        elif kind == "cleanup": short = "Cleanup"
        elif kind == "concurrent": short = "Concurrent"
        else: short = d.strip()[:32] or "Other"

        return {"kind": kind, "short": short, "stw": stw, "full": full, "cause": cause}

    def _match_gc(line: str) -> Optional[Dict[str, str]]:
        for rx in (_RX_MEM_THEN_DUR, _RX_DUR_THEN_MEM, _RX_DUR_ONLY):
            m = rx.search(line)
            if m: 
                return m.groupdict()
        return None

    # ======================= Core parse =======================
    def _parse_gc_rows(text: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        arr = _maybe_extract_json_array(text)
        items: List[Dict[str, Any]] = []
        if arr is not None:
            # Use grep JSON (preferred)
            for obj in arr:
                if not isinstance(obj, dict): 
                    continue
                items.append({
                    "line_text": obj.get("line_text",""),
                    "path": obj.get("path"),
                    "line_no": obj.get("line_no")
                })
        else:
            # Fall back to raw text
            for ln, line in enumerate(text.splitlines(), start=1):
                items.append({"line_text": line, "path": None, "line_no": ln})

        for it in items:
            line = it["line_text"]
            m = _match_gc(line)
            if not m:
                continue

            ts = float(m.get("ts")) if m.get("ts") else -1.0
            dur_ms = _parse_duration_ms(m.get("dur"))
            before_s, after_s, heap_s = m.get("before"), m.get("after"), m.get("heap")
            before_b = _parse_size_to_bytes(before_s)
            after_b  = _parse_size_to_bytes(after_s)
            heap_b   = _parse_size_to_bytes(heap_s)
            freed_b  = (before_b - after_b) if (before_b >= 0 and after_b >= 0) else -1
            freed_pct = (freed_b / heap_b) if (freed_b >= 0 and heap_b > 0) else -1.0

            desc_info = _classify_desc(m.get("desc",""))

            rows.append({
                "event": m.get("event"),
                "event_id": int(m.get("id")) if m.get("id") else None,
                "timestamp_s": ts,
                "duration_ms": dur_ms,
                "mem_before_str": before_s or "?",
                "mem_after_str":  after_s or "?",
                "heap_str":        heap_s or "?",
                "mem_before_bytes": before_b,
                "mem_after_bytes":  after_b,
                "heap_bytes":        heap_b,
                "freed_bytes":       freed_b,
                "freed_mb_str":      _bytes_to_mb(freed_b),
                "freed_pct":         freed_pct,
                "kind":              desc_info["kind"],
                "kind_short":        desc_info["short"],
                "stw":               desc_info["stw"],
                "full":              desc_info["full"],
                "cause":             desc_info["cause"],
                "path":              it.get("path"),
                "service":           _derive_service_from_path(it.get("path")),
                "line_no":           it.get("line_no")
            })

        # Sort by ts then event id when available
        rows.sort(key=lambda r: (r["service"] or "", r["timestamp_s"] if r["timestamp_s"] >= 0 else 0.0, r["event_id"] or 0))
        # Compute interval since previous, both global and per service
        last_ts_global: Optional[float] = None
        last_ts_by_service: Dict[str, float] = {}
        for r in rows:
            ts = r["timestamp_s"]
            svc = r.get("service") or "_"
            if last_ts_global is None or ts < 0:
                r["interval_prev_s"] = None
            else:
                r["interval_prev_s"] = ts - last_ts_global if ts >= 0 else None
            if svc not in last_ts_by_service or ts < 0:
                r["interval_prev_service_s"] = None
            else:
                r["interval_prev_service_s"] = ts - last_ts_by_service[svc] if ts >= 0 else None
            if ts >= 0:
                last_ts_global = ts
                last_ts_by_service[svc] = ts
        return rows

    # ======================= Rendering =======================
    def _render_main_table(rows: List[Dict[str, Any]], fmt: str, max_rows: int) -> str:
        header_md = (
            "| GC | Svc | Timestamp | Duration | Kind | Cause | Before→After | Heap | Freed | Freed % | Δprev(s) |\n"
            "|---|:---:|---:|---:|---|---|---:|---:|---:|---:|---:|"
        )
        out = [header_md]
        for r in rows[:max_rows]:
            ts = f"{r['timestamp_s']:.3f}s" if r["timestamp_s"] is not None and r["timestamp_s"] >= 0 else "?"
            dur = _nice_ms(r["duration_ms"])
            mem_ba = f"{r['mem_before_str']}→{r['mem_after_str']}"
            freed_pct = _pct(r["freed_pct"])
            delta = f"{r['interval_prev_service_s']:.3f}" if r.get("interval_prev_service_s") not in (None, -1) else ""
            out.append(
                f"| {r['event']} | {r.get('service') or ''} | {ts} | {dur} | {r['kind_short']} | "
                f"{(r['cause'] or '')} | {mem_ba} | {r['heap_str']} | {r['freed_mb_str']} | {freed_pct} | {delta} |"
            )
        if len(rows) > max_rows:
            out.append(f"\n_… {len(rows)-max_rows} more rows_")
        return "\n".join(out)

    def _render_top_table(rows: List[Dict[str, Any]], key: str, title: str, n: int) -> str:
        header = f"**{title} (top {n})**\n\n" + \
            "| GC | Svc | Timestamp | Duration | Before→After | Freed |\n|---|:---:|---:|---:|---:|---:|"
        out = [header]
        for r in rows[:n]:
            ts = f"{r['timestamp_s']:.3f}s" if r["timestamp_s"] is not None and r["timestamp_s"] >= 0 else "?"
            dur = _nice_ms(r["duration_ms"])
            mem_ba = f"{r['mem_before_str']}→{r['mem_after_str']}"
            out.append(f"| {r['event']} | {r.get('service') or ''} | {ts} | {dur} | {mem_ba} | {r['freed_mb_str']} |")
        return "\n".join(out)

    def _compute_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        stw = [r for r in rows if r.get("stw")]
        durs = [r["duration_ms"] for r in stw if r["duration_ms"] >= 0]
        freed = [r["freed_bytes"] for r in rows if r["freed_bytes"] >= 0]
        fulls = [r for r in rows if r.get("full")]
        youngs = [r for r in rows if r.get("kind") == "pause_young"]
        remarks = [r for r in rows if r.get("kind") == "remark"]
        cleanups = [r for r in rows if r.get("kind") == "cleanup"]
        conc = [r for r in rows if r.get("kind") == "concurrent"]

        total_pause_ms = sum(durs) if durs else 0.0
        out = {
            "total_events": len(rows),
            "stw_events": len(stw),
            "concurrent_events": len(conc),
            "young_gc": len(youngs),
            "full_gc": len(fulls),
            "remark": len(remarks),
            "cleanup": len(cleanups),
            "total_stw_pause_ms": total_pause_ms,
            "avg_pause_ms": (sum(durs)/len(durs)) if durs else -1,
            "p50_pause_ms": _q(0.50, durs),
            "p95_pause_ms": _q(0.95, durs),
            "p99_pause_ms": _q(0.99, durs),
            "total_freed_mb": (sum(freed)/(1024**2)) if freed else 0.0,
            "max_freed_mb": (max(freed)/(1024**2)) if freed else -1,
            "max_pause_ms": max(durs) if durs else -1,
        }
        # Estimate overall observation window
        ts = [r["timestamp_s"] for r in rows if r["timestamp_s"] is not None and r["timestamp_s"] >= 0]
        if len(ts) >= 2:
            span_s = max(ts) - min(ts)
            out["observed_span_s"] = span_s
            out["events_per_min"] = (len(rows) / span_s * 60.0) if span_s > 0 else -1
        else:
            out["observed_span_s"] = -1
            out["events_per_min"] = -1
        return out

    def _render_summary(stats: Dict[str, Any]) -> str:
        def val(k, unit=""):
            v = stats.get(k, -1)
            if v == -1 or v is None:
                return "?"
            if unit == "ms":
                return _nice_ms(v)
            if unit == "mb":
                return f"{v:,.0f}MB"
            if unit == "s":
                return f"{v:,.3f}s"
            if unit == "rate":
                return f"{v:.2f}/min" if v >= 0 else "?"
            return f"{v:,}"
        return (
            f"**Events:** {val('total_events')}  •  **STW:** {val('stw_events')}  •  **Concurrent:** {val('concurrent_events')}  •  "
            f"**Young:** {val('young_gc')}  •  **Full:** {val('full_gc')}  •  **Remark:** {val('remark')}  •  **Cleanup:** {val('cleanup')}\n\n"
            f"**Total STW pause:** {val('total_stw_pause_ms','ms')}  •  "
            f"**p50/p95/p99:** {val('p50_pause_ms','ms')} / {val('p95_pause_ms','ms')} / {val('p99_pause_ms','ms')}\n\n"
            f"**Total freed:** {val('total_freed_mb','mb')}  •  **Max freed:** {val('max_freed_mb','mb')}  •  "
            f"**Max pause:** {val('max_pause_ms','ms')}\n\n"
            f"**Observed window:** {val('observed_span_s','s')}  •  **Event rate:** {val('events_per_min','rate')}"
        )

    def _extract_executor_ip(path: Optional[str]) -> Optional[str]:
        """Extract executor IP from file path like executor-10.139.127.191.log"""
        if not path:
            return None
        m = re.search(r"executor-([\d\.]+)", path)
        return m.group(1) if m else None

    def _determine_gc_health(full_gc_count: int, max_duration_ms: float, max_heap_used_pct: float) -> Dict[str, Any]:
        """Determine GC health status based on metrics"""
        issues = []
        
        # Check Full GC frequency
        if full_gc_count >= 15:
            issues.append("Excessive Full GCs")
            severity = "⚠️ Heavy GC activity"
        elif full_gc_count >= 5:
            issues.append("High Full GC count")
            severity = "⚠️ Moderate GC activity"
        else:
            severity = "✅ Healthy"
        
        # Check pause duration
        if max_duration_ms >= 1000:
            issues.append(f"Long pause ({max_duration_ms/1000:.2f}s)")
            severity = "⚠️ Heavy GC activity" if severity == "✅ Healthy" else severity
        
        # Check heap utilization
        if max_heap_used_pct >= 90:
            issues.append(f"High heap pressure ({max_heap_used_pct:.0f}%)")
            severity = "⚠️ Heavy GC activity" if severity == "✅ Healthy" else severity
        
        return {
            "status": severity,
            "issues": issues
        }

    def _aggregate_by_executor(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Aggregate GC events by executor IP"""
        by_executor: Dict[str, List[Dict[str, Any]]] = {}
        
        for r in rows:
            executor_ip = _extract_executor_ip(r.get("path"))
            if not executor_ip:
                executor_ip = "driver" if "driver" in str(r.get("path", "")).lower() else "unknown"
            
            if executor_ip not in by_executor:
                by_executor[executor_ip] = []
            by_executor[executor_ip].append(r)
        
        aggregated = {}
        for executor_ip, events in by_executor.items():
            full_gcs = [e for e in events if e.get("full")]
            durations = [e["duration_ms"] for e in events if e["duration_ms"] >= 0]
            heap_used = []
            
            # Calculate heap % used from after_bytes / heap_bytes
            for e in events:
                if e["heap_bytes"] > 0 and e["mem_after_bytes"] >= 0:
                    heap_used.append(e["mem_after_bytes"] / e["heap_bytes"] * 100)
            
            max_heap_pct = max(heap_used) if heap_used else 0.0
            max_duration = max(durations) if durations else 0.0
            full_gc_count = len(full_gcs)
            
            health = _determine_gc_health(full_gc_count, max_duration, max_heap_pct)
            
            aggregated[executor_ip] = {
                "executor_ip": executor_ip,
                "total_events": len(events),
                "full_gc_count": full_gc_count,
                "young_gc_count": len([e for e in events if e.get("kind") == "pause_young"]),
                "max_duration_ms": max_duration,
                "max_duration_sec": max_duration / 1000.0 if max_duration > 0 else 0.0,
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0,
                "max_heap_used_pct": max_heap_pct,
                "max_heap_used_bytes": max([e["mem_after_bytes"] for e in events if e["mem_after_bytes"] >= 0], default=0),
                "health_status": health["status"],
                "health_issues": health["issues"]
            }
        
        return aggregated

    def _render_driver_gc_table(rows: List[Dict[str, Any]], max_rows: int = 50) -> str:
        """Render detailed driver GC events table"""
        driver_events = [r for r in rows if "driver" in str(r.get("path", "")).lower()]
        
        if not driver_events:
            return "_No driver GC events found_"
        
        header = (
            "**Driver GC Events**\n\n"
            "| Timestamp | GC Type | Duration | Before GC | After GC | Reclaimed | Heap % Used |\n"
            "|---:|---|---:|---:|---:|---:|---:|"
        )
        
        lines = [header]
        for r in driver_events[:max_rows]:
            ts = f"{r['timestamp_s']:.0f}s" if r["timestamp_s"] >= 0 else "?"
            gc_type = "Full GC" if r.get("full") else r.get("kind_short", "GC")
            duration = f"{r['duration_ms']/1000:.2f}" if r["duration_ms"] >= 0 else "?"
            before = r["mem_before_str"]
            after = r["mem_after_str"]
            reclaimed = r["freed_mb_str"]
            
            # Calculate heap % used
            heap_pct = "?"
            if r["heap_bytes"] > 0 and r["mem_after_bytes"] >= 0:
                heap_pct = f"{(r['mem_after_bytes'] / r['heap_bytes'] * 100):.0f}%"
            
            lines.append(f"| {ts} | {gc_type} | {duration} | {before} | {after} | {reclaimed} | {heap_pct} |")
        
        if len(driver_events) > max_rows:
            lines.append(f"\n_... {len(driver_events) - max_rows} more events_")
        
        return "\n".join(lines)

    def _render_executor_summary_table(aggregated: Dict[str, Dict[str, Any]]) -> str:
        """Render executor-level GC summary table"""
        if not aggregated:
            return "_No executor GC events found_"
        
        # Separate driver from executors
        executors = {k: v for k, v in aggregated.items() if k != "driver" and k != "unknown"}
        
        if not executors:
            return "_No executor GC events found_"
        
        header = (
            "**Executor GC Summary**\n\n"
            "| Executor IP | Total Full GCs | Max GC Duration | Max Heap Used | GC Status |\n"
            "|---|---:|---:|---:|---|"
        )
        
        lines = [header]
        # Sort by full_gc_count descending
        sorted_executors = sorted(executors.items(), key=lambda x: x[1]["full_gc_count"], reverse=True)
        
        for executor_ip, stats in sorted_executors:
            full_gcs = f"{stats['full_gc_count']}+" if stats['full_gc_count'] >= 15 else str(stats['full_gc_count'])
            max_duration = f"{stats['max_duration_sec']:.2f} sec" if stats['max_duration_sec'] > 0 else "?"
            max_heap = _bytes_to_mb(stats['max_heap_used_bytes'])
            status = stats['health_status']
            
            lines.append(f"| {executor_ip} | {full_gcs} | {max_duration} | {max_heap} | {status} |")
        
        return "\n".join(lines)

    def _extract_gc_config(text: str) -> Dict[str, str]:
        """Extract GC configuration from logs"""
        config = {}
        
        # Try to find heap size settings
        heap_match = re.search(r"-Xmx([\d\.]+)([GMK])", text)
        if heap_match:
            value = float(heap_match.group(1))
            unit = heap_match.group(2)
            if unit == "G":
                config["Max Heap Size"] = f"{value} GB (-Xmx{heap_match.group(1)}{unit})"
            elif unit == "M":
                config["Max Heap Size"] = f"{value/1024:.1f} GB (-Xmx{heap_match.group(1)}{unit})"
        
        # Try to infer from GC events
        if not config.get("Max Heap Size"):
            heap_sizes = re.findall(r"\((\d+(?:\.\d+)?[KMGT])\)", text)
            if heap_sizes:
                # Parse largest heap size seen
                max_heap = 0
                for hs in heap_sizes:
                    bytes_val = _parse_size_to_bytes(hs)
                    if bytes_val > max_heap:
                        max_heap = bytes_val
                if max_heap > 0:
                    config["Max Heap Size"] = f"{max_heap/(1024**3):.1f} GB (~observed)"
        
        # Look for GC algorithm mentions
        if "G1" in text or "G1GC" in text:
            config["GC Algorithm"] = "G1 Garbage Collector"
        elif "ParallelGC" in text or "PSYoungGen" in text:
            config["GC Algorithm"] = "Parallel GC"
        elif "CMS" in text:
            config["GC Algorithm"] = "Concurrent Mark Sweep (CMS)"
        
        return config

    def _render_gc_config(config: Dict[str, str]) -> str:
        """Render GC configuration table"""
        if not config:
            return "_GC configuration not detected in logs_"
        
        header = "**GC Configuration**\n\n| Parameter | Value |\n|---|---|"
        lines = [header]
        
        for param, value in config.items():
            lines.append(f"| {param} | {value} |")
        
        return "\n".join(lines)

    # ======================= Pipeline =======================
    rows = _parse_gc_rows(log_text or "")

    # Filters
    if min_duration_ms and min_duration_ms > 0:
        rows = [r for r in rows if r["duration_ms"] >= 0 and r["duration_ms"] >= min_duration_ms]
    if only_stw:
        rows = [r for r in rows if r.get("stw")]

    # Sort
    if sort_by == "duration":
        rows.sort(key=lambda r: (-(r["duration_ms"] if r["duration_ms"] >= 0 else -1)))
    elif sort_by == "freed":
        rows.sort(key=lambda r: (-(r["freed_bytes"] if r["freed_bytes"] >= 0 else -1)))
    elif sort_by == "service_then_time":
        rows.sort(key=lambda r: (r.get("service") or "", r["timestamp_s"] if r["timestamp_s"] >= 0 else 0.0))
    else:
        rows.sort(key=lambda r: (r["timestamp_s"] if r["timestamp_s"] >= 0 else 0.0))

    # Stats & summaries computed on the *filtered* set
    stats = _compute_stats(rows)

    # Executor aggregation
    executor_aggregated = _aggregate_by_executor(rows)

    # Tables
    table = _render_main_table(rows, format, max_rows)
    driver_gc_table = _render_driver_gc_table(rows, max_rows=50)
    executor_summary_table = _render_executor_summary_table(executor_aggregated)
    
    top_by_dur = sorted(rows, key=lambda r: (r["duration_ms"] if r["duration_ms"] >= 0 else -1), reverse=True)
    top_by_freed = sorted(rows, key=lambda r: (r["freed_bytes"] if r["freed_bytes"] >= 0 else -1), reverse=True)

    top_pauses_table = _render_top_table(top_by_dur, "duration_ms", "Longest pauses", top_n)
    top_freed_table = _render_top_table(top_by_freed, "freed_bytes", "Largest frees", top_n)
    summary = _render_summary(stats)
    
    # Extract GC configuration
    gc_config = _extract_gc_config(log_text or "")
    gc_config_table = _render_gc_config(gc_config)

    return {
        "table": table,
        "driver_gc_table": driver_gc_table,
        "executor_summary_table": executor_summary_table,
        "top_pauses_table": top_pauses_table,
        "top_freed_table": top_freed_table,
        "summary": summary,
        "gc_config_table": gc_config_table,
        "executor_aggregated": executor_aggregated,
        "rows": rows,
        "stats": stats
    }


# LangChain tool wrapper for use with ReAct agents
@tool
def analyze_gc_logs_tool(log_text: str) -> str:
    """
    Analyze Garbage Collection (GC) logs for memory-related issues.
    
    Use this tool when investigating memory problems, OOM errors, or GC overhead issues.
    This tool parses GC log output and provides statistics about pause times, memory freed,
    and identifies problematic GC events with executor-level aggregation.
    
    Args:
        log_text: Raw GC log text OR grep output (JSON array with line_text fields).
                  Can be the direct output from grep_logs_tool when searching for GC patterns.
    
    Returns:
        JSON string with GC analysis including:
        - summary: Overview statistics (total events, pause times, memory freed)
        - driver_gc_table: Detailed driver GC events with duration, heap usage, reclaimed memory
        - executor_summary_table: Executor-level aggregation with health status
        - gc_config_table: Detected GC configuration parameters
        - top_pauses_table: Longest pause events (potential performance issues)
        - stats: Detailed statistics (p50/p95/p99 pause times, event counts)
        - executor_details: Per-executor metrics for programmatic access
    
    Examples:
        - Use after grep_logs_tool finds GC-related entries
        - Analyze when keywords contain: GC, heap, memory, OOM, pause
    """
    result = GC_analyzer_tool(
        log_text=log_text,
        format="markdown",
        max_rows=100,
        top_n=10,
        sort_by="duration"
    )
    
    # Return comprehensive analysis for the agent
    return json.dumps({
        "summary": result.get("summary", ""),
        "driver_gc_table": result.get("driver_gc_table", ""),
        "executor_summary_table": result.get("executor_summary_table", ""),
        "gc_config_table": result.get("gc_config_table", ""),
        "top_pauses_table": result.get("top_pauses_table", ""),
        "stats": result.get("stats", {}),
        "executor_details": result.get("executor_aggregated", {}),
        "total_events": result.get("stats", {}).get("total_events", 0)
    }, indent=2)
