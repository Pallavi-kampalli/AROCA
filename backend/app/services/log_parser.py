"""
Log parser service: supports .log/.txt/.json/.jsonl/.csv formats.
Extracts timestamp, level, source, message, service, correlation_id.
"""
import re
import json
import csv
import io
import hashlib
from datetime import datetime, timezone
from typing import Iterator, Optional, Tuple
from app.db.models import LogLevel


TIMESTAMP_PATTERNS = [
    re.compile(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'),
    re.compile(r'(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})'),
    re.compile(r'(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})'),
]

LEVEL_PATTERNS = [
    re.compile(r'\b(CRITICAL|FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE|NOTICE)\b', re.IGNORECASE),
]

SOURCE_PATTERNS = [
    re.compile(r'\[([^\]]{1,100})\]'),
    re.compile(r'(\w[\w./-]{2,60}):\s'),
]

CORRELATION_PATTERNS = [
    re.compile(r'(?:traceId|trace_id|requestId|request_id|correlationId|correlation_id)[=: ]+([a-f0-9-]{8,64})', re.IGNORECASE),
]


def parse_timestamp(raw: str) -> Optional[datetime]:
    for pattern in TIMESTAMP_PATTERNS:
        m = pattern.search(raw)
        if m:
            ts_str = m.group(1)
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%d/%b/%Y:%H:%M:%S %z",
            ]:
                try:
                    dt = datetime.strptime(ts_str, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue
    return None


def parse_level(raw: str) -> LogLevel:
    for pattern in LEVEL_PATTERNS:
        m = pattern.search(raw)
        if m:
            lvl = m.group(1).upper()
            if lvl in ("CRITICAL", "FATAL"):
                return LogLevel.CRITICAL
            if lvl == "ERROR":
                return LogLevel.ERROR
            if lvl in ("WARN", "WARNING"):
                return LogLevel.WARNING
            if lvl == "INFO":
                return LogLevel.INFO
            if lvl in ("DEBUG", "TRACE"):
                return LogLevel.DEBUG
    return LogLevel.UNKNOWN


def parse_source(raw: str) -> Optional[str]:
    for pattern in SOURCE_PATTERNS:
        m = pattern.search(raw)
        if m:
            candidate = m.group(1).strip()
            if 2 <= len(candidate) <= 100:
                return candidate
    return None


def parse_correlation(raw: str) -> Optional[str]:
    for pattern in CORRELATION_PATTERNS:
        m = pattern.search(raw)
        if m:
            return m.group(1)
    return None


def error_signature_hash(message: str) -> str:
    normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27}', '<UUID>', message)
    normalized = re.sub(r'\d{10,}', '<ID>', normalized)
    normalized = re.sub(r'\d+\.\d+\.\d+\.\d+', '<IP>', normalized)
    return hashlib.sha256(normalized.encode()).hexdigest()


ParsedEvent = dict


def parse_plain_text(content: str) -> Iterator[Tuple[int, ParsedEvent]]:
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        event = {
            "line_number": i,
            "raw_line": line[:2000],
            "timestamp": parse_timestamp(line),
            "level": parse_level(line),
            "source": parse_source(line),
            "message": line.strip()[:2000],
            "correlation_id": parse_correlation(line),
        }
        yield i, event


def parse_json_lines(content: str) -> Iterator[Tuple[int, ParsedEvent]]:
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            ts_raw = (
                obj.get("timestamp") or obj.get("time") or obj.get("@timestamp")
                or obj.get("ts") or obj.get("date") or ""
            )
            ts = parse_timestamp(str(ts_raw)) if ts_raw else None
            level_raw = str(
                obj.get("level") or obj.get("severity") or obj.get("lvl") or ""
            )
            msg = str(
                obj.get("message") or obj.get("msg") or obj.get("log") or str(obj)
            )[:2000]
            event = {
                "line_number": i,
                "raw_line": line[:2000],
                "timestamp": ts,
                "level": parse_level(level_raw) if level_raw else LogLevel.UNKNOWN,
                "source": str(obj.get("logger") or obj.get("source") or obj.get("service") or "")[:200] or None,
                "message": msg,
                "correlation_id": str(obj.get("traceId") or obj.get("trace_id") or obj.get("requestId") or "")[:200] or None,
                "service_name": str(obj.get("service") or obj.get("app") or "")[:200] or None,
                "extra_fields": {k: v for k, v in obj.items() if k not in (
                    "timestamp", "time", "@timestamp", "ts", "date",
                    "level", "severity", "lvl", "message", "msg", "log",
                    "logger", "source", "service", "traceId", "trace_id", "requestId"
                )},
            }
            yield i, event
        except json.JSONDecodeError:
            yield i, {
                "line_number": i,
                "raw_line": line[:2000],
                "timestamp": None,
                "level": LogLevel.UNKNOWN,
                "source": None,
                "message": line[:2000],
                "correlation_id": None,
                "parse_error": "invalid JSON",
            }


def parse_csv(content: str) -> Iterator[Tuple[int, ParsedEvent]]:
    reader = csv.DictReader(io.StringIO(content))
    for i, row in enumerate(reader, 2):
        ts_raw = (
            row.get("timestamp") or row.get("time") or row.get("date") or
            row.get("Timestamp") or row.get("Time") or ""
        )
        ts = parse_timestamp(ts_raw) if ts_raw else None
        level_raw = row.get("level") or row.get("severity") or row.get("Level") or ""
        msg = (
            row.get("message") or row.get("msg") or row.get("Message") or
            str(row)
        )[:2000]
        event = {
            "line_number": i,
            "raw_line": str(row)[:2000],
            "timestamp": ts,
            "level": parse_level(level_raw),
            "source": (row.get("source") or row.get("logger") or row.get("Source") or "")[:200] or None,
            "message": msg,
            "correlation_id": (row.get("traceId") or row.get("correlation_id") or "")[:200] or None,
            "service_name": (row.get("service") or row.get("app") or "")[:200] or None,
        }
        yield i, event


def parse_file(content: str, filename: str) -> Iterator[Tuple[int, ParsedEvent]]:
    fname = filename.lower()
    if fname.endswith(".jsonl"):
        yield from parse_json_lines(content)
    elif fname.endswith(".json"):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for i, item in enumerate(data, 1):
                    line = json.dumps(item)
                    yield from parse_json_lines(line)
            else:
                yield from parse_json_lines(content)
        except json.JSONDecodeError:
            yield from parse_plain_text(content)
    elif fname.endswith(".csv"):
        yield from parse_csv(content)
    else:
        yield from parse_plain_text(content)
