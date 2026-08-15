import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main


class TestOpenF1ClientQueries(unittest.TestCase):

    def setUp(self):
        self.client = main.OpenF1Client(token="test_token_123")

    @patch("urllib.request.urlopen")
    def test_request_url_params_and_auth_header(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = json.dumps([{"key": "value"}]).encode("utf-8")
        mock_urlopen.return_value = mock_response

        params = {
            "session_key": 9126,
            "driver_number": 44,
            "date>": "2023-07-09T14:00:00.000",
            "date<": "2023-07-09T15:00:00.000",
            "empty_param": None
        }

        result = self.client._request("position", params)

        self.assertEqual(result, [{"key": "value"}])
        mock_urlopen.assert_called_once()
        req_arg = mock_urlopen.call_args[0][0]
        
        # Check URL
        self.assertTrue(req_arg.full_url.startswith("https://api.openf1.org/v1/position?"))
        self.assertIn("session_key=9126", req_arg.full_url)
        self.assertIn("driver_number=44", req_arg.full_url)
        self.assertIn("date%3E=2023-07-09T14%3A00%3A00.000", req_arg.full_url)
        self.assertIn("date%3C=2023-07-09T15%3A00%3A00.000", req_arg.full_url)
        self.assertNotIn("empty_param", req_arg.full_url)

        # Check Auth Header
        self.assertEqual(req_arg.get_header("Authorization"), "Bearer test_token_123")

    @patch("urllib.request.urlopen")
    def test_request_bearer_token_not_duplicated(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = json.dumps([]).encode("utf-8")
        mock_urlopen.return_value = mock_response

        client_bearer = main.OpenF1Client(token="Bearer already_has_bearer")
        client_bearer._request("sessions")

        req_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(req_arg.get_header("Authorization"), "Bearer already_has_bearer")

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_request_rate_limit_retry_success(self, mock_urlopen, mock_sleep):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = json.dumps([{"status": "ok"}]).encode("utf-8")

        error_429 = urllib.error.HTTPError(
            url="https://api.openf1.org/v1/sessions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None
        )

        mock_urlopen.side_effect = [error_429, mock_response]

        res = self.client._request("sessions")
        self.assertEqual(res, [{"status": "ok"}])
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    @patch("urllib.request.urlopen")
    def test_request_404_empty_response(self, mock_urlopen):
        import io
        error_404 = urllib.error.HTTPError(
            url="https://api.openf1.org/v1/sessions",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(json.dumps({"detail": "no records found"}).encode("utf-8"))
        )
        mock_urlopen.side_effect = error_404

        res = self.client._request("sessions")
        self.assertEqual(res, [])

    @patch("urllib.request.urlopen")
    def test_request_http_error_detail(self, mock_urlopen):
        import io
        error_400 = urllib.error.HTTPError(
            url="https://api.openf1.org/v1/sessions",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(json.dumps({"detail": "Invalid parameter: year"}).encode("utf-8"))
        )
        mock_urlopen.side_effect = error_400

        with self.assertRaises(main.OpenF1Error) as ctx:
            self.client._request("sessions")
        self.assertIn("HTTP error 400: Invalid parameter: year", str(ctx.exception))

    @patch.object(main.OpenF1Client, "_request")
    def test_get_positions_query_params(self, mock_request):
        mock_request.return_value = [{"position": 1}]
        import datetime

        start = datetime.datetime(2023, 7, 9, 14, 0, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2023, 7, 9, 14, 5, 0, tzinfo=datetime.timezone.utc)

        res = self.client.get_positions(session_key=9126, driver_number=44, start_time=start, end_time=end)

        self.assertEqual(res, [{"position": 1}])
        mock_request.assert_called_once_with("position", {
            "session_key": 9126,
            "driver_number": 44,
            "date>": "2023-07-09T14:00:00.000",
            "date<": "2023-07-09T14:05:00.000"
        })

    @patch.object(main.OpenF1Client, "_request")
    def test_get_car_data_query_params(self, mock_request):
        mock_request.return_value = [{"speed": 310}]
        import datetime

        start = datetime.datetime(2023, 7, 9, 14, 0, 0, tzinfo=datetime.timezone.utc)
        res = self.client.get_car_data(session_key=9126, driver_number=1, start_time=start, end_time=None)

        self.assertEqual(res, [{"speed": 310}])
        mock_request.assert_called_once_with("car_data", {
            "session_key": 9126,
            "driver_number": 1,
            "date>": "2023-07-09T14:00:00.000",
            "date<": None
        })

    @patch.object(main.OpenF1Client, "_request")
    def test_get_location_query_params(self, mock_request):
        mock_request.return_value = [{"x": 100, "y": 200, "z": 300}]

        res = self.client.get_location(session_key=9126, driver_number=None, start_time=None, end_time=None)

        self.assertEqual(res, [{"x": 100, "y": 200, "z": 300}])
        mock_request.assert_called_once_with("location", {
            "session_key": 9126,
            "driver_number": None,
            "date>": None,
            "date<": None
        })

    @patch.object(main.OpenF1Client, "_request")
    def test_get_session_selection_and_cancellation(self, mock_request):
        mock_request.return_value = [
            {"session_key": 100, "session_name": "Practice 1", "session_type": "Practice", "location": "Silverstone"},
            {"session_key": 101, "session_name": "Race", "session_type": "Race", "location": "Silverstone", "is_cancelled": False},
            {"session_key": 102, "session_name": "Sprint", "session_type": "Sprint", "location": "Silverstone", "is_cancelled": True}
        ]

        # Exact match
        session = self.client.get_session(2023, "Silverstone", "Race")
        self.assertEqual(session["session_key"], 101)

        # Cancelled session
        with self.assertRaises(main.SessionCancelledError):
            self.client.get_session(2023, "Silverstone", "Sprint")

        # Not found session
        with self.assertRaises(main.SessionNotFoundError) as ctx:
            self.client.get_session(2023, "Silverstone", "Qualifying")
        self.assertIn("Available sessions for this Grand Prix: Practice 1, Race, Sprint", str(ctx.exception))

    @patch.object(main.OpenF1Client, "_request")
    def test_get_driver_matching_variants(self, mock_request):
        mock_drivers = [
            {"driver_number": 44, "name_acronym": "HAM", "first_name": "Lewis", "last_name": "Hamilton", "full_name": "Lewis HAMILTON"},
            {"driver_number": 63, "name_acronym": "RUS", "first_name": "George", "last_name": "Russell", "full_name": "George RUSSELL"},
            {"driver_number": 1, "name_acronym": "VER", "first_name": "Max", "last_name": "Verstappen", "full_name": "Max VERSTAPPEN"}
        ]
        mock_request.return_value = mock_drivers

        # By number
        d1 = self.client.get_driver(9126, "44")
        self.assertEqual(d1["name_acronym"], "HAM")
        d1_int = self.client.get_driver(9126, 44)
        self.assertEqual(d1_int["name_acronym"], "HAM")

        # By acronym
        d2 = self.client.get_driver(9126, "rus")
        self.assertEqual(d2["driver_number"], 63)

        # By last name
        d3 = self.client.get_driver(9126, "Verstappen")
        self.assertEqual(d3["driver_number"], 1)

        # By partial full name
        d4 = self.client.get_driver(9126, "Lewis")
        self.assertEqual(d4["driver_number"], 44)

        # Not found
        with self.assertRaises(main.DriverNotFoundError) as ctx:
            self.client.get_driver(9126, "Norris")
        self.assertIn("Available drivers in this session: HAM (#44), RUS (#63), VER (#1)", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
