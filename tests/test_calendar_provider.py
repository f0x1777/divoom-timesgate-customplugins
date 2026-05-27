from datetime import datetime, timedelta
import unittest

import calendar_provider


class CalendarProviderTests(unittest.TestCase):
    def test_parse_ics_event(self):
        start = (datetime.now() + timedelta(hours=1)).strftime("%Y%m%dT%H%M%S")
        text = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{start}
SUMMARY:Focus block
END:VEVENT
END:VCALENDAR
"""

        events = calendar_provider._parse_ics(text)

        self.assertEqual(events[0]["summary"], "Focus block")
        self.assertIn("start", events[0])


if __name__ == "__main__":
    unittest.main()
