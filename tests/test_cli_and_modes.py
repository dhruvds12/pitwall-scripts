import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cli
import main


class TestCLIAndModes(unittest.TestCase):

    @patch("cli.OpenF1Client")
    def test_cli_session_mode_all_sessions_table(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_sessions_at_track.return_value = [
            {"session_name": "Practice 1", "session_type": "Practice", "date_start": "2023-07-07T11:30:00", "session_key": 9119, "location": "Silverstone", "country_name": "UK"}
        ]
        mock_client_cls.return_value = mock_client

        test_args = ["main.py", "--mode", "session", "--track", "Silverstone", "--year", "2023"]
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("sys.argv", test_args), patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            main.main()

        output = stdout_buf.getvalue()
        self.assertIn("Practice 1", output)
        self.assertIn("9119", output)
        mock_client.get_sessions_at_track.assert_called_once_with(2023, "Silverstone")

    @patch("cli.OpenF1Client")
    def test_cli_session_mode_single_session_json(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_session.return_value = {
            "session_name": "Race",
            "session_key": 9126,
            "location": "Silverstone"
        }
        mock_client_cls.return_value = mock_client

        test_args = ["main.py", "--mode", "session", "--track", "Silverstone", "--session", "Race", "--year", "2023", "--json"]
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("sys.argv", test_args), patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            main.main()

        data = json.loads(stdout_buf.getvalue())
        self.assertEqual(data["session_key"], 9126)
        self.assertEqual(data["session_name"], "Race")
        mock_client.get_session.assert_called_once_with(2023, "Silverstone", "Race")

    def test_cli_missing_session_for_position_mode(self):
        test_args = ["main.py", "--mode", "position", "--track", "Silverstone"]
        stderr_buf = io.StringIO()

        with patch("sys.argv", test_args), patch("sys.stderr", stderr_buf):
            with self.assertRaises(SystemExit) as ctx:
                main.main()
            self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("--session is required when --mode is 'position'", stderr_buf.getvalue())

    @patch("cli.OpenF1Client")
    def test_cli_position_mode_with_driver_and_limit(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_session.return_value = {
            "session_key": 9126,
            "session_name": "Race",
            "location": "Silverstone",
            "country_name": "United Kingdom",
            "date_start": "2023-07-09T14:00:00+00:00"
        }
        mock_client.get_driver.return_value = {
            "driver_number": 44,
            "full_name": "Lewis HAMILTON",
            "name_acronym": "HAM"
        }
        mock_client.get_positions.return_value = [
            {"date": "2023-07-09T14:01:00.000+00:00", "position": 1},
            {"date": "2023-07-09T14:02:00.000+00:00", "position": 2},
            {"date": "2023-07-09T14:03:00.000+00:00", "position": 2},
            {"date": "2023-07-09T14:04:00.000+00:00", "position": 3}
        ]
        mock_client_cls.return_value = mock_client

        test_args = [
            "main.py", "--mode", "position", "--track", "Silverstone",
            "--session", "Race", "--driver", "HAM", "--limit-samples", "2",
            "--year", "2023"
        ]
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("sys.argv", test_args), patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            main.main()

        output = stdout_buf.getvalue()
        self.assertIn("Position history for Lewis HAMILTON (#44)", output)
        # Should have only 2 data rows due to limit-samples=2
        lines = [l for l in output.strip().split("\n") if "2023-07-09" in l]
        self.assertEqual(len(lines), 2)

    @patch("cli.OpenF1Client")
    def test_cli_car_data_mode_json(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_session.return_value = {
            "session_key": 9126,
            "session_name": "Race",
            "location": "Silverstone",
            "country_name": "United Kingdom",
            "date_start": "2023-07-09T14:00:00+00:00"
        }
        mock_client.get_driver.return_value = {
            "driver_number": 1,
            "full_name": "Max VERSTAPPEN",
            "name_acronym": "VER"
        }
        mock_client.get_car_data.return_value = [
            {"date": "2023-07-09T14:00:01.000+00:00", "speed": 290, "rpm": 11000, "n_gear": 7, "throttle": 100, "brake": 0, "drs": 0, "driver_number": 1}
        ]
        mock_client_cls.return_value = mock_client

        test_args = [
            "main.py", "--mode", "car-data", "--track", "Silverstone",
            "--session", "Race", "--driver", "1", "--json", "--year", "2023"
        ]
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("sys.argv", test_args), patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            main.main()

        data = json.loads(stdout_buf.getvalue())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["speed"], 290)

    @patch("cli.OpenF1Client")
    def test_cli_location_mode_all_drivers_table(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_session.return_value = {
            "session_key": 9126,
            "session_name": "Race",
            "location": "Silverstone",
            "country_name": "United Kingdom",
            "date_start": "2023-07-09T14:00:00+00:00"
        }
        mock_client._request.return_value = [
            {"driver_number": 1, "name_acronym": "VER"}
        ]
        mock_client.get_location.return_value = [
            {"date": "2023-07-09T14:00:01.000+00:00", "driver_number": 1, "x": 1000, "y": 2000, "z": 300}
        ]
        mock_client_cls.return_value = mock_client

        test_args = [
            "main.py", "--mode", "location", "--track", "Silverstone",
            "--session", "Race", "--year", "2023"
        ]
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("sys.argv", test_args), patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            main.main()

        output = stdout_buf.getvalue()
        self.assertIn("GPS location data during Race", output)
        self.assertIn("VER (#1)", output)
        self.assertIn("1000", output)

    @patch("cli.OpenF1Client")
    def test_cli_error_exit_handling(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_session.side_effect = main.SessionNotFoundError("Track not found")
        mock_client_cls.return_value = mock_client

        test_args = ["main.py", "--mode", "position", "--track", "Atlantis", "--session", "Race"]
        stderr_buf = io.StringIO()

        with patch("sys.argv", test_args), patch("sys.stderr", stderr_buf):
            with self.assertRaises(SystemExit) as ctx:
                main.main()
            self.assertEqual(ctx.exception.code, 1)
        self.assertIn("Error: Track not found", stderr_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
