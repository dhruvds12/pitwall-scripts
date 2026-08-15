"""
Command-line interface and workflow handlers for OpenF1 telemetry scripts.
"""

import argparse
import json
import sys

from client import OpenF1Client
from config import load_env_file
from exceptions import OpenF1Error
from formatters import (
    build_car_data_table_rows,
    build_location_table_rows,
    build_position_table_rows,
    build_session_table_rows,
    print_table,
)
from time_utils import parse_iso_datetime, resolve_time_bounds


def build_parser():
    """Build and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Retrieve and filter Formula 1 telemetry and position data from OpenF1 API."
    )
    # Mode selection
    parser.add_argument(
        "--mode",
        type=str,
        default="position",
        choices=["session", "position", "car-data", "location"],
        help="Data retrieval mode: session (metadata), position (default), car-data (telemetry), or location (GPS)"
    )

    # Session criteria
    parser.add_argument("--year", type=int, default=2026, help="Year of the session (e.g. 2026)")
    parser.add_argument("--track", type=str, required=True, help="Track location name, country or short name (e.g. Silverstone)")
    parser.add_argument("--session", type=str, default=None, help="Session name or type (e.g. 'Race', 'Practice 1'). Optional if mode is 'session'.")
    parser.add_argument("--driver", type=str, default=None, help="Driver name, acronym or number (e.g. Hamilton, HAM, 44)")

    # Time limits and offsets
    parser.add_argument("--start-offset", type=str, default=None, help="Start offset from session start (e.g. '5m', '30s', '1h')")
    parser.add_argument("--end-offset", type=str, default=None, help="End offset from session start (e.g. '10m', '1.5h')")
    parser.add_argument("--start-time", type=str, default=None, help="Absolute ISO 8601 start timestamp")
    parser.add_argument("--end-time", type=str, default=None, help="Absolute ISO 8601 end timestamp")
    parser.add_argument("--limit-minutes", type=float, default=None, help="Limit telemetry/position data duration in minutes from start")

    # Sampling and formatting
    parser.add_argument("--limit-samples", type=int, default=None, help="Limit output to a maximum number of data points")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data instead of a formatted table")
    parser.add_argument("--token", type=str, default=None, help="OpenF1 OAuth2 subscription token for live sessions")

    return parser


def parse_args(args=None):
    """Parse and validate command-line arguments."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.mode != "session" and parsed_args.session is None:
        parser.error(f"--session is required when --mode is '{parsed_args.mode}'")

    return parsed_args


def handle_session_mode(client, args):
    """Handle session metadata query mode."""
    if args.session:
        print(f"Searching for session '{args.session}' at '{args.track}' in {args.year}...", file=sys.stderr)
        session = client.get_session(args.year, args.track, args.session)
        if args.json:
            print(json.dumps(session, indent=2))
        else:
            print(f"Session Key: {session.get('session_key')}")
            print(f"Session Name: {session.get('session_name')}")
            print(f"Location:     {session.get('location')} ({session.get('country_name')})")
            print(f"Start Time:   {session.get('date_start')}")
    else:
        print(f"Searching for all sessions at '{args.track}' in {args.year}...", file=sys.stderr)
        sessions = client.get_sessions_at_track(args.year, args.track)
        if args.json:
            print(json.dumps(sessions, indent=2))
        else:
            headers, rows = build_session_table_rows(sessions)
            print(f"\nSessions at {sessions[0].get('location')} ({sessions[0].get('country_name')}) in {args.year}:")
            print_table(headers, rows)


def resolve_session_and_driver(client, args):
    """Resolve session details, driver info (if specified), and query time bounds."""
    print(f"Searching for session '{args.session}' at '{args.track}' in {args.year}...", file=sys.stderr)
    session = client.get_session(args.year, args.track, args.session)
    session_key = session["session_key"]
    session_start_str = session.get("date_start")
    print(f"Found session: {session.get('session_name')} at {session.get('location')} ({session.get('country_name')}) [Key: {session_key}]", file=sys.stderr)

    driver_number = None
    driver_info = None
    if args.driver:
        print(f"Searching for driver '{args.driver}' in this session...", file=sys.stderr)
        driver_info = client.get_driver(session_key, args.driver)
        driver_number = driver_info["driver_number"]
        print(f"Resolved driver: {driver_info.get('full_name')} (#{driver_number})", file=sys.stderr)

    resolved_start, resolved_end = resolve_time_bounds(
        session_start_str=session_start_str,
        start_time=args.start_time,
        end_time=args.end_time,
        start_offset=args.start_offset,
        end_offset=args.end_offset,
        limit_minutes=args.limit_minutes
    )

    return session, driver_info, driver_number, resolved_start, resolved_end


def fetch_driver_map_if_needed(client, session_key, driver_number):
    """Fetch all drivers in session to map numbers to acronyms when driver is not filtered."""
    if driver_number is None:
        print("Fetching driver details to map numbers to names...", file=sys.stderr)
        drivers = client._request("drivers", {"session_key": session_key})
        return {d["driver_number"]: d for d in drivers}
    return None


def fetch_mode_data(client, mode, session_key, driver_number, resolved_start, resolved_end):
    """Fetch requested dataset from OpenF1 API."""
    print(f"Fetching {mode} data...", file=sys.stderr)
    if mode == "position":
        return client.get_positions(
            session_key=session_key,
            driver_number=driver_number,
            start_time=resolved_start,
            end_time=resolved_end
        )
    elif mode == "car-data":
        return client.get_car_data(
            session_key=session_key,
            driver_number=driver_number,
            start_time=resolved_start,
            end_time=resolved_end
        )
    elif mode == "location":
        return client.get_location(
            session_key=session_key,
            driver_number=driver_number,
            start_time=resolved_start,
            end_time=resolved_end
        )
    return []


def handle_position_mode(client, session, driver_info, driver_number, data_points):
    """Format and display position tracking data."""
    if not data_points:
        print("No position updates found in the specified timeframe.")
        return

    session_start = parse_iso_datetime(session.get("date_start"))
    session_key = session["session_key"]

    if driver_number is not None:
        headers, rows = build_position_table_rows(data_points, session_start, driver_info=driver_info)
        print(f"\nPosition history for {driver_info.get('full_name')} (#{driver_number}) during {session.get('session_name')}:")
        print_table(headers, rows)
    else:
        driver_map = fetch_driver_map_if_needed(client, session_key, driver_number)
        headers, rows = build_position_table_rows(data_points, session_start, driver_map=driver_map)
        print(f"\nChronological position changes during {session.get('session_name')}:")
        print_table(headers, rows)


def handle_car_data_mode(client, session, driver_info, driver_number, data_points):
    """Format and display car telemetry data."""
    if not data_points:
        print("No car telemetry data found in the specified timeframe.")
        return

    session_start = parse_iso_datetime(session.get("date_start"))
    session_key = session["session_key"]
    driver_map = fetch_driver_map_if_needed(client, session_key, driver_number)

    headers, rows = build_car_data_table_rows(
        data_points,
        session_start,
        driver_info=driver_info,
        driver_map=driver_map
    )
    print(f"\nCar telemetry during {session.get('session_name')}:")
    print_table(headers, rows)


def handle_location_mode(client, session, driver_info, driver_number, data_points):
    """Format and display GPS location telemetry data."""
    if not data_points:
        print("No location data found in the specified timeframe.")
        return

    session_start = parse_iso_datetime(session.get("date_start"))
    session_key = session["session_key"]
    driver_map = fetch_driver_map_if_needed(client, session_key, driver_number)

    headers, rows = build_location_table_rows(
        data_points,
        session_start,
        driver_info=driver_info,
        driver_map=driver_map
    )
    print(f"\nGPS location data during {session.get('session_name')}:")
    print_table(headers, rows)


def main(args=None):
    """Entrypoint function for CLI execution."""
    load_env_file()
    parsed_args = parse_args(args)

    client = OpenF1Client(token=parsed_args.token)

    try:
        if parsed_args.mode == "session":
            handle_session_mode(client, parsed_args)
            return

        session, driver_info, driver_number, resolved_start, resolved_end = resolve_session_and_driver(
            client, parsed_args
        )

        data_points = fetch_mode_data(
            client,
            parsed_args.mode,
            session["session_key"],
            driver_number,
            resolved_start,
            resolved_end
        )

        if parsed_args.limit_samples is not None and parsed_args.limit_samples > 0:
            data_points = data_points[:parsed_args.limit_samples]

        if parsed_args.json:
            print(json.dumps(data_points, indent=2))
            return

        if parsed_args.mode == "position":
            handle_position_mode(client, session, driver_info, driver_number, data_points)
        elif parsed_args.mode == "car-data":
            handle_car_data_mode(client, session, driver_info, driver_number, data_points)
        elif parsed_args.mode == "location":
            handle_location_mode(client, session, driver_info, driver_number, data_points)

    except OpenF1Error as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
