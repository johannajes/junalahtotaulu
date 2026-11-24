"""Keksitty esimerkkiaineisto, joka ei kuvaa oikeaa junaliikennettä.

Rakenne jäljittelee Digitrafficin JSON-vastausta. Esimerkit kulkevat samojen
suodatus- ja aikamuunnosfunktioiden läpi kuin oikeat junatiedot.
"""

from datetime import datetime, timedelta, timezone

from digitraffic import ALLOWED_STATIONS, validate_station


DEMO_STATION_NAMES = {
    **ALLOWED_STATIONS,
    "OL": "Oulu",
    "ROI": "Rovaniemi",
    "TKU": "Turku",
    "JY": "Jyväskylä",
}


def make_demo_trains(station_code, now=None):
    """Luo toimiva lähtötaulu myös ilman verkkoyhteyttä; ajat ovat esimerkkejä."""
    validate_station(station_code)
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc).replace(second=0, microsecond=0)

    def timestamp(value):
        return value.isoformat().replace("+00:00", "Z")

    # Sama rakenne näyttää viiveen, ajallaan kulun, puuttuvan ennusteen,
    # perumisen, toteutuneen lähdön ja epävarman myöhästymisen.
    examples = [
        {"number": 42, "offset": -8, "actual": 6, "destination": "HKI"},
        {"number": 27, "offset": 7, "estimate": 12, "destination": "OL"},
        {"number": 50, "offset": 20, "estimate": 0, "destination": "HKI"},
        {"number": 65, "offset": 35, "destination": "ROI"},
        {"number": 48, "offset": 50, "cancelled": True, "destination": "TPE"},
        {"number": 29, "offset": 70, "unknown": True, "destination": "OL"},
    ]
    trains = []
    for index, example in enumerate(examples):
        scheduled = now + timedelta(minutes=example["offset"])
        destination = example["destination"]
        if destination == station_code:
            destination = "TPE" if station_code != "TPE" else "HKI"
        departure = {
            "stationShortCode": station_code,
            "type": "DEPARTURE",
            "trainStopping": True,
            "commercialStop": True,
            "commercialTrack": str(index % 3 + 1),
            "scheduledTime": timestamp(scheduled),
            "cancelled": example.get("cancelled", False),
        }
        if "estimate" in example:
            departure["liveEstimateTime"] = timestamp(scheduled + timedelta(minutes=example["estimate"]))
            departure["differenceInMinutes"] = example["estimate"]
        if "actual" in example:
            departure["actualTime"] = timestamp(scheduled + timedelta(minutes=example["actual"]))
            departure["differenceInMinutes"] = example["actual"]
        if example.get("unknown"):
            departure["unknownDelay"] = True
            # Tahallaan vanhentunut ennuste: unknownDelayn pitää estää sen käyttö.
            departure["liveEstimateTime"] = timestamp(scheduled + timedelta(minutes=15))
            departure["differenceInMinutes"] = 15
        trains.append({
            "trainNumber": example["number"],
            "trainType": "IC",
            "trainCategory": "Long-distance",
            "departureDate": scheduled.date().isoformat(),
            "cancelled": example.get("cancelled", False),
            "timeTableRows": [
                departure,
                {
                    "stationShortCode": destination,
                    "type": "ARRIVAL",
                    "trainStopping": True,
                    "commercialStop": True,
                    "scheduledTime": timestamp(scheduled + timedelta(hours=3)),
                    "cancelled": example.get("cancelled", False),
                },
            ],
        })
    return trains
