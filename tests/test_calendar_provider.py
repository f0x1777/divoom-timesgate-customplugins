from datetime import datetime, timedelta
import unittest
from unittest.mock import Mock, patch

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

    def test_calendar_urls_support_numbered_feeds(self):
        with patch.dict(
            "os.environ",
            {
                "CALENDAR_ICS_URL": "",
                "CALENDAR_ICS_URLS": "",
                "CALENDAR_ICS_URL_1": "https://example.com/one.ics",
                "CALENDAR_ICS_URL_2": "https://example.com/two.ics",
            },
            clear=True,
        ):
            urls = calendar_provider._calendar_urls()

        self.assertEqual(urls, ["https://example.com/one.ics", "https://example.com/two.ics"])

    def test_calendar_urls_normalize_webcal_to_https(self):
        with patch.dict(
            "os.environ",
            {
                "CALENDAR_ICS_URL": "webcal://example.com/private.ics",
                "CALENDAR_ICS_URLS": "",
                "CALENDAR_ICS_URL_1": "",
                "CALENDAR_ICS_URL_2": "",
            },
            clear=True,
        ):
            urls = calendar_provider._calendar_urls()

        self.assertEqual(urls, ["https://example.com/private.ics"])

    def test_get_next_events_merges_multiple_calendars_by_start_time(self):
        first = (datetime.now() + timedelta(hours=2)).strftime("%Y%m%dT%H%M%S")
        second = (datetime.now() + timedelta(hours=1)).strftime("%Y%m%dT%H%M%S")
        one = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{first}
SUMMARY:Later event
END:VEVENT
END:VCALENDAR
"""
        two = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{second}
SUMMARY:Earlier event
END:VEVENT
END:VCALENDAR
"""
        responses = [Mock(text=one), Mock(text=two)]
        for response in responses:
            response.raise_for_status.return_value = None

        with patch.dict(
            "os.environ",
            {
                "CALENDAR_ICS_URL": "",
                "CALENDAR_ICS_URLS": "",
                "CALENDAR_ICS_URL_1": "https://example.com/one.ics",
                "CALENDAR_ICS_URL_2": "https://example.com/two.ics",
            },
            clear=True,
        ), \
             patch.object(calendar_provider, "CACHE_TTL_SECS", 0), \
             patch("requests.get", side_effect=responses):
            events = calendar_provider.get_next_events(max_items=2)

        self.assertEqual([event["summary"] for event in events], ["Earlier event", "Later event"])


if __name__ == "__main__":
    unittest.main()
