"""
Output formatting and table generation utilities for OpenF1 data.
"""

from time_utils import format_relative_time


def print_table(headers, rows):
    """Print an aligned text table without external dependencies."""
    if not rows:
        print("No data available.")
        return

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))

    fmt = " | ".join(f"{{:<{w}}}" for w in widths)

    print(fmt.format(*headers))
    print("-+-".join("-" * w for w in widths))

    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def format_brake_status(brake_val):
    """Format brake value to 'On' or 'Off'."""
    if brake_val is True or (isinstance(brake_val, (int, float)) and brake_val > 0):
        return "On"
    return "Off"


def format_driver_display(driver_number, driver_info=None, driver_map=None):
    """Format driver acronym and number for display (e.g. 'HAM (#44)')."""
    if driver_info:
        acronym = driver_info.get("name_acronym", "???")
        num = driver_info.get("driver_number", driver_number)
        return f"{acronym} (#{num})"
    elif driver_map:
        d_info = driver_map.get(driver_number, {})
        acronym = d_info.get("name_acronym", "???")
        return f"{acronym} (#{driver_number})"
    return f"#{driver_number}"


def build_session_table_rows(sessions):
    """Build headers and rows for session listings."""
    headers = ["Session Name", "Session Type", "Start Time (Local/Track)", "Session Key"]
    rows = []
    for s in sessions:
        rows.append([
            s.get("session_name", "N/A"),
            s.get("session_type", "N/A"),
            s.get("date_start", "N/A"),
            s.get("session_key", "N/A")
        ])
    rows.sort(key=lambda x: x[2])
    return headers, rows


def build_position_table_rows(data_points, session_start, driver_info=None, driver_map=None):
    """Build headers and rows for position data."""
    if driver_info is not None:
        headers = ["Relative Time", "Timestamp (UTC)", "Position"]
        rows = []
        for pos in data_points:
            date_str = pos.get("date")
            position = pos.get("position")
            rel_time, time_display = format_relative_time(date_str, session_start)
            rows.append([rel_time, time_display, position])
        rows.sort(key=lambda x: x[1])
        return headers, rows
    else:
        headers = ["Relative Time", "Timestamp (UTC)", "Driver", "Position"]
        rows = []
        for pos in data_points:
            d_num = pos.get("driver_number")
            position = pos.get("position")
            date_str = pos.get("date")
            d_display = format_driver_display(d_num, driver_map=driver_map)
            rel_time, time_display = format_relative_time(date_str, session_start)
            rows.append([rel_time, time_display, d_display, position])
        rows.sort(key=lambda x: x[1])
        return headers, rows


def build_car_data_table_rows(data_points, session_start, driver_info=None, driver_map=None):
    """Build headers and rows for car telemetry data."""
    headers = ["Relative Time", "Timestamp (UTC)", "Driver", "Speed (km/h)", "RPM", "Gear", "Throttle (%)", "Brake", "DRS"]
    rows = []
    for sample in data_points:
        d_num = sample.get("driver_number")
        d_display = format_driver_display(d_num, driver_info=driver_info, driver_map=driver_map)

        date_str = sample.get("date")
        speed = sample.get("speed")
        rpm = sample.get("rpm")
        gear = sample.get("n_gear")
        throttle = sample.get("throttle")
        brake_val = sample.get("brake")
        drs = sample.get("drs")

        brake_display = format_brake_status(brake_val)
        rel_time, time_display = format_relative_time(date_str, session_start)

        rows.append([rel_time, time_display, d_display, speed, rpm, gear, throttle, brake_display, drs])

    rows.sort(key=lambda x: x[1])
    return headers, rows


def build_location_table_rows(data_points, session_start, driver_info=None, driver_map=None):
    """Build headers and rows for location GPS data."""
    headers = ["Relative Time", "Timestamp (UTC)", "Driver", "X (mm)", "Y (mm)", "Z (mm)"]
    rows = []
    for sample in data_points:
        d_num = sample.get("driver_number")
        d_display = format_driver_display(d_num, driver_info=driver_info, driver_map=driver_map)

        date_str = sample.get("date")
        x = sample.get("x")
        y = sample.get("y")
        z = sample.get("z")

        rel_time, time_display = format_relative_time(date_str, session_start)
        rows.append([rel_time, time_display, d_display, x, y, z])

    rows.sort(key=lambda x: x[1])
    return headers, rows
