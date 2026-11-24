"""Digitrafficin hakeminen ja junien muuttaminen lähtötaulun JSON-tiedoiksi.

Tässä tiedostossa ei muodosteta HTML:ää. Näin samaa tietojen käsittelyä voidaan
testata erikseen sekä oikealla rajapintatiedolla että keksityllä demodatalla.
Dokumentaatio: https://www.digitraffic.fi/rautatieliikenne/
"""

from datetime import datetime
import logging
import math
from time import monotonic
from zoneinfo import ZoneInfo

import requests


# Käyttäjä valitsee vain asemakoodin. Hän ei voi antaa omaa palvelinosoitetta.
BASE_URL = "https://rata.digitraffic.fi/api/v1"
ALLOWED_STATIONS = {"HKI": "Helsinki", "TPE": "Tampere", "KOK": "Kokkola"}
FINLAND = ZoneInfo("Europe/Helsinki")
PASSENGER_CATEGORIES = {"Commuter", "Long-distance"}
TIMEOUT = (3.05, 8)  # Yhteyden muodostus enintään 3,05 s, lukemisen odotus 8 s.
HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip",  # requests purkaa gzip-vastauksen automaattisesti.
    "Digitraffic-User": "junalahtotaulu-opiskeluprojekti",
    "User-Agent": "Junalahtotaulu/1.0 (Flask educational application)",
}
logger = logging.getLogger(__name__)

# Asemien nimet muuttuvat harvoin. Tunnin välimuisti vähentää verkkopyyntöjä.
# Tämä välimuisti sisältää julkisia asematietoja, ei käyttäjän henkilötietoja.
_station_cache = {"names": None, "expires": 0.0}


class DigitrafficError(Exception):
    """Tunnettu rajapintavirhe, jonka sisäistä viestiä ei lähetetä selaimeen."""

    def __init__(self, reason="network"):
        self.reason = reason
        super().__init__(reason)


def validate_station(station_code):
    """Tarkista sallittu asema ennen verkkopyyntöä ja osoitteen muodostamista."""
    if not isinstance(station_code, str) or station_code not in ALLOWED_STATIONS:
        raise ValueError("Asemakoodi ei ole sallittujen asemien listassa.")
    return station_code


def parse_timestamp(value):
    """Lue ISO-aikaleima ja palauta Suomen aikavyöhykkeelle muutettu aika.

    Z tarkoittaa UTC-aikaa. ZoneInfo huomioi sekä talvi- että kesäajan,
    joten tuntien lisääminen käsin ei ole tarpeen. Puuttuva tai virheellinen
    valinnainen aikaleima palauttaa None eikä kaada koko lähtötaulua.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            # API:n aikaleimassa pitää olla aikavyöhyke. Sitä ei arvata.
            return None
        return parsed.astimezone(FINLAND)
    except (ValueError, OverflowError):
        return None


def _request_list(path, params=None):
    """Tee kiinteään HTTPS-rajapintaan GET-pyyntö ja tarkista JSON-lista."""
    try:
        response = requests.get(
            BASE_URL + path,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        # Uudelleenohjausta ei seurata toiselle palvelimelle.
        if 300 <= response.status_code < 400:
            raise DigitrafficError("http")
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as error:
        logger.warning("Digitraffic-pyynnön aikakatkaisu (%s).", path)
        raise DigitrafficError("timeout") from error
    except requests.HTTPError as error:
        logger.warning("Digitraffic palautti HTTP-virheen (%s).", path)
        raise DigitrafficError("http") from error
    except requests.exceptions.JSONDecodeError as error:
        logger.warning("Digitraffic palautti virheellistä JSON-tietoa (%s).", path)
        raise DigitrafficError("format") from error
    except requests.RequestException as error:
        logger.warning("Digitraffic-yhteys epäonnistui (%s).", path)
        raise DigitrafficError("network") from error
    except ValueError as error:
        logger.warning("Digitraffic ei palauttanut kelvollista JSON-tietoa (%s).", path)
        raise DigitrafficError("format") from error

    # Esimerkiksi API:n virheobjekti ei ole tyhjä lähtötaulu.
    if not isinstance(data, list):
        raise DigitrafficError("format")
    return data


def get_station_names():
    """Hae asemakoodien nimet; pelkkä nimihakemiston virhe ei estä lähtöjä."""
    cached = _station_cache["names"]
    if cached is not None and monotonic() < _station_cache["expires"]:
        return dict(cached), None

    try:
        stations = _request_list("/metadata/stations")
        names = {
            station["stationShortCode"]: station["stationName"]
            for station in stations
            if isinstance(station, dict)
            and isinstance(station.get("stationShortCode"), str)
            and isinstance(station.get("stationName"), str)
            and station["stationName"].strip()
        }
        if not names:
            raise DigitrafficError("format")
        # Valittavien asemien lyhyet, selkeät nimet ovat käyttöliittymän omat.
        names.update(ALLOWED_STATIONS)
        _station_cache.update(names=names, expires=monotonic() + 3600)
        return dict(names), None
    except DigitrafficError:
        # Mahdollinen aiempi nimihakemisto on edelleen käyttökelpoinen.
        names = dict(cached or ALLOWED_STATIONS)
        warning = (
            "Asemien kaikkia nimiä ei voitu päivittää. "
            "Osa määränpäistä voi näkyä asemakoodeina."
        )
        return names, warning


def _destination(rows, departure_index, station_names, cancelled):
    """Etsi reitin viimeinen matkustajapysähdys tämän lähdön jälkeen.

    Aikataulurivit ovat API:ssa reittijärjestyksessä. Viimeinen tekninen
    liikennepaikka tai varikko ei siksi automaattisesti ole matkustajan määränpää.
    Perutusta junasta näytetään suunniteltu määränpää. Muusta junasta ohitetaan
    perutut loppumatkan pysähdykset, jos jäljellä on käytössä oleva määränpää.
    """
    candidates = [
        row for row in rows[departure_index + 1:]
        if isinstance(row, dict)
        and row.get("type") == "ARRIVAL"
        and row.get("trainStopping") is True
        and row.get("commercialStop") is not False
        and isinstance(row.get("stationShortCode"), str)
    ]
    if not cancelled:
        candidates = [row for row in candidates if row.get("cancelled") is not True]
    if not candidates:
        return "Määränpää ei tiedossa", ""
    code = candidates[-1]["stationShortCode"]
    return station_names.get(code, code), code


def _minutes_between(later, scheduled):
    """Pyöristä aikaero lähimpään minuuttiin, myös etuajassa lähteneelle."""
    # UTC-hetkien erotus toimii myös silloin, kun kello siirtyy kesäajan
    # päättyessä takaisin. Paikallisten kellonaikojen erotus olisi silloin väärä.
    seconds = later.timestamp() - scheduled.timestamp()
    minutes = math.floor(abs(seconds) / 60 + 0.5)
    return minutes if seconds >= 0 else -minutes


def normalize_departures(trains, station_code, station_names):
    """Muunna junien timeTableRows-rivit enintään kymmeneksi lähtöriviksi.

    Rajapinta rajaa haun seuraavaksi lähteviin juniin. Tässä ei poisteta riviä
    vain menneen aikatauluajan perusteella: myöhästynyt juna voi yhä odottaa
    lähtöä. Mahdollinen toteutunut lähtö näytetään toteumana, ei ennusteena.
    """
    validate_station(station_code)
    if not isinstance(trains, list):
        raise DigitrafficError("format")

    departures = []
    seen = set()
    for train in trains:
        if not isinstance(train, dict) or train.get("deleted") is True:
            continue
        # Parametrirajauksen lisäksi tarkistetaan palautetun junan luokka.
        if train.get("trainCategory") not in PASSENGER_CATEGORIES:
            continue
        number = train.get("trainNumber")
        if not isinstance(number, int) or isinstance(number, bool):
            continue
        rows = train.get("timeTableRows")
        if not isinstance(rows, list):
            continue

        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            if row.get("stationShortCode") != station_code or row.get("type") != "DEPARTURE":
                continue
            if row.get("trainStopping") is not True or row.get("commercialStop") is False:
                continue
            scheduled = parse_timestamp(row.get("scheduledTime"))
            if scheduled is None:
                # Ilman aikataulua ei voida muodostaa luotettavaa lähtöriviä.
                continue
            departure_date = train.get("departureDate")
            if not isinstance(departure_date, str):
                departure_date = ""
            key = (number, departure_date, scheduled.isoformat())
            if key in seen:
                continue
            seen.add(key)

            cancelled = train.get("cancelled") is True or row.get("cancelled") is True
            actual = parse_timestamp(row.get("actualTime"))
            estimated = parse_timestamp(row.get("liveEstimateTime"))
            unknown_delay = row.get("unknownDelay") is True and actual is None and not cancelled
            display_time, time_kind, delay, delay_source = None, "unavailable", None, None

            if cancelled:
                # Perutulle lähdölle ei luvata lähtöaikaa tai lasketa myöhästymistä.
                actual, estimated = None, None
            elif actual is not None:
                display_time, time_kind = actual, "actual"
                delay, delay_source = _minutes_between(actual, scheduled), "actual"
            elif unknown_delay:
                # Liikenteenohjaus on merkinnyt ennusteen epäluotettavaksi.
                estimated = None
            elif estimated is not None:
                display_time, time_kind = estimated, "estimate"
                delay, delay_source = _minutes_between(estimated, scheduled), "estimate"
            else:
                # Valinnainen ennuste saa puuttua. Minuuttitieto voi silti olla
                # saatavilla, mutta siitä ei keksitä kellonaikaennustetta.
                reported = row.get("differenceInMinutes")
                if isinstance(reported, int) and not isinstance(reported, bool):
                    delay, delay_source = reported, "reported"

            destination, destination_code = _destination(rows, index, station_names, cancelled)
            track = row.get("commercialTrack")
            if not isinstance(track, (str, int)) or isinstance(track, bool):
                track = None
            departures.append({
                "train_number": number,
                "train_type": train.get("trainType") if isinstance(train.get("trainType"), str) else "Juna",
                "commuter_line": (
                    train.get("commuterLineID") or None
                    if isinstance(train.get("commuterLineID"), str) else None
                ),
                "destination": destination,
                "destination_code": destination_code,
                "scheduled_time": scheduled.isoformat(),
                "estimated_time": estimated.isoformat() if estimated else None,
                "actual_time": actual.isoformat() if actual else None,
                "display_time": display_time.isoformat() if display_time else None,
                "time_kind": time_kind,
                "delay_minutes": delay,
                "delay_source": delay_source,
                "unknown_delay": unknown_delay,
                "track": str(track) if track is not None and str(track) else None,
                "cancelled": cancelled,
            })

    # Järjestetään aikataulun mukaan. ISO-merkkijonon sijaan verrataan oikeita
    # aikoja; tämä toimii myös syksyn kesäaikasiirtymän kahdella 03-tunnilla.
    departures.sort(key=lambda item: datetime.fromisoformat(item["scheduled_time"]).timestamp())
    return departures[:10]


def get_departures(station_code):
    """Hae oikeat junat ja palauta (lähtörivit, mahdollinen nimivaroitus)."""
    validate_station(station_code)
    trains = _request_list(
        f"/live-trains/station/{station_code}",
        params={
            "arrived_trains": 0,
            "arriving_trains": 0,
            "departed_trains": 0,
            "departing_trains": 10,
            "include_nonstopping": "false",
            "train_categories": "Commuter,Long-distance",
        },
    )
    if not trains:
        return [], None
    names, warning = get_station_names()
    return normalize_departures(trains, station_code, names), warning
