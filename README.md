# Junalähtötaulu – Python ja Flask

Selainkäyttöinen harjoitussovellus näyttää Helsingin, Tampereen ja Kokkolan lähteviä matkustajajunia. Käyttäjä valitsee aseman, hakee lähdöt ja vertaa aikataulua ennusteeseen tai toteutuneeseen lähtöön. Tiedot haetaan Fintrafficin Digitraffic-rajapinnasta.

Sovelluksessa on myös erilliset, selvästi merkityt esimerkkitilat lähtötaulun, tyhjän tuloksen ja yhteysvirheen esittelyyn. Esimerkkien junat ja ajat ovat keksittyjä. Niitä ei käytetä automaattisesti verkkoyhteyden epäonnistuessa.

## 1. Käynnistä Macissa

Tarvitset Python 3.10:n tai uudemman, selaimen ja internetyhteyden kirjastojen asennukseen sekä oikeiden junatietojen hakemiseen. VS Code helpottaa tiedostojen tarkastelua. Jos Python on jo asennettu, sitä ei tarvitse asentaa uudelleen.

1. Pura ZIP-tiedosto kaksoisklikkaamalla sitä Finderissa.
2. Avaa VS Code. Valitse **File → Open Folder…** ja avaa `junalahtotaulu`-kansio. Oikeassa kansiossa näkyvät esimerkiksi `app.py` ja `requirements.txt`.
3. Valitse VS Codessa **Terminal → New Terminal**. Kirjoita seuraavat komennot alareunaan avautuvaan terminaaliin yksi kerrallaan. Paina jokaisen jälkeen Enter.

Tarkista ensin Python:

```bash
python3 --version
```

Luo projektin oma virtuaaliympäristö:

```bash
python3 -m venv .venv
```

Virtuaaliympäristö on projektin oma kirjastokansio. Sen avulla tämän sovelluksen kirjastot pysyvät erillään muiden projektien kirjastoista. Aktivoi se:

```bash
source .venv/bin/activate
```

Terminaalin rivin alkuun tulee yleensä `(.venv)`. Asenna sovelluksen tarvitsemat kirjastot:

```bash
python -m pip install -r requirements.txt
```

Käynnistä palvelin:

```bash
python app.py
```

Pidä terminaali auki. Avaa Safarissa tai muussa selaimessa osoite **http://127.0.0.1:5001**. Tämä osoite tarkoittaa omalla koneellasi toimivaa sovellusta. HTML-tiedostoa ei avata erikseen Finderista, koska käyttöliittymä tarvitsee Flask-palvelimen.

Pysäytä sovellus klikkaamalla terminaalia ja painamalla **Control + C**. Macissa tämä on Control-näppäin, ei Command.

Seuraavalla käyttökerralla avaa sama kansio ja terminaali. Kirjastoja ei tarvitse asentaa uudelleen:

```bash
source .venv/bin/activate
python app.py
```

## 2. Käyttötapaus: Kokkolan lähdöt

1. Valitse asemaksi **Kokkola (KOK)**.
2. Paina **Hae lähdöt**.
3. Tarkastele lähtötaulusta junan numeroa, määränpäätä, aikataulun mukaista aikaa, arviota tai toteumaa ja myöhästymistä minuutteina.
4. Vertaa aikataulua arvioon. Esimerkiksi **keksityssä laskuesimerkissä** aikataulu on 10.00 ja arvio 10.12. Myöhästyminen on silloin **+12 minuuttia**. Tämä ei ole oikean junan tämänhetkinen aikataulu.

Kaikki kellonajat näytetään Suomen ajassa. Toteutunut aika erotetaan ennusteesta. Jos ennustetta ei ole saatavilla, näkyviin tulee tieto puuttuvasta arviosta. Puuttuvaa aikaa ei korvata keksityllä ennusteella. Onnistuneen reaaliaikaisen haun jälkeen tiedot päivittyvät 60 sekunnin välein, kun sivu on näkyvissä. Virheen jälkeen voit yrittää uudelleen painikkeesta.

### Kokeile tyhjää tulosta ja yhteysvirhettä

Avaa käyttöliittymän **Kokeile esimerkkitilanteita** -osio. Painikkeet ovat **Lähtötaulu**, **Ei junia** ja **Yhteysvirhe**. Näin voit esitellä tilanteet ilman oikean liikenteen muuttamista tai internetyhteyden katkaisemista. Palaa sen jälkeen reaaliaikaisiin tietoihin painikkeesta **Näytä oikeat lähdöt**.

Esimerkkilähdöt sisältävät muun muassa myöhästyneen, lähteneen ja perutun junan sekä tilanteen, jossa arvio puuttuu. Tyhjä tulos tarkoittaa onnistunutta hakua ilman näytettäviä lähtöjä. Yhteysvirhe tarkoittaa epäonnistunutta hakua; sitä ei esitetä tyhjänä lähtötauluna.

## 3. Mitä tiedostot tekevät?

| Tiedosto | Tehtävä |
| --- | --- |
| `ALOITA_TASTA.txt` | Lyhyt käynnistysohje. |
| `README.md` | Tämä laajempi käyttö- ja toteutusohje. |
| `app.py` | Flask-palvelin, verkkosivun tarjoaminen ja oman JSON-rajapinnan reitit. |
| `digitraffic.py` | HTTP-haut, asematiedot, aikataulurivien käsittely ja aikamuunnokset. |
| `demo_data.py` | Keksityt esimerkkijunat, jotka käsitellään samalla logiikalla kuin oikeat tiedot. |
| `templates/index.html` | Sivun rakenne, asemavalinta ja lähtötaulun paikka. |
| `static/style.css` | Värit, taulukon ulkoasu ja pienen näytön asettelu. |
| `static/app.js` | Painikkeet, tiedonhaku selaimesta ja tulosten näyttäminen. |
| `tests/test_app.py` | Automaattiset tarkistukset aikatauluille, virheille ja rajauksille. |
| `requirements.txt` | Asennettavat Python-kirjastot ja tässä projektissa käytetyt versiot. |
| `.gitignore` | Estää esimerkiksi virtuaaliympäristön ja tilapäistiedostojen lisäämisen Gitiin. |

Koodin suomenkieliset kommentit selittävät käsittelyvaiheita ja valintojen syitä. Aloita lukeminen `app.py`-tiedostosta ja siirry sitten `digitraffic.py`-tiedostoon.

## 4. Miten tieto kulkee?

Selain lähettää **HTTP GET** -pyynnön oman Flask-palvelimen osoitteeseen:

```text
/api/departures?station=KOK&mode=live
```

Flask tarkistaa asemakoodin. Sitten Python tekee GET-pyynnön Digitrafficiin. Helsinkiä koskeva haku näyttää tältä:

```text
https://rata.digitraffic.fi/api/v1/live-trains/station/HKI?arrived_trains=0&arriving_trains=0&departed_trains=0&departing_trains=10&include_nonstopping=false&train_categories=Commuter,Long-distance
```

Asemien nimet haetaan osoitteesta:

```text
https://rata.digitraffic.fi/api/v1/metadata/stations
```

Digitraffic palauttaa JSON-tietoa. Python poimii siitä lähtötaulun tarvitseman osan ja palauttaa selaimelle oman JSON-vastauksen. JavaScript muodostaa vastauksesta taulukon. HTML antaa rakenteen ja CSS ulkoasun. Reactia ei tarvita tässä toteutuksessa.

## 5. Aikataulujen käsittely

Sallitut asemat ovat **HKI = Helsinki**, **TPE = Tampere** ja **KOK = Kokkola**. Tarkistus tehdään palvelimella, joten pelkkä selaimen valikon ohittaminen ei mahdollista muiden osoitteiden hakemista.

Junan `timeTableRows`-listasta valitaan käyttäjän aseman `DEPARTURE`-rivit. Saapumiset, läpiajot, selvästi ei-kaupalliset pysähdykset ja tavarajunat jätetään pois. Tulokset järjestetään aikataulun mukaiseen lähtöjärjestykseen, ja näytettäviä rivejä on enintään kymmenen. Mennyt aikatauluaika ei yksin poista junaa: se voi olla yhä lähdössä myöhässä.

| API-kenttä | Käyttö sovelluksessa |
| --- | --- |
| `trainNumber` | Junan numero. |
| `stationShortCode` | Aseman tunnistaminen ja nimen hakeminen. |
| `scheduledTime` | Aikataulun mukainen lähtöaika. |
| `actualTime` | Toteutunut lähtö; käytetään ensisijaisesti. |
| `liveEstimateTime` | Ennuste, jos toteumaa ei vielä ole. |
| `differenceInMinutes` | Ilmoitettu minuuttiero, jos kellonaika-arviota tai toteumaa ei ole. |
| `unknownDelay` | Myöhästymisen määrää ei tunneta luotettavasti. |
| `cancelled` | Junan tai yksittäisen lähdön peruminen. |

Kun toteuma tai kelvollinen ennuste löytyy, minuuttiero lasketaan suhteessa aikatauluun ja pyöristetään lähimpään minuuttiin. Negatiivinen luku tarkoittaa etuajassa olevaa lähtöä. Jos käytössä on vain `differenceInMinutes`, kellonaika-arviota ei johdeta siitä. Pelkkä ilmoitettu nolla ilman arviota tai toteumaa ei ole varma tieto aikataulussa kulkemisesta. `unknownDelay` estää epäluotettavan ennusteen käyttämisen. Perutulle lähdölle ei luvata lähtöaikaa eikä näytetä laskettua viivettä.

Määränpää päätellään lähdön jälkeisestä viimeisestä matkustajille tarkoitetusta saapumispysähdyksestä. Tämä on harjoitussovelluksen käytännöllinen tulkinta. Digitrafficin dokumentaatiossa mainitaan, että osittain perutulla reitillä kaupallisen pysähdyksen merkintä voi olla epätarkka. Tällaisessa poikkeustilanteessa päätelty määränpää voi poiketa matkustajainformaatiosta. [Digitrafficin dokumentaatio](https://www.digitraffic.fi/rautatieliikenne/)

API:n UTC-ajat muunnetaan `ZoneInfo("Europe/Helsinki")`-aikavyöhykkeelle. Kesä- ja talviaika vaihtuvat aikavyöhyketiedon mukaan. Aikaero lasketaan aikaleimojen todellisesta erotuksesta, joten myös syksyn taaksepäin siirtyvä tunti käsitellään oikein. [Pythonin ZoneInfo-ohje](https://docs.python.org/3/library/zoneinfo.html)

## 6. Virhetilanteet ja turvallisuus

Verkkopyynnöt käyttävät kiinteää HTTPS-osoitetta ja TLS-varmenteiden tarkistusta. Yhteyden muodostukselle on 3,05 sekunnin ja lukemisen odotukselle 8 sekunnin aikakatkaisu. Nämä ovat verkkopyynnön eri odotusrajoja, eivät koko hakuketjun yhteinen kahdeksan sekunnin enimmäisaika. Uudelleenohjauksia ei seurata.

HTTP-virheet, yhteyskatkot ja virheellinen JSON tuottavat käyttäjälle ymmärrettävän yleisviestin. Sisäistä poikkeusta tai Pythonin virheketjua ei lähetetä selaimeen. Jos vain asemien nimihaku epäonnistuu, junat voidaan näyttää edelleen: joitakin määränpäitä näytetään asemakoodeina ja käyttäjä saa tästä huomautuksen. Onnistuneet asematiedot säilytetään palvelimen muistissa tunnin ajan.

JavaScript lisää API:n tekstit sivulle tekstinä. Sivun selainrajaukset sallivat ohjelmakoodin lataamisen sovelluksen omasta osoitteesta. Sovellus ei tarvitse API-avainta eikä käyttäjän kirjautumistietoja. Flask käynnistyy vain oman koneen osoitteeseen ja debug-tila on pois.

## 7. Tarkistukset ja rajaukset

Suorita testit projektikansiossa aktivoidussa virtuaaliympäristössä:

```bash
python -m unittest discover -s tests -v
```

Projektin **18 testiä läpäisivät tarkistuksen Python 3.12 -ympäristössä**. Testit kattavat esimerkiksi asemarajauksen, lähtöjen suodatuksen, puuttuvan ennusteen, perumisen, kesäajan muutoksen, verkkovirheet, turvalliset virheviestit ja esimerkkitilat. Ulkoiset verkkopyynnöt korvataan testeissä hallituilla vastauksilla, joten testit toimivat ilman internetyhteyttä.

Selaimessa tarkistettiin lisäksi kaikkien kolmen aseman esimerkkilähtötaulut, aseman vaihtamisen vaikutus, tyhjä tulos ja yhteysvirheilmoitus. JavaScriptin syntaksitarkistus onnistui. Ulkoasu sisältää pienen näytön asettelun; erillistä mobiiliselaintestausta ei tehty.

**Oikean Digitraffic-yhteyden toimintaa ei saatu tässä valmisteluympäristössä vahvistettua:** koekysely päättyi aikakatkaisuun. Läpäisseet testit eivät tarkoita, että tämänhetkiset oikeat junatiedot olisi tarkistettu. Kokeile reaaliaikainen Kokkola-haku omalla koneellasi.

Digitrafficin lukumäärähaun aikahorisontti on aikataulun perusteella 24 tuntia molempiin suuntiin. Siksi seuraavia lähtöjä voi löytyä alle kymmenen. Koska haussa `departed_trains=0`, toteutuneita lähtöjä näkyy tavallisesti vähän tai ei lainkaan; toteuman esitystapaa voi kokeilla esimerkeillä. [Rajapinnan kuvaus](https://www.digitraffic.fi/rautatieliikenne/)

Sovellus on paikallinen oppimisprojekti. Julkinen verkkopalvelu tarvitsee erikseen sille sopivan palvelinympäristön ja ylläpidon; mukana oleva Flask-käynnistys on tarkoitettu omalla koneella työskentelyyn.

## 8. Tavalliset käynnistysongelmat

- **`No module named flask` tai `requests`:** aktivoi `.venv` ja suorita kirjastojen asennuskomento uudelleen.
- **`can't open file 'app.py'`:** terminaali on väärässä kansiossa. Avaa VS Codessa kansio, jonka sisällä `app.py` näkyy, ja avaa uusi terminaali.
- **Selaimeen ei tule sivua:** varmista, että `python app.py` on edelleen käynnissä, ja käytä täsmälleen osoitetta `http://127.0.0.1:5001`.
- **Portti on jo käytössä:** pysäytä aiempi sovellus sen terminaalissa Control + C:llä ja käynnistä uudelleen.
- **Junatietoja ei saada:** kokeile esimerkkitiloja ja yritä oikeaa hakua myöhemmin. Älä poista TLS-varmenteiden tarkistusta ongelman kiertämiseksi.

## Lähteet

- [Digitraffic: rautatieliikenteen rajapinta](https://www.digitraffic.fi/rautatieliikenne/)
- [Digitraffic: Swagger](https://rata.digitraffic.fi/swagger/)
- [Flask: asennus ja virtuaaliympäristö](https://flask.palletsprojects.com/en/stable/installation/)
- [Python: ZoneInfo-aikavyöhykkeet](https://docs.python.org/3/library/zoneinfo.html)

Junatietojen lähde on **Fintraffic / Digitraffic**. Esimerkkitilojen aineisto on tämän projektin omaa keksittyä testiaineistoa.
