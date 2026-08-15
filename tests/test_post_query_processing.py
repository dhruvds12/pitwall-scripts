import io
import json
import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main


# Self-contained sample fixtures for testing post-query processing
SAMPLE_DRIVERS = [
    {
        "meeting_key": 1289,
        "session_key": 11316,
        "driver_number": 1,
        "broadcast_name": "L NORRIS",
        "full_name": "Lando NORRIS",
        "name_acronym": "NOR",
        "team_name": "McLaren",
        "team_colour": "F47600",
        "first_name": "Lando",
        "last_name": "Norris",
        "headshot_url": "https://media.formula1.com/d_driver_fallback_image.png/content/dam/fom-website/drivers/L/LANNOR01_Lando_Norris/lannor01.png.transform/1col/image.png",
        "country_code": None
    },
    {
        "meeting_key": 1289,
        "session_key": 11316,
        "driver_number": 3,
        "broadcast_name": "M VERSTAPPEN",
        "full_name": "Max VERSTAPPEN",
        "name_acronym": "VER",
        "team_name": "Red Bull Racing",
        "team_colour": "4781D7",
        "first_name": "Max",
        "last_name": "Verstappen",
        "headshot_url": "https://media.formula1.com/d_driver_fallback_image.png/content/dam/fom-website/drivers/M/MAXVER01_Max_Verstappen/maxver01.png.transform/1col/image.png",
        "country_code": None
    }
]

SAMPLE_LOCATIONS = [
    {
        "date": "2026-07-03T12:00:00.116000+00:00",
        "session_key": 11316,
        "z": 2025,
        "y": 12534,
        "meeting_key": 1289,
        "driver_number": 1,
        "x": 1130
    },
    {
        "date": "2026-07-03T12:00:00.476000+00:00",
        "session_key": 11316,
        "z": 2025,
        "y": 12592,
        "meeting_key": 1289,
        "driver_number": 1,
        "x": 1287
    },
    {
        "date": "2026-07-03T12:00:00.656000+00:00",
        "session_key": 11316,
        "z": 2025,
        "y": 12633,
        "meeting_key": 1289,
        "driver_number": 1,
        "x": 1419
    },
    {
        "date": "2026-07-03T12:00:00.956000+00:00",
        "session_key": 11316,
        "z": 2026,
        "y": 12693,
        "meeting_key": 1289,
        "driver_number": 1,
        "x": 1642
    },
    {
        "date": "2026-07-03T12:00:01.096000+00:00",
        "session_key": 11316,
        "z": 2026,
        "y": 12727,
        "meeting_key": 1289,
        "driver_number": 1,
        "x": 1756
    }
]


class TestPostQueryProcessing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load sample data files if available in local workspace, otherwise use in-memory fixtures
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
        driver_file = os.path.join(data_dir, 'driver_data.json')
        location_file = os.path.join(data_dir, 'test_location.json')

        if os.path.exists(driver_file):
            try:
                with open(driver_file, 'r', encoding='utf-8') as f:
                    cls.drivers = json.load(f)
            except Exception:
                cls.drivers = SAMPLE_DRIVERS
        else:
            cls.drivers = SAMPLE_DRIVERS

        if os.path.exists(location_file):
            try:
                with open(location_file, 'r', encoding='utf-8') as f:
                    cls.locations = json.load(f)
            except Exception:
                cls.locations = SAMPLE_LOCATIONS
        else:
            cls.locations = SAMPLE_LOCATIONS

    def test_print_table_formatting(self):
        headers = ["Col A", "Column B"]
        rows = [
            ["short", 12345],
            ["a much longer value", 6]
        ]

        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            main.print_table(headers, rows)

        output = stdout_buf.getvalue()
        lines = output.strip().split("\n")
        self.assertEqual(len(lines), 4)
        self.assertIn("Col A", lines[0])
        self.assertIn("Column B", lines[0])
        self.assertIn("-+-", lines[1])
        self.assertIn("a much longer value", lines[3])

    def test_print_table_empty(self):
        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            main.print_table(["H1"], [])
        self.assertEqual(stdout_buf.getvalue().strip(), "No data available.")

    def test_relative_time_and_iso_formatting(self):
        session_start = main.parse_iso_datetime("2026-07-03T12:00:00+00:00")

        # Exact start
        dt1 = main.parse_iso_datetime("2026-07-03T12:00:00.000+00:00")
        diff1 = dt1 - session_start
        total_sec1 = int(diff1.total_seconds())
        h, m, s = total_sec1 // 3600, (total_sec1 % 3600) // 60, total_sec1 % 60
        self.assertEqual(f"{h:02d}:{m:02d}:{s:02d}", "00:00:00")

        # 1 hour 15 min 30 sec later
        dt2 = main.parse_iso_datetime("2026-07-03T13:15:30.500+00:00")
        diff2 = dt2 - session_start
        total_sec2 = int(diff2.total_seconds())
        h, m, s = total_sec2 // 3600, (total_sec2 % 3600) // 60, total_sec2 % 60
        self.assertEqual(f"{h:02d}:{m:02d}:{s:02d}", "01:15:30")

    def test_driver_data_lookup_and_formatting(self):
        driver_map = {d["driver_number"]: d for d in self.drivers}

        # Test driver 1 (Norris)
        norris = driver_map.get(1)
        self.assertIsNotNone(norris)
        self.assertEqual(norris.get("name_acronym"), "NOR")
        self.assertEqual(norris.get("full_name"), "Lando NORRIS")

        # Test driver 3 (Verstappen)
        ver = driver_map.get(3)
        self.assertIsNotNone(ver)
        self.assertEqual(ver.get("name_acronym"), "VER")

        # Driver display string
        display_str = f"{norris.get('name_acronym', '???')} (#{norris.get('driver_number')})"
        self.assertEqual(display_str, "NOR (#1)")

    def test_location_sample_data_processing(self):
        # Pick first 5 location records
        sample_locs = self.locations[:5]
        session_start = main.parse_iso_datetime("2026-07-03T12:00:00+00:00")

        rows = []
        for sample in sample_locs:
            d_num = sample.get("driver_number")
            date_str = sample.get("date")
            x = sample.get("x")
            y = sample.get("y")
            z = sample.get("z")

            dt = main.parse_iso_datetime(date_str)
            time_display = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            diff = dt - session_start
            total_seconds = int(diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            rel_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            rows.append([rel_time, time_display, f"NOR (#{d_num})", x, y, z])

        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0][0], "00:00:00")
        self.assertEqual(rows[0][3], 1130)
        self.assertEqual(rows[0][4], 12534)
        self.assertEqual(rows[0][5], 2025)

    def test_brake_value_interpretation(self):
        def interpret_brake(brake_val):
            if brake_val is True or (isinstance(brake_val, (int, float)) and brake_val > 0):
                return "On"
            return "Off"

        self.assertEqual(interpret_brake(True), "On")
        self.assertEqual(interpret_brake(1), "On")
        self.assertEqual(interpret_brake(100), "On")
        self.assertEqual(interpret_brake(0.5), "On")
        self.assertEqual(interpret_brake(False), "Off")
        self.assertEqual(interpret_brake(0), "Off")
        self.assertEqual(interpret_brake(None), "Off")


if __name__ == "__main__":
    unittest.main()
