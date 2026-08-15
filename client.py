"""
OpenF1 API Client for Formula 1 telemetry and session data.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from exceptions import (
    DriverNotFoundError,
    OpenF1Error,
    SessionCancelledError,
    SessionNotFoundError,
)
from time_utils import format_api_datetime


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
