"""
ML Feature Extractor: extracts numerical features from parsed log events.
Only uses features that are actually present in the data.
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta


LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "UNKNOWN": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


def extract_features(log_events: List[dict]) -> Tuple[Optional[np.ndarray], List[str], str]:
    """
    Extract feature vector from a list of log event dicts.
    
    Returns:
        (feature_vector, feature_names, status_message)
        feature_vector is None if insufficient data.
    """
    if not log_events:
        return None, [], "No log events available for feature extraction"

    n = len(log_events)
    if n < 5:
        return None, [], f"Insufficient log events ({n}). Minimum 5 required."

    features = {}
    feature_names = []

    # 1. Level distribution
    levels = [e.get("level", "UNKNOWN") for e in log_events]
    level_counts = Counter(levels)
    total = max(n, 1)

    for lvl in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "UNKNOWN"]:
        key = f"ratio_{lvl.lower()}"
        features[key] = level_counts.get(lvl, 0) / total
        feature_names.append(key)

    # 2. Error/warning frequency
    features["error_rate"] = (level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)) / total
    feature_names.append("error_rate")

    features["warning_rate"] = level_counts.get("WARNING", 0) / total
    feature_names.append("warning_rate")

    # 3. Average severity score
    severity_scores = [LEVEL_ORDER.get(lvl, 1) for lvl in levels]
    features["mean_severity"] = float(np.mean(severity_scores))
    features["max_severity"] = float(np.max(severity_scores))
    feature_names.extend(["mean_severity", "max_severity"])

    # 4. Temporal features (only if timestamps available)
    timestamps = [
        e.get("timestamp") for e in log_events
        if e.get("timestamp") is not None
    ]

    if len(timestamps) >= 5:
        timestamps_sorted = sorted(timestamps)
        time_diffs = []
        for i in range(1, len(timestamps_sorted)):
            try:
                a = timestamps_sorted[i-1]
                b = timestamps_sorted[i]
                if hasattr(a, 'timestamp') and hasattr(b, 'timestamp'):
                    diff = abs((b.timestamp() - a.timestamp()))
                    time_diffs.append(diff)
            except Exception:
                pass

        if time_diffs:
            features["mean_event_interval_sec"] = float(np.mean(time_diffs))
            features["std_event_interval_sec"] = float(np.std(time_diffs))
            features["event_burst_ratio"] = sum(1 for d in time_diffs if d < 1.0) / max(len(time_diffs), 1)
        else:
            features["mean_event_interval_sec"] = 0.0
            features["std_event_interval_sec"] = 0.0
            features["event_burst_ratio"] = 0.0
        feature_names.extend(["mean_event_interval_sec", "std_event_interval_sec", "event_burst_ratio"])

        # Events in time windows
        if len(timestamps_sorted) >= 2:
            try:
                total_span = (timestamps_sorted[-1].timestamp() - timestamps_sorted[0].timestamp())
                first_quarter = total_span / 4
                first_quarter_boundary = timestamps_sorted[0].timestamp() + first_quarter

                errors_in_first_quarter = sum(
                    1 for e in log_events
                    if e.get("timestamp") and
                    e.get("timestamp").timestamp() <= first_quarter_boundary and
                    e.get("level") in ("ERROR", "CRITICAL")
                )
                errors_in_last_quarter = sum(
                    1 for e in log_events
                    if e.get("timestamp") and
                    e.get("timestamp").timestamp() > timestamps_sorted[-1].timestamp() - first_quarter and
                    e.get("level") in ("ERROR", "CRITICAL")
                )
                total_errors = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
                features["error_concentration_end"] = errors_in_last_quarter / max(total_errors, 1)
                feature_names.append("error_concentration_end")
            except Exception:
                pass

    # 5. Source diversity
    sources = [e.get("source") for e in log_events if e.get("source")]
    features["unique_sources_ratio"] = len(set(sources)) / max(len(sources), 1)
    feature_names.append("unique_sources_ratio")

    # 6. Message uniqueness (repeated messages may indicate loops)
    messages = [e.get("message", "")[:100] for e in log_events]
    msg_counts = Counter(messages)
    features["repeated_message_ratio"] = sum(1 for c in msg_counts.values() if c > 1) / max(len(msg_counts), 1)
    features["max_message_repeat"] = max(msg_counts.values()) / max(n, 1)
    feature_names.extend(["repeated_message_ratio", "max_message_repeat"])

    # 7. Log volume
    features["log_count_log10"] = float(np.log10(n + 1))
    feature_names.append("log_count_log10")

    # Build feature vector in consistent order
    vec = np.array([features[name] for name in feature_names], dtype=np.float64)

    # Replace NaN/Inf
    vec = np.nan_to_num(vec, nan=0.0, posinf=1.0, neginf=0.0)

    return vec, feature_names, f"Extracted {len(feature_names)} features from {n} log events"


def extract_features_batch(events_by_job: Dict[str, List[dict]]) -> Tuple[Optional[np.ndarray], List[str], str]:
    """
    Extract features from multiple ingestion jobs (for model training).
    Returns a 2D array of shape (n_jobs, n_features).
    """
    all_vecs = []
    feature_names = None

    for job_id, events in events_by_job.items():
        vec, names, _ = extract_features(events)
        if vec is not None:
            if feature_names is None:
                feature_names = names
            all_vecs.append(vec)

    if not all_vecs:
        return None, feature_names or [], "Insufficient data for batch feature extraction"

    return np.array(all_vecs), feature_names or [], f"Extracted features from {len(all_vecs)} log batches"
