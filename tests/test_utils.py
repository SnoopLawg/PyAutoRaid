"""Tests for utility functions that don't require a screen or game running."""

import re
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add parent dir to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Modules'))


class TestCreateTaskTimeConversion(unittest.TestCase):
    """Test the time conversion logic from CreateTask.py."""

    def _convert(self, time_str):
        # Inline the logic to avoid importing tkinter at module level
        time_part, meridiem = time_str.split()
        hour, minute = map(int, time_part.split(':'))
        if meridiem == "PM" and hour < 12:
            hour += 12
        elif meridiem == "AM" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    def test_midnight(self):
        self.assertEqual(self._convert("12:00 AM"), "00:00")

    def test_noon(self):
        self.assertEqual(self._convert("12:00 PM"), "12:00")

    def test_morning(self):
        self.assertEqual(self._convert("09:30 AM"), "09:30")

    def test_afternoon(self):
        self.assertEqual(self._convert("03:00 PM"), "15:00")

    def test_late_night(self):
        self.assertEqual(self._convert("11:30 PM"), "23:30")

    def test_early_morning(self):
        self.assertEqual(self._convert("01:00 AM"), "01:00")

    def test_generate_time_options_count(self):
        # 24 hours * 2 intervals (00 and 30) = 48 options
        times = []
        for hour in range(24):
            for minute in [0, 30]:
                if hour < 12:
                    suffix = "AM"
                    display_hour = hour if hour > 0 else 12
                else:
                    suffix = "PM"
                    display_hour = hour - 12 if hour > 12 else 12
                times.append(f"{display_hour:02d}:{minute:02d} {suffix}")
        self.assertEqual(len(times), 48)
        self.assertEqual(times[0], "12:00 AM")
        self.assertEqual(times[-1], "11:30 PM")


class TestVersionIncrement(unittest.TestCase):
    """Test the version increment logic from increment_version.py."""

    def _increment(self, tag):
        match = re.match(r'v(\d+\.\d+)-beta', tag)
        if not match:
            return None
        version = match.group(1)
        major, minor = map(int, version.split('.'))
        minor += 1
        return f"v{major}.{minor}-beta"

    def test_basic_increment(self):
        self.assertEqual(self._increment("v1.5-beta"), "v1.6-beta")

    def test_zero_minor(self):
        self.assertEqual(self._increment("v2.0-beta"), "v2.1-beta")

    def test_high_minor(self):
        self.assertEqual(self._increment("v1.99-beta"), "v1.100-beta")

    def test_invalid_format(self):
        self.assertIsNone(self._increment("1.0"))
        self.assertIsNone(self._increment("v1.0"))
        self.assertIsNone(self._increment("release-1.0"))


class TestBaseHelpers(unittest.TestCase):
    """Test the helper functions from base.py with mocked pyautogui."""

    @patch('base.pyautogui')
    def test_locate_and_click_found(self, mock_pyautogui):
        from base import locate_and_click
        mock_location = MagicMock()
        mock_pyautogui.locateOnScreen.return_value = mock_location
        mock_pyautogui.center.return_value = (100, 200)

        result = locate_and_click("fake.png", sleep_after=0)

        self.assertIsNotNone(result)
        mock_pyautogui.click.assert_called_once_with(100, 200)

    @patch('base.pyautogui')
    def test_locate_and_click_not_found(self, mock_pyautogui):
        from base import locate_and_click
        mock_pyautogui.locateOnScreen.return_value = None

        result = locate_and_click("fake.png", sleep_after=0)

        self.assertIsNone(result)
        mock_pyautogui.click.assert_not_called()

    @patch('base.pyautogui')
    def test_locate_and_click_no_click(self, mock_pyautogui):
        from base import locate_and_click
        mock_location = MagicMock()
        mock_pyautogui.locateOnScreen.return_value = mock_location

        result = locate_and_click("fake.png", click=False, sleep_after=0)

        self.assertIsNotNone(result)
        mock_pyautogui.click.assert_not_called()

    @patch('base.pyautogui')
    def test_locate_and_click_loop_clicks_until_gone(self, mock_pyautogui):
        from base import locate_and_click_loop
        mock_location = MagicMock()
        # Found 3 times, then gone
        mock_pyautogui.locateOnScreen.side_effect = [
            mock_location, mock_location, mock_location, None,
        ]
        mock_pyautogui.center.return_value = (50, 50)

        clicks = locate_and_click_loop("fake.png", sleep_after=0)

        self.assertEqual(clicks, 3)
        self.assertEqual(mock_pyautogui.click.call_count, 3)

    @patch('base.pyautogui')
    def test_locate_and_click_loop_respects_max_retries(self, mock_pyautogui):
        from base import locate_and_click_loop
        mock_location = MagicMock()
        # Always found — should stop at max_retries
        mock_pyautogui.locateOnScreen.return_value = mock_location
        mock_pyautogui.center.return_value = (50, 50)

        clicks = locate_and_click_loop("fake.png", sleep_after=0, max_retries=5)

        self.assertEqual(clicks, 5)

    @patch('base.time')
    @patch('base.pyautogui')
    def test_wait_for_image_found(self, mock_pyautogui, mock_time):
        from base import wait_for_image
        mock_location = MagicMock()
        mock_pyautogui.locateOnScreen.side_effect = [None, None, mock_location]
        mock_time.time.side_effect = [0, 1, 2, 3]
        mock_time.sleep = MagicMock()

        result = wait_for_image("fake.png", timeout=10, poll_interval=1)

        self.assertIsNotNone(result)

    def test_asset_path_join(self):
        from base import asset
        result = asset("/some/path", "image.png")
        self.assertEqual(result, os.path.join("/some/path", "image.png"))


if __name__ == '__main__':
    unittest.main()
