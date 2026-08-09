import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

class OpenF1Error(Exception):
    """Base exception class for OpenF1 operations."""
    pass

class SessionNotFoundError(OpenF1Error):
    """Raised when a requested session cannot be found."""
    pass

class SessionCancelledError(OpenF1Error):
    """Raised when a requested session was cancelled."""
    pass

class DriverNotFoundError(OpenF1Error):
    """Raised when a driver cannot be found in a session."""
    pass

def load_env_file(filepath=".env"):
    """Load key-value pairs from a local .env file into os.environ."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    val = val.strip().strip("'\"")
                    key = key.strip()
                    if key:
                        os.environ[key] = val
        except Exception as e:
            print(f"Warning: Failed to read {filepath}: {e}", file=sys.stderr)

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

class OpenF1Client:
    BASE_URL = "https://api.openf1.org/v1"

    def __init__(self, token=None):
        self.token = token or os.environ.get("OPENF1_TOKEN")

    def _request(self, endpoint, params=None):
        """Helper to make a GET request to the OpenF1 API."""
        url = f"{self.BASE_URL}/{endpoint}"
        if params:
            # Filter out None values and convert all to strings
            clean_params = {k: str(v) for k, v in params.items() if v is not None}
            if clean_params:
                url += "?" + urllib.parse.urlencode(clean_params)
        
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if self.token:
            token_str = self.token.strip()
            if not token_str.lower().startswith("bearer "):
                token_str = f"Bearer {token_str}"
            req.add_header("Authorization", token_str)
        
        retries = 3
        backoff = 1.0
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:  # Rate limit
                    if attempt < retries - 1:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                elif e.code == 404:
                    # Check if response payload contains the 'no results' error details
                    try:
                        body = e.read().decode("utf-8")
                        data = json.loads(body)
                        if isinstance(data, dict) and "detail" in data:
                            return []
                    except Exception:
                        pass
                    return []
                
                # Try to parse a detailed error message from response body
                try:
                    body = e.read().decode("utf-8")
                    data = json.loads(body)
                    if isinstance(data, dict) and "detail" in data:
                        raise OpenF1Error(f"HTTP error {e.code}: {data['detail']}")
                except Exception as parse_err:
                    if isinstance(parse_err, OpenF1Error):
                        raise parse_err
                raise OpenF1Error(f"HTTP error {e.code}: {e.reason}")
            except urllib.error.URLError as e:
                raise OpenF1Error(f"Failed to connect to API: {e.reason}")
        raise OpenF1Error("Exceeded max retries for rate-limited requests.")

    def get_sessions_at_track(self, year, track_search):
        """Retrieve all sessions for a given year and track."""
        sessions = self._request("sessions", {"year": year})
        if not sessions:
            raise SessionNotFoundError(f"No sessions found for year {year}.")

        track_search_lower = track_search.lower()
        matching_sessions = []
        for s in sessions:
            loc = s.get("location") or ""
            country = s.get("country_name") or ""
            circuit = s.get("circuit_short_name") or ""
            if (track_search_lower in loc.lower() or 
                track_search_lower in country.lower() or 
                track_search_lower in circuit.lower()):
                matching_sessions.append(s)
                
        if not matching_sessions:
            available_tracks = sorted(list(set(
                s.get("location") for s in sessions if s.get("location")
            )))
            raise SessionNotFoundError(
                f"No track matching '{track_search}' found in year {year}.\n"
                f"Available tracks in {year}: {', '.join(available_tracks)}"
            )
            
        return matching_sessions

    def get_session(self, year, track_search, session_name_search):
        """Find a session matching year, track, and session name."""
        matching_sessions = self.get_sessions_at_track(year, track_search)

        session_search_lower = session_name_search.lower()
        final_sessions = []
        for s in matching_sessions:
            s_name = s.get("session_name") or ""
            s_type = s.get("session_type") or ""
            if (session_search_lower in s_name.lower() or 
                session_search_lower in s_type.lower()):
                final_sessions.append(s)

        if not final_sessions:
            available_sessions = sorted(list(set(
                s.get("session_name") for s in matching_sessions if s.get("session_name")
            )))
            raise SessionNotFoundError(
                f"Session '{session_name_search}' not found at '{track_search}' in {year}.\n"
                f"Available sessions for this Grand Prix: {', '.join(available_sessions)}"
            )

        # Disambiguate if multiple match; prefer exact match if possible
        exact_matches = [s for s in final_sessions if s.get("session_name").lower() == session_search_lower]
        session = exact_matches[0] if exact_matches else final_sessions[0]

        if session.get("is_cancelled"):
            raise SessionCancelledError(
                f"Session '{session.get('session_name')}' at '{track_search}' in {year} was cancelled."
            )

        return session

    def get_driver(self, session_key, driver_search):
        """Identify a driver by name, acronym, or number in a specific session."""
        drivers = self._request("drivers", {"session_key": session_key})
        if not drivers:
            raise DriverNotFoundError(f"No drivers found for session {session_key}.")

        driver_search_str = str(driver_search).strip().lower()
        
        matching_drivers = []
        for d in drivers:
            d_number = str(d.get("driver_number"))
            acronym = (d.get("name_acronym") or "").lower()
            full_name = (d.get("full_name") or "").lower()
            first_name = (d.get("first_name") or "").lower()
            last_name = (d.get("last_name") or "").lower()
            
            if (driver_search_str == d_number or
                driver_search_str == acronym or
                driver_search_str == last_name or
                driver_search_str == first_name or
                driver_search_str in full_name):
                matching_drivers.append(d)

        if not matching_drivers:
            available = [f"{d.get('name_acronym')} (#{d.get('driver_number')})" for d in drivers if d.get("name_acronym")]
            raise DriverNotFoundError(
                f"Driver '{driver_search}' not found in this session.\n"
                f"Available drivers in this session: {', '.join(sorted(available))}"
            )
            
        if len(matching_drivers) > 1:
            # dis-ambiguate exact matches on acronym or last name
            exact_acronym = [d for d in matching_drivers if (d.get("name_acronym") or "").lower() == driver_search_str]
            if len(exact_acronym) == 1:
                return exact_acronym[0]
            exact_last = [d for d in matching_drivers if (d.get("last_name") or "").lower() == driver_search_str]
            if len(exact_last) == 1:
                return exact_last[0]
                
        return matching_drivers[0]

    def get_positions(self, session_key, driver_number=None, start_time=None, end_time=None):
        """Retrieve positions, filtering by date bounds on the server side."""
        params = {
            "session_key": session_key,
            "driver_number": driver_number,
            "date>": format_api_datetime(start_time),
            "date<": format_api_datetime(end_time)
        }
        return self._request("position", params)

    def get_car_data(self, session_key, driver_number=None, start_time=None, end_time=None):
        """Retrieve telemetry data (RPM, speed, gear, throttle, brake, DRS) for a session."""
        params = {
            "session_key": session_key,
            "driver_number": driver_number,
            "date>": format_api_datetime(start_time),
            "date<": format_api_datetime(end_time)
        }
        return self._request("car_data", params)

    def get_location(self, session_key, driver_number=None, start_time=None, end_time=None):
        """Retrieve GPS telemetry location data (X, Y, Z coordinates) for a session."""
        params = {
            "session_key": session_key,
            "driver_number": driver_number,
            "date>": format_api_datetime(start_time),
            "date<": format_api_datetime(end_time)
        }
        return self._request("location", params)

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

def main():
    # Load token from local .env if present
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Retrieve and filter Formula 1 telemetry and position data from OpenF1 API."
    )
    # Mode selection
    parser.add_argument("--mode", type=str, default="position", choices=["session", "position", "car-data", "location"],
                        help="Data retrieval mode: session (metadata), position (default), car-data (telemetry), or location (GPS)")
    
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

    args = parser.parse_args()

    # Validate session parameter based on mode
    if args.mode != "session" and args.session is None:
        parser.error(f"--session is required when --mode is '{args.mode}'")

    client = OpenF1Client(token=args.token)
    
    try:
        # Handle Session Query Mode separately
        if args.mode == "session":
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
                    print(f"\nSessions at {sessions[0].get('location')} ({sessions[0].get('country_name')}) in {args.year}:")
                    print_table(headers, rows)
            return

        # 1. Resolve Session for data modes
        print(f"Searching for session '{args.session}' at '{args.track}' in {args.year}...", file=sys.stderr)
        session = client.get_session(args.year, args.track, args.session)
        session_key = session["session_key"]
        session_start_str = session.get("date_start")
        print(f"Found session: {session.get('session_name')} at {session.get('location')} ({session.get('country_name')}) [Key: {session_key}]", file=sys.stderr)
        
        # 2. Resolve Driver if specified
        driver_number = None
        driver_info = None
        if args.driver:
            print(f"Searching for driver '{args.driver}' in this session...", file=sys.stderr)
            driver_info = client.get_driver(session_key, args.driver)
            driver_number = driver_info["driver_number"]
            print(f"Resolved driver: {driver_info.get('full_name')} (#{driver_number})", file=sys.stderr)
            
        # 3. Resolve Query Time Bounds
        resolved_start, resolved_end = resolve_time_bounds(
            session_start_str=session_start_str,
            start_time=args.start_time,
            end_time=args.end_time,
            start_offset=args.start_offset,
            end_offset=args.end_offset,
            limit_minutes=args.limit_minutes
        )
        
        # 4. Fetch the target data based on mode
        print(f"Fetching {args.mode} data...", file=sys.stderr)
        if args.mode == "position":
            data_points = client.get_positions(
                session_key=session_key,
                driver_number=driver_number,
                start_time=resolved_start,
                end_time=resolved_end
            )
        elif args.mode == "car-data":
            data_points = client.get_car_data(
                session_key=session_key,
                driver_number=driver_number,
                start_time=resolved_start,
                end_time=resolved_end
            )
        elif args.mode == "location":
            data_points = client.get_location(
                session_key=session_key,
                driver_number=driver_number,
                start_time=resolved_start,
                end_time=resolved_end
            )
            
        # 5. Apply sample limits if requested
        if args.limit_samples is not None and args.limit_samples > 0:
            data_points = data_points[:args.limit_samples]
            
        if args.json:
            print(json.dumps(data_points, indent=2))
            return
            
        # 6. Format and display data
        if args.mode == "position":
            if not data_points:
                print("No position updates found in the specified timeframe.")
                return

            if driver_number is not None:
                headers = ["Relative Time", "Timestamp (UTC)", "Position"]
                rows = []
                session_start = parse_iso_datetime(session_start_str) if session_start_str else None
                
                for pos in data_points:
                    date_str = pos.get("date")
                    position = pos.get("position")
                    
                    rel_time = "N/A"
                    time_display = date_str
                    if date_str:
                        try:
                            dt = parse_iso_datetime(date_str)
                            time_display = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            if session_start:
                                diff = dt - session_start
                                total_seconds = int(diff.total_seconds())
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                seconds = total_seconds % 60
                                rel_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        except Exception:
                            pass
                    rows.append([rel_time, time_display, position])
                
                rows.sort(key=lambda x: x[1])
                print(f"\nPosition history for {driver_info.get('full_name')} (#{driver_number}) during {session.get('session_name')}:")
                print_table(headers, rows)
            else:
                print("Fetching driver details to map numbers to names...", file=sys.stderr)
                drivers = client._request("drivers", {"session_key": session_key})
                driver_map = {d["driver_number"]: d for d in drivers}
                
                headers = ["Relative Time", "Timestamp (UTC)", "Driver", "Position"]
                rows = []
                session_start = parse_iso_datetime(session_start_str) if session_start_str else None
                
                for pos in data_points:
                    d_num = pos.get("driver_number")
                    position = pos.get("position")
                    date_str = pos.get("date")
                    
                    d_info = driver_map.get(d_num, {})
                    d_display = f"{d_info.get('name_acronym', '???')} (#{d_num})"
                    
                    rel_time = "N/A"
                    time_display = date_str
                    if date_str:
                        try:
                            dt = parse_iso_datetime(date_str)
                            time_display = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            if session_start:
                                diff = dt - session_start
                                total_seconds = int(diff.total_seconds())
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                seconds = total_seconds % 60
                                rel_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        except Exception:
                            pass
                    rows.append([rel_time, time_display, d_display, position])
                    
                rows.sort(key=lambda x: x[1])
                print(f"\nChronological position changes during {session.get('session_name')}:")
                print_table(headers, rows)
                
        elif args.mode == "car-data":
            if not data_points:
                print("No car telemetry data found in the specified timeframe.")
                return
                
            headers = ["Relative Time", "Timestamp (UTC)", "Driver", "Speed (km/h)", "RPM", "Gear", "Throttle (%)", "Brake", "DRS"]
            rows = []
            session_start = parse_iso_datetime(session_start_str) if session_start_str else None
            
            driver_map = {}
            if driver_number is None:
                print("Fetching driver details to map numbers to names...", file=sys.stderr)
                drivers = client._request("drivers", {"session_key": session_key})
                driver_map = {d["driver_number"]: d for d in drivers}

            for sample in data_points:
                d_num = sample.get("driver_number")
                if driver_number is None:
                    d_info = driver_map.get(d_num, {})
                    d_display = f"{d_info.get('name_acronym', '???')} (#{d_num})"
                else:
                    d_display = f"{driver_info.get('name_acronym', '???')} (#{d_num})"
                
                date_str = sample.get("date")
                speed = sample.get("speed")
                rpm = sample.get("rpm")
                gear = sample.get("n_gear")
                throttle = sample.get("throttle")
                brake_val = sample.get("brake")
                drs = sample.get("drs")
                
                # Format brake status
                if brake_val is True or (isinstance(brake_val, (int, float)) and brake_val > 0):
                    brake_display = "On"
                else:
                    brake_display = "Off"
                    
                rel_time = "N/A"
                time_display = date_str
                if date_str:
                    try:
                        dt = parse_iso_datetime(date_str)
                        time_display = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        if session_start:
                            diff = dt - session_start
                            total_seconds = int(diff.total_seconds())
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            seconds = total_seconds % 60
                            rel_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    except Exception:
                        pass
                        
                rows.append([rel_time, time_display, d_display, speed, rpm, gear, throttle, brake_display, drs])
                
            rows.sort(key=lambda x: x[1])
            print(f"\nCar telemetry during {session.get('session_name')}:")
            print_table(headers, rows)
            
        elif args.mode == "location":
            if not data_points:
                print("No location data found in the specified timeframe.")
                return
                
            headers = ["Relative Time", "Timestamp (UTC)", "Driver", "X (mm)", "Y (mm)", "Z (mm)"]
            rows = []
            session_start = parse_iso_datetime(session_start_str) if session_start_str else None
            
            driver_map = {}
            if driver_number is None:
                print("Fetching driver details to map numbers to names...", file=sys.stderr)
                drivers = client._request("drivers", {"session_key": session_key})
                driver_map = {d["driver_number"]: d for d in drivers}
                
            for sample in data_points:
                d_num = sample.get("driver_number")
                if driver_number is None:
                    d_info = driver_map.get(d_num, {})
                    d_display = f"{d_info.get('name_acronym', '???')} (#{d_num})"
                else:
                    d_display = f"{driver_info.get('name_acronym', '???')} (#{d_num})"
                    
                date_str = sample.get("date")
                x = sample.get("x")
                y = sample.get("y")
                z = sample.get("z")
                
                rel_time = "N/A"
                time_display = date_str
                if date_str:
                    try:
                        dt = parse_iso_datetime(date_str)
                        time_display = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        if session_start:
                            diff = dt - session_start
                            total_seconds = int(diff.total_seconds())
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            seconds = total_seconds % 60
                            rel_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    except Exception:
                        pass
                        
                rows.append([rel_time, time_display, d_display, x, y, z])
                
            rows.sort(key=lambda x: x[1])
            print(f"\nGPS location data during {session.get('session_name')}:")
            print_table(headers, rows)
            
    except OpenF1Error as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
