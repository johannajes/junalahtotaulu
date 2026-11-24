"""Lähtötaulun olennaiset tarkistukset ilman toimivaa internetyhteyttä.

Suorita projektikansiossa: python3 -m unittest discover -s tests -v
Testiaineisto on keksittyä: näitä aikatauluja ei saa käyttää matkustamiseen.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import requests

import app as application
import digitraffic


STATION_NAMES = {"HKI": "Helsinki", "TPE": "Tampere", "KOK": "Kokkola", "OL": "Oulu"}


def timetable_row(station="KOK", event="DEPARTURE", time="2026-11-24T10:00:00.000Z", **extra):
    """Yksi pieni Digitrafficin aikataulurivi; extra muuttaa testattavan asian."""
    row = {
        "stationShortCode": station,
        "type": event,
        "scheduledTime": time,
        "trainStopping": True,
        "commercialStop": True,
        "cancelled": False,
    }
    row.update(extra)
    return row


def train(rows=None, number=23, **extra):
    """Riittävästi junan tietoja oikean käsittelyketjun kokeilemiseen."""
    value = {
        "trainNumber": number,
        "trainType": "IC",
        "trainCategory": "Long-distance",
        "departureDate": "2026-11-24",
        "cancelled": False,
        "timeTableRows": rows or [
            timetable_row(),
            timetable_row("OL", "ARRIVAL", "2026-11-24T12:00:00.000Z"),
        ],
    }
    value.update(extra)
    return value


def normalized(row=None, **train_changes):
    """Normalisoi yhden junan ja palauta sen ainoa Kokkola-lähtö."""
    rows = [
        row or timetable_row(),
        timetable_row("OL", "ARRIVAL", "2026-11-24T12:00:00.000Z"),
    ]
    return digitraffic.normalize_departures([train(rows, **train_changes)], "KOK", STATION_NAMES)[0]


class TimetableTests(unittest.TestCase):
    """Aikataulut, asemien valinta ja puuttuvat kentät ovat ydintoimintoja."""

    def test_only_selected_station_departures_and_passenger_stops(self):
        rows = [
            timetable_row("KOK", "ARRIVAL"),
            timetable_row("TPE", "DEPARTURE"),
            timetable_row(commercialStop=False),
            timetable_row(trainStopping=False),
            timetable_row(time="2026-11-24T10:05:00Z"),
            timetable_row("OL", "ARRIVAL", "2026-11-24T12:00:00Z"),
        ]
        freight = train(number=9999, trainCategory="Cargo")
        actual = digitraffic.normalize_departures([train(rows), freight], "KOK", STATION_NAMES)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["train_number"], 23)
        self.assertEqual(datetime.fromisoformat(actual[0]["scheduled_time"]).minute, 5)

    def test_destination_is_last_passenger_arrival_not_depot(self):
        rows = [
            timetable_row("HKI", "ARRIVAL", "2026-11-24T08:00:00Z"),
            timetable_row(),
            timetable_row("OL", "ARRIVAL", "2026-11-24T12:00:00Z"),
            timetable_row("VARIKKO", "ARRIVAL", "2026-11-24T12:20:00Z", commercialStop=False),
        ]
        actual = digitraffic.normalize_departures([train(rows)], "KOK", STATION_NAMES)[0]
        self.assertEqual(actual["destination_code"], "OL")
        self.assertEqual(actual["destination"], "Oulu")

    def test_finland_winter_summer_and_midnight_are_converted(self):
        cases = [
            ("2026-01-15T22:30:00Z", "2026-01-16T00:30:00+02:00"),
            ("2026-07-15T22:30:00Z", "2026-07-16T01:30:00+03:00"),
        ]
        for utc, expected in cases:
            with self.subTest(utc=utc):
                actual = normalized(timetable_row(time=utc))
                self.assertEqual(datetime.fromisoformat(actual["scheduled_time"]), datetime.fromisoformat(expected))
                self.assertEqual(datetime.fromisoformat(actual["scheduled_time"]).isoformat(), expected)

    def test_delay_across_autumn_clock_change_uses_elapsed_minutes(self):
        # Suomessa kello palaa neljästä kolmeen. Junan viive on silti 10 minuuttia.
        actual = normalized(timetable_row(
            time="2026-10-25T00:55:00Z", liveEstimateTime="2026-10-25T01:05:00Z"
        ))
        self.assertEqual(actual["delay_minutes"], 10)
        self.assertEqual(datetime.fromisoformat(actual["scheduled_time"]).utcoffset(), timedelta(hours=3))
        self.assertEqual(datetime.fromisoformat(actual["display_time"]).utcoffset(), timedelta(hours=2))

    def test_actual_time_wins_over_estimate_and_reported_delay(self):
        actual = normalized(timetable_row(
            actualTime="2026-11-24T10:03:00Z", liveEstimateTime="2026-11-24T10:20:00Z", differenceInMinutes=20
        ))
        self.assertEqual(actual["time_kind"], "actual")
        self.assertEqual(actual["delay_source"], "actual")
        self.assertEqual(actual["delay_minutes"], 3)
        self.assertEqual(actual["display_time"], actual["actual_time"])
        early = normalized(timetable_row(actualTime="2026-11-24T09:58:00Z"))
        self.assertEqual(early["delay_minutes"], -2)

    def test_missing_estimate_is_unknown_not_automatically_on_time(self):
        actual = normalized()
        self.assertIsNone(actual["estimated_time"])
        self.assertIsNone(actual["display_time"])
        self.assertIsNone(actual["delay_minutes"])
        self.assertEqual(actual["time_kind"], "unavailable")
        # Pelkkä rajapinnan ilmoittama minuuttiero ei keksi puuttuvaa kellonaikaa.
        reported = normalized(timetable_row(differenceInMinutes=7))
        self.assertEqual(reported["delay_minutes"], 7)
        self.assertEqual(reported["delay_source"], "reported")
        self.assertIsNone(reported["display_time"])

    def test_unknown_delay_suppresses_unreliable_estimate(self):
        actual = normalized(timetable_row(
            unknownDelay=True, liveEstimateTime="2026-11-24T10:05:00Z", differenceInMinutes=5
        ))
        self.assertTrue(actual["unknown_delay"])
        self.assertIsNone(actual["display_time"])
        self.assertIsNone(actual["delay_minutes"])

    def test_train_and_stop_cancellation_do_not_show_delay(self):
        cases = [
            (timetable_row(liveEstimateTime="2026-11-24T10:05:00Z", cancelled=True), {}),
            (timetable_row(liveEstimateTime="2026-11-24T10:05:00Z"), {"cancelled": True}),
        ]
        for row, changes in cases:
            with self.subTest(changes=changes):
                actual = normalized(row, **changes)
                self.assertTrue(actual["cancelled"])
                self.assertIsNone(actual["display_time"])
                self.assertIsNone(actual["delay_minutes"])

    def test_malformed_optional_fields_do_not_hide_valid_departure(self):
        actual = normalized(timetable_row(actualTime="ei aikaleima", liveEstimateTime=None))
        self.assertEqual(actual["time_kind"], "unavailable")
        rows = [
            timetable_row(time="ei aikaleima"),
            timetable_row(time="2026-11-24T10:00:00Z"),
            timetable_row("OL", "ARRIVAL", "2026-11-24T12:00:00Z"),
        ]
        self.assertEqual(len(digitraffic.normalize_departures([train(rows)], "KOK", STATION_NAMES)), 1)
        for bad in (None, "", "ei aikaleima", {}, 42):
            with self.subTest(value=bad):
                self.assertIsNone(digitraffic.parse_timestamp(bad))

    def test_overdue_departure_and_same_number_on_other_date_are_retained(self):
        old = train([
            timetable_row(time="2020-01-01T10:00:00Z", liveEstimateTime="2020-01-01T10:20:00Z"),
            timetable_row("OL", "ARRIVAL", "2020-01-01T12:00:00Z"),
        ], departureDate="2020-01-01")
        other_day = train(departureDate="2026-11-24")
        actual = digitraffic.normalize_departures([other_day, old], "KOK", STATION_NAMES)
        self.assertEqual(len(actual), 2)
        self.assertEqual(actual[0]["delay_minutes"], 20)
        self.assertEqual([row["train_number"] for row in actual], [23, 23])


class ApiTests(unittest.TestCase):
    """Kokeile palvelimen oikeita reittejä ja korvaa vain ulkoinen verkkoyhteys."""

    def setUp(self):
        application.app.config.update(TESTING=True)
        self.client = application.app.test_client()
        # Aiemman testin välimuisti ei saa vaikuttaa seuraavan testin tulokseen.
        self.cache_patch = patch.dict(digitraffic._station_cache, {"names": None, "expires": 0.0})
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    @staticmethod
    def response(data, status=200):
        response = Mock()
        response.status_code = status
        response.json.return_value = data
        response.raise_for_status.return_value = None
        return response

    def test_station_allowlist_rejects_untrusted_input_before_network(self):
        with patch("digitraffic.requests.get") as network:
            for station in ("", "kok", "XYZ", "../metadata/stations", "https://example.com", "HKI?evil=1"):
                with self.subTest(station=station):
                    result = self.client.get("/api/departures", query_string={"station": station})
                    self.assertEqual(result.status_code, 400)
                    self.assertEqual(result.json["code"], "invalid_station")
            result = self.client.get("/api/departures?station=KOK&mode=unknown")
            self.assertEqual(result.status_code, 400)
            self.assertEqual(result.json["code"], "invalid_mode")
            network.assert_not_called()

    def test_http_get_uses_fixed_https_host_timeout_and_departure_filters(self):
        with patch("digitraffic.requests.get", return_value=self.response([])) as network:
            for station, name in STATION_NAMES.items():
                if station not in {"HKI", "TPE", "KOK"}:
                    continue
                with self.subTest(station=station):
                    result = self.client.get("/api/departures", query_string={"station": station})
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json["station"], {"code": station, "name": name})
                    self.assertEqual(result.json["source"], "live")
                    self.assertEqual(result.json["departures"], [])
                    args, kwargs = network.call_args
                    self.assertEqual(args[0], "https://rata.digitraffic.fi/api/v1/live-trains/station/" + station)
                    self.assertEqual(kwargs["params"]["departing_trains"], 10)
                    for key in ("arrived_trains", "arriving_trains", "departed_trains"):
                        self.assertEqual(kwargs["params"][key], 0)
                    self.assertEqual(kwargs["params"]["include_nonstopping"], "false")
                    self.assertEqual(set(kwargs["params"]["train_categories"].split(",")), {"Commuter", "Long-distance"})
                    self.assertTrue(all(value > 0 for value in kwargs["timeout"]))
                    self.assertFalse(kwargs["allow_redirects"])
                    self.assertNotEqual(kwargs.get("verify"), False)
                    self.assertEqual(result.headers["Cache-Control"], "no-store")

    def test_timeout_connection_and_http_errors_are_safe(self):
        private_details = "SECRET_INTERNAL_DETAIL traceback at /private/path.py"
        errors = [
            (requests.Timeout(private_details), 504, "upstream_timeout"),
            (requests.ConnectionError(private_details), 502, "upstream_unavailable"),
            (requests.HTTPError(private_details), 502, "upstream_unavailable"),
        ]
        for error, status, code in errors:
            with self.subTest(error=type(error).__name__), patch("digitraffic.requests.get", side_effect=error):
                result = self.client.get("/api/departures?station=KOK")
                self.assertEqual(result.status_code, status)
                self.assertEqual(result.json["code"], code)
                self.assertIn("error", result.json)
                self.assertNotIn(private_details, result.get_data(as_text=True))

    def test_invalid_json_wrong_top_level_and_redirect_are_errors_not_empty_boards(self):
        invalid_json = self.response(None)
        invalid_json.json.side_effect = ValueError("PRIVATE parser contents")
        cases = [invalid_json, self.response({"error": "upstream error"}), self.response([], status=302)]
        for response in cases:
            with self.subTest(response=response), patch("digitraffic.requests.get", return_value=response):
                result = self.client.get("/api/departures?station=KOK")
                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.json["code"], "upstream_unavailable")
                self.assertNotIn("departures", result.json)
                self.assertNotIn("PRIVATE", result.get_data(as_text=True))

    def test_metadata_failure_preserves_trains_with_code_and_warning(self):
        responses = [self.response([train()]), requests.Timeout("metadata unavailable")]
        with patch("digitraffic.requests.get", side_effect=responses):
            result = self.client.get("/api/departures?station=KOK")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json["departures"]), 1)
        self.assertEqual(result.json["departures"][0]["destination"], "OL")
        self.assertTrue(result.json["warning"])

    def test_metadata_names_are_used_and_cached_for_later_requests(self):
        stations = [{"stationShortCode": "OL", "stationName": "Oulu"}]
        responses = [self.response([train()]), self.response(stations), self.response([train()])]
        with patch("digitraffic.requests.get", side_effect=responses) as network:
            first = self.client.get("/api/departures?station=KOK")
            second = self.client.get("/api/departures?station=KOK")
        self.assertEqual(first.json["departures"][0]["destination"], "Oulu")
        self.assertEqual(second.json["departures"][0]["destination"], "Oulu")
        self.assertIsNone(second.json["warning"])
        self.assertEqual(network.call_count, 3)  # Junat kahdesti, asemien nimet kerran.

    def test_demo_empty_and_error_modes_never_use_live_network(self):
        with patch("digitraffic.requests.get") as network:
            for station in ("HKI", "TPE", "KOK"):
                with self.subTest(station=station):
                    result = self.client.get("/api/departures", query_string={"station": station, "mode": "demo"})
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json["source"], "demo")
                    self.assertTrue(result.json["departures"])
                    rows = result.json["departures"]
                    self.assertTrue(any(row["cancelled"] for row in rows))
                    self.assertTrue(any(row["time_kind"] == "actual" for row in rows))
                    self.assertTrue(any(row["time_kind"] == "unavailable" and not row["cancelled"] for row in rows))
                    self.assertTrue(any((row["delay_minutes"] or 0) > 0 for row in rows))
            empty = self.client.get("/api/departures?station=KOK&mode=empty")
            self.assertEqual(empty.status_code, 200)
            self.assertEqual(empty.json["departures"], [])
            self.assertEqual(empty.json["source"], "demo")
            error = self.client.get("/api/departures?station=KOK&mode=error")
            self.assertEqual(error.status_code, 503)
            self.assertEqual(error.json["code"], "demo_unavailable")
            network.assert_not_called()

    def test_unexpected_error_does_not_leak_traceback_and_has_safe_headers(self):
        private_details = "SECRET_INTERNAL_DETAIL /private/passwords.txt"
        with patch("app.get_departures", side_effect=RuntimeError(private_details)), patch.object(application.app.logger, "exception"):
            result = self.client.get("/api/departures?station=KOK")
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.json["code"], "internal_error")
        self.assertNotIn(private_details, result.get_data(as_text=True))
        self.assertEqual(result.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("script-src 'self'", result.headers["Content-Security-Policy"])
        self.assertFalse(application.app.debug)


if __name__ == "__main__":
    unittest.main()
