import os
import sys
import datetime
import unittest

# Add parent directory to system path to import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main

class TestF1TelemetryHelpers(unittest.TestCase):
    def test_parse_offset_to_timedelta(self):
        # Test floats as minutes
        self.assertEqual(main.parse_offset_to_timedelta("5"), datetime.timedelta(minutes=5))
        self.assertEqual(main.parse_offset_to_timedelta("1.5"), datetime.timedelta(minutes=1.5))
        
        # Test string units
        self.assertEqual(main.parse_offset_to_timedelta("30s"), datetime.timedelta(seconds=30))
        self.assertEqual(main.parse_offset_to_timedelta("10m"), datetime.timedelta(minutes=10))
        self.assertEqual(main.parse_offset_to_timedelta("2h"), datetime.timedelta(hours=2))
        
        # Test spaces and case
        self.assertEqual(main.parse_offset_to_timedelta("  5M  "), datetime.timedelta(minutes=5))
        self.assertEqual(main.parse_offset_to_timedelta("15S"), datetime.timedelta(seconds=15))

    def test_format_api_datetime(self):
        # Timezone naive
        dt = datetime.datetime(2023, 9, 16, 13, 3, 35, 200000)
        self.assertEqual(main.format_api_datetime(dt), "2023-09-16T13:03:35.200")
        
        # Timezone aware (UTC)
        dt_utc = datetime.datetime(2023, 9, 16, 13, 3, 35, 200000, tzinfo=datetime.timezone.utc)
        self.assertEqual(main.format_api_datetime(dt_utc), "2023-09-16T13:03:35.200")
        
        # Timezone aware (Offset +02:00) -> should convert to UTC
        dt_offset = datetime.datetime(2023, 9, 16, 15, 3, 35, 200000, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
        self.assertEqual(main.format_api_datetime(dt_offset), "2023-09-16T13:03:35.200")

    def test_resolve_time_bounds(self):
        session_start_str = "2023-09-16T13:00:00+00:00"
        
        # Absolute start/end
        start, end = main.resolve_time_bounds(
            session_start_str,
            start_time="2023-09-16T13:03:35.200+00:00",
            end_time="2023-09-16T13:03:35.800+00:00"
        )
        self.assertEqual(start, datetime.datetime(2023, 9, 16, 13, 3, 35, 200000, tzinfo=datetime.timezone.utc))
        self.assertEqual(end, datetime.datetime(2023, 9, 16, 13, 3, 35, 800000, tzinfo=datetime.timezone.utc))
        
        # Relative offsets
        start_rel, end_rel = main.resolve_time_bounds(
            session_start_str,
            start_offset="5m",
            end_offset="10m"
        )
        self.assertEqual(start_rel, datetime.datetime(2023, 9, 16, 13, 5, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(end_rel, datetime.datetime(2023, 9, 16, 13, 10, 0, tzinfo=datetime.timezone.utc))
        
        # Relative start + limit minutes
        start_lim, end_lim = main.resolve_time_bounds(
            session_start_str,
            start_offset="5m",
            limit_minutes=2.5
        )
        self.assertEqual(start_lim, datetime.datetime(2023, 9, 16, 13, 5, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(end_lim, datetime.datetime(2023, 9, 16, 13, 7, 30, tzinfo=datetime.timezone.utc))

import json
import unittest.mock

class TestF1SessionRetrieval(unittest.TestCase):
    @unittest.mock.patch('urllib.request.urlopen')
    def test_get_sessions_at_track_success(self, mock_urlopen):
        mock_response = unittest.mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = json.dumps([
            {"location": "Silverstone", "country_name": "United Kingdom", "session_name": "Practice 1", "session_key": 9119},
            {"location": "Silverstone", "country_name": "United Kingdom", "session_name": "Race", "session_key": 9126},
            {"location": "Monaco", "country_name": "Monaco", "session_name": "Race", "session_key": 9100}
        ]).encode("utf-8")
        mock_urlopen.return_value = mock_response

        client = main.OpenF1Client()
        sessions = client.get_sessions_at_track(2023, "Silverstone")
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["session_key"], 9119)
        self.assertEqual(sessions[1]["session_key"], 9126)

    @unittest.mock.patch('urllib.request.urlopen')
    def test_get_sessions_at_track_not_found(self, mock_urlopen):
        mock_response = unittest.mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = json.dumps([
            {"location": "Silverstone", "session_name": "Race", "session_key": 9126}
        ]).encode("utf-8")
        mock_urlopen.return_value = mock_response

        client = main.OpenF1Client()
        with self.assertRaises(main.SessionNotFoundError) as ctx:
            client.get_sessions_at_track(2023, "Monza")
            
        self.assertIn("No track matching 'Monza' found", str(ctx.exception))
        self.assertIn("Available tracks in 2023: Silverstone", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
