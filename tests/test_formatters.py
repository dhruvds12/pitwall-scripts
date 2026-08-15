import datetime
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import formatters


class TestFormatters(unittest.TestCase):

    def test_format_brake_status(self):
        self.assertEqual(formatters.format_brake_status(True), "On")
        self.assertEqual(formatters.format_brake_status(1), "On")
        self.assertEqual(formatters.format_brake_status(0.5), "On")
        self.assertEqual(formatters.format_brake_status(100), "On")
        self.assertEqual(formatters.format_brake_status(False), "Off")
        self.assertEqual(formatters.format_brake_status(0), "Off")
        self.assertEqual(formatters.format_brake_status(None), "Off")

    def test_format_driver_display(self):
        # Driver info dict
        info = {"driver_number": 44, "name_acronym": "HAM"}
        self.assertEqual(formatters.format_driver_display(44, driver_info=info), "HAM (#44)")

        # Driver map
        driver_map = {1: {"driver_number": 1, "name_acronym": "VER"}}
        self.assertEqual(formatters.format_driver_display(1, driver_map=driver_map), "VER (#1)")
        self.assertEqual(formatters.format_driver_display(63, driver_map=driver_map), "??? (#63)")

        # Fallback
        self.assertEqual(formatters.format_driver_display(55), "#55")

    def test_build_session_table_rows(self):
        sessions = [
            {"session_name": "Race", "session_type": "Race", "date_start": "2023-07-09T14:00:00", "session_key": 9126},
            {"session_name": "Practice 1", "session_type": "Practice", "date_start": "2023-07-07T11:30:00", "session_key": 9119}
        ]
        headers, rows = formatters.build_session_table_rows(sessions)
        self.assertEqual(headers, ["Session Name", "Session Type", "Start Time (Local/Track)", "Session Key"])
        # Should be sorted chronologically by date_start
        self.assertEqual(rows[0][0], "Practice 1")
        self.assertEqual(rows[1][0], "Race")

    def test_build_position_table_rows_single_driver(self):
        session_start = datetime.datetime(2023, 7, 9, 14, 0, 0, tzinfo=datetime.timezone.utc)
        driver_info = {"driver_number": 44, "name_acronym": "HAM", "full_name": "Lewis HAMILTON"}
        data = [
            {"date": "2023-07-09T14:05:00.000+00:00", "position": 1}
        ]
        headers, rows = formatters.build_position_table_rows(data, session_start, driver_info=driver_info)
        self.assertEqual(headers, ["Relative Time", "Timestamp (UTC)", "Position"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "00:05:00")
        self.assertEqual(rows[0][2], 1)

    def test_build_position_table_rows_all_drivers(self):
        session_start = datetime.datetime(2023, 7, 9, 14, 0, 0, tzinfo=datetime.timezone.utc)
        driver_map = {44: {"driver_number": 44, "name_acronym": "HAM"}}
        data = [
            {"date": "2023-07-09T14:02:00.000+00:00", "driver_number": 44, "position": 3}
        ]
        headers, rows = formatters.build_position_table_rows(data, session_start, driver_map=driver_map)
        self.assertEqual(headers, ["Relative Time", "Timestamp (UTC)", "Driver", "Position"])
        self.assertEqual(rows[0][2], "HAM (#44)")
        self.assertEqual(rows[0][3], 3)

    def test_build_car_data_table_rows(self):
        session_start = datetime.datetime(2023, 7, 9, 14, 0, 0, tzinfo=datetime.timezone.utc)
        driver_map = {1: {"driver_number": 1, "name_acronym": "VER"}}
        data = [
            {
                "date": "2023-07-09T14:01:00.000+00:00",
                "driver_number": 1,
                "speed": 320,
                "rpm": 11500,
                "n_gear": 8,
                "throttle": 100,
                "brake": 0,
                "drs": 1
            }
        ]
        headers, rows = formatters.build_car_data_table_rows(data, session_start, driver_map=driver_map)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "VER (#1)")
        self.assertEqual(rows[0][3], 320)
        self.assertEqual(rows[0][7], "Off")
        self.assertEqual(rows[0][8], 1)

    def test_build_location_table_rows(self):
        session_start = datetime.datetime(2023, 7, 9, 14, 0, 0, tzinfo=datetime.timezone.utc)
        driver_map = {1: {"driver_number": 1, "name_acronym": "VER"}}
        data = [
            {
                "date": "2023-07-09T14:01:00.000+00:00",
                "driver_number": 1,
                "x": 1234,
                "y": 5678,
                "z": 900
            }
        ]
        headers, rows = formatters.build_location_table_rows(data, session_start, driver_map=driver_map)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "VER (#1)")
        self.assertEqual(rows[0][3], 1234)
        self.assertEqual(rows[0][4], 5678)
        self.assertEqual(rows[0][5], 900)


if __name__ == "__main__":
    unittest.main()
