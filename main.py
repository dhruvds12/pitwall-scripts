#!/usr/bin/env python3
"""
OpenF1 Telemetry & Session CLI.

This module serves as the primary entry point and facade, re-exporting components
from their respective modules for backward compatibility.
"""

import sys

# Re-export exceptions
from exceptions import (
    DriverNotFoundError,
    OpenF1Error,
    SessionCancelledError,
    SessionNotFoundError,
)

# Re-export configuration utilities
from config import load_env_file

# Re-export datetime utilities
from time_utils import (
    format_api_datetime,
    format_relative_time,
    parse_iso_datetime,
    parse_offset_to_timedelta,
    resolve_time_bounds,
)

# Re-export API client
from client import OpenF1Client

# Re-export output formatters
from formatters import (
    build_car_data_table_rows,
    build_location_table_rows,
    build_position_table_rows,
    build_session_table_rows,
    format_brake_status,
    format_driver_display,
    print_table,
)

# Re-export CLI workflow functions
from cli import (
    build_parser,
    fetch_driver_map_if_needed,
    fetch_mode_data,
    handle_car_data_mode,
    handle_location_mode,
    handle_position_mode,
    handle_session_mode,
    main,
    parse_args,
    resolve_session_and_driver,
)


if __name__ == "__main__":
    main()
