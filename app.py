"""Flask-palvelin: selain pyytää lähtöjä, Python hakee ne Digitrafficista.

Käynnistä: python app.py
Avaa sen jälkeen selaimessa: http://127.0.0.1:5001
"""

from datetime import datetime
import logging

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from demo_data import DEMO_STATION_NAMES, make_demo_trains
from digitraffic import (
    ALLOWED_STATIONS,
    FINLAND,
    DigitrafficError,
    get_departures,
    normalize_departures,
)


app = Flask(__name__)
app.json.ensure_ascii = False  # Ä ja ö säilyvät JSON-vastauksessa luettavina.


@app.after_request
def security_headers(response):
    """Selaimen tulee ladata ohjelmakoodi vain tämän sovelluksen sisältä."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.path.startswith("/api/"):
        # Lähtötaulun JSON ei saa jäädä selaimen HTTP-välimuistiin.
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    """Lähetä selaimelle käyttöliittymä ja sallittujen asemien valinnat."""
    stations = [{"code": code, "name": name} for code, name in ALLOWED_STATIONS.items()]
    return render_template("index.html", stations=stations)


@app.get("/api/departures")
def api_departures():
    """Oman sovelluksen GET-rajapinta, jota selaimen JavaScript käyttää."""
    station_code = request.args.get("station", "KOK")
    mode = request.args.get("mode", "live")

    # Tarkistus tehdään myös palvelimella: HTML-valikko yksin ei suojaa API:a.
    if station_code not in ALLOWED_STATIONS:
        return jsonify(error="Valitse asema Helsinki, Tampere tai Kokkola.", code="invalid_station"), 400
    if mode not in {"live", "demo", "empty", "error"}:
        return jsonify(error="Valittu näkymä ei ole käytettävissä.", code="invalid_mode"), 400

    # Esimerkkitilat ovat käyttäjän erikseen valitsemia. Verkkovirhettä ei
    # peitetä vaihtamalla oikeita aikatauluja automaattisesti keksittyihin.
    if mode == "error":
        return jsonify(
            error="Esimerkkitilanne: yhteys junatietoihin epäonnistui. Yritä uudelleen.",
            code="demo_unavailable",
        ), 503
    warning = None
    if mode == "empty":
        departures = []
    elif mode == "demo":
        departures = normalize_departures(
            make_demo_trains(station_code), station_code, DEMO_STATION_NAMES
        )
    else:
        try:
            departures, warning = get_departures(station_code)
        except DigitrafficError as error:
            if error.reason == "timeout":
                return jsonify(
                    error="Junatietojen hakeminen kesti liian kauan. Yritä hetken kuluttua uudelleen.",
                    code="upstream_timeout",
                ), 504
            return jsonify(
                error="Junatietoja ei saatu haettua. Tarkista verkkoyhteys ja yritä uudelleen.",
                code="upstream_unavailable",
            ), 502

    return jsonify(
        station={"code": station_code, "name": ALLOWED_STATIONS[station_code]},
        departures=departures,
        fetched_at=datetime.now(FINLAND).isoformat(),
        source="live" if mode == "live" else "demo",
        mode=mode,
        warning=warning,
    )


@app.errorhandler(Exception)
def unexpected_error(error):
    """Lokita ylläpitäjälle; käyttäjä saa vain turvallisen yleisviestin."""
    if isinstance(error, HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(error="Pyydettyä toimintoa ei löytynyt.", code="request_error"), error.code
        return error
    app.logger.exception("Odottamaton sovellusvirhe")
    if request.path.startswith("/api/"):
        return jsonify(error="Tietojen näyttäminen epäonnistui. Yritä uudelleen.", code="internal_error"), 500
    return "Sovellusta ei saatu avattua. Yritä hetken kuluttua uudelleen.", 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Paikallinen harjoitussovellus: vain oma kone, ei julkista kehityspalvelinta.
    # Debug on pois, jotta sisäisiä virheitä tai Python-debuggeria ei näytetä.
    app.run(host="127.0.0.1", port=5001, debug=False)
