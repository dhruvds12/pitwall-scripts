"""
Datetime parsing, conversion, and bounding utilities for OpenF1 API.
"""

import datetime
from exceptions import OpenF1Error


def parse_iso_datetime(dt_str):
    """Parse an ISO 8601 datetime string, handling Z and offset suffixes."""
    if not dt_str:
        return None
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.datetime.fromisoformat(dt_str)


def parse_offset_to_timedelta(offset_str):
    """Parse string offsets like '5m', '30s', '1.5h' or float minutes to timedelta."""
    if not offset_str:
        return None

    # If it is a simple float or int, treat as minutes
    try:
        return datetime.timedelta(minutes=float(offset_str))
    except ValueError:
        pass

    offset_str = offset_str.strip().lower()
    if offset_str.endswith('s'):
        return datetime.timedelta(seconds=float(offset_str[:-1]))
    elif offset_str.endswith('m'):
        return datetime.timedelta(minutes=float(offset_str[:-1]))
    elif offset_str.endswith('h'):
        return datetime.timedelta(hours=float(offset_str[:-1]))
    else:
        raise OpenF1Error(
            f"Invalid offset format: '{offset_str}'. Use format like '30s', '5m', '1h', or float minutes."
        )


def format_api_datetime(dt):
    """Format a datetime object to UTC ISO string format expected by OpenF1 API (e.g. YYYY-MM-DDTHH:MM:SS.mmm)."""
    if not dt:
        return None
    # Ensure in UTC
    if dt.tzinfo:
        dt = dt.astimezone(datetime.timezone.utc)
    # Format to ISO format and trim to millisecond precision
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def resolve_time_bounds(session_start_str, start_time=None, end_time=None, start_offset=None, end_offset=None, limit_minutes=None):
    """Compute start and end datetime bounds based on absolute times and relative offsets."""
    session_start = parse_iso_datetime(session_start_str) if session_start_str else None

    resolved_start = None
    resolved_end = None

    # 1. Start time / offset
    if start_time:
        try:
            resolved_start = parse_iso_datetime(start_time)
        except Exception as e:
            raise OpenF1Error(f"Invalid --start-time format '{start_time}': {e}")
    elif start_offset:
        if not session_start:
            raise OpenF1Error("Cannot apply --start-offset because session start time is not available.")
        resolved_start = session_start + parse_offset_to_timedelta(start_offset)

    # 2. End time / offset / limit_minutes
    if end_time:
        try:
            resolved_end = parse_iso_datetime(end_time)
        except Exception as e:
            raise OpenF1Error(f"Invalid --end-time format '{end_time}': {e}")
    elif end_offset:
        if not session_start:
            raise OpenF1Error("Cannot apply --end-offset because session start time is not available.")
        resolved_end = session_start + parse_offset_to_timedelta(end_offset)
    elif limit_minutes is not None:
        base = resolved_start if resolved_start else session_start
        if not base:
            raise OpenF1Error("Cannot apply time limit/minutes because session start time is not available.")
        resolved_end = base + datetime.timedelta(minutes=limit_minutes)

    return resolved_start, resolved_end


def format_relative_time(date_str, session_start=None):
    """
    Format an ISO date string and calculate relative time offset from session start.
    Returns (rel_time_str, time_display_str).
    """
    rel_time = "N/A"
    time_display = date_str or "N/A"

    if date_str:
        try:
            dt = parse_iso_datetime(date_str)
            time_display = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            if session_start:
                diff = dt - session_start
                total_seconds = int(diff.total_seconds())
                is_neg = total_seconds < 0
                abs_seconds = abs(total_seconds)
                hours = abs_seconds // 3600
                minutes = (abs_seconds % 3600) // 60
                seconds = abs_seconds % 60
                prefix = "-" if is_neg else ""
                rel_time = f"{prefix}{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            pass

    return rel_time, time_display
