"use strict";

// Selain pyytää tietoja vain omalta Flask-palvelimelta. Varsinainen
// Digitraffic-pyyntö, asemavalinnan tarkistus ja JSON-käsittely tehdään Pythonissa.
const ui = {
  form: document.querySelector("#station-form"),
  station: document.querySelector("#station"),
  search: document.querySelector("#search-button"),
  board: document.querySelector("#board"),
  title: document.querySelector("#board-title"),
  code: document.querySelector("#station-code"),
  dataLabel: document.querySelector("#data-label"),
  updatedAt: document.querySelector("#updated-at"),
  warning: document.querySelector("#metadata-warning"),
  announcement: document.querySelector("#announcement"),
  statePanel: document.querySelector("#state-panel"),
  stateSymbol: document.querySelector("#state-symbol"),
  stateTitle: document.querySelector("#state-title"),
  stateMessage: document.querySelector("#state-message"),
  retry: document.querySelector("#retry-button"),
  tableWrap: document.querySelector("#table-wrap"),
  body: document.querySelector("#departures-body"),
  demoBanner: document.querySelector("#demo-banner"),
  backToLive: document.querySelector("#back-to-live"),
  clock: document.querySelector("#clock-time"),
  exampleButtons: [...document.querySelectorAll("[data-mode]")],
  refreshNote: document.querySelector("#refresh-note"),
};

const REFRESH_INTERVAL = 60_000;
const FETCH_TIMEOUT = 25_000;
const ALLOWED_MODES = new Set(["live", "demo", "empty", "error"]);
const state = { mode: "live", controller: null, requestId: 0, refreshTimer: null };

// Selaimen oma aikavyöhyke ei vaikuta lähtötauluun. Europe/Helsinki
// huomioi automaattisesti sekä kesäajan että talviajan.
const timeFormatter = new Intl.DateTimeFormat("fi-FI", {
  timeZone: "Europe/Helsinki", hour: "2-digit", minute: "2-digit",
});
const dateFormatter = new Intl.DateTimeFormat("fi-FI", {
  timeZone: "Europe/Helsinki", weekday: "short", day: "numeric", month: "numeric",
});
const dateKeyFormatter = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Europe/Helsinki", year: "numeric", month: "2-digit", day: "2-digit",
});

function validDate(value) {
  if (typeof value !== "string" || !value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function showTime(value) {
  const date = validDate(value);
  return date ? timeFormatter.format(date) : "—";
}

function showDate(value) {
  const date = validDate(value);
  return date ? dateFormatter.format(date) : "Päivä ei tiedossa";
}

function updateClock() {
  const now = new Date();
  ui.clock.textContent = timeFormatter.format(now);
  ui.clock.dateTime = now.toISOString();
}

function selectedStation() {
  const option = ui.station.selectedOptions[0];
  return {
    code: ui.station.value,
    name: option.textContent.replace(/\s*\([A-Z]+\)$/, ""),
  };
}

// Ulkoa saatu teksti asetetaan aina textContent-arvoksi. Näin API:n tekstiä
// ei koskaan tulkita HTML-koodina, vaikka siinä olisi esimerkiksi <script>.
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function makeCell(label, className = "") {
  const cell = element("td", className);
  cell.dataset.label = label;
  return cell;
}

function appendTime(cell, timestamp, note, extraClass = "") {
  const date = validDate(timestamp);
  const time = element(date ? "time" : "span", `cell-main cell-time ${extraClass}`, showTime(timestamp));
  if (date) time.dateTime = timestamp;
  cell.append(time, element("span", "cell-note", note));
}

function delayPresentation(train) {
  if (train.cancelled) return { text: "Peruttu", note: "Lähtö on peruttu", tone: "cancelled" };
  if (train.unknown_delay && train.time_kind !== "actual") {
    return { text: "Myöhässä", note: "Arvio puuttuu", tone: "late" };
  }
  const delay = train.delay_minutes;
  if (typeof delay !== "number" || !Number.isFinite(delay)) {
    return { text: "—", note: "Ei viivetietoa", tone: "unknown" };
  }
  const reported = train.delay_source === "reported";
  if (delay > 0) return { text: `+${delay} min`, note: reported ? "Ilmoitettu viive" : "Myöhässä", tone: "late" };
  if (delay < 0) return { text: `−${Math.abs(delay)} min`, note: reported ? "Ilmoitettu ero" : "Etuajassa", tone: "early" };
  // Puuttuvasta ennusteesta ei päätellä, että juna kulkisi ajallaan.
  return { text: "0 min", note: reported ? "Ilmoitettu ero" : "Aikataulussa", tone: reported ? "unknown" : "ontime" };
}

function departureRow(train) {
  const row = document.createElement("tr");
  const trainCell = makeCell("Juna", "train-cell");
  const identity = element("span", "train-identity");
  const type = element("span", "train-type", train.commuter_line || train.train_type || "Juna");
  type.dataset.commuter = String(Boolean(train.commuter_line));
  identity.append(type, element("span", "train-number", train.train_number ?? "—"));
  trainCell.append(identity);

  const destinationCell = makeCell("Määränpää", "destination-cell");
  destinationCell.append(element("span", "cell-main destination-name", train.destination || train.destination_code || "Ei tiedossa"));

  const scheduledCell = makeCell("Aikataulu");
  appendTime(scheduledCell, train.scheduled_time, showDate(train.scheduled_time), train.cancelled ? "is-cancelled" : "");

  const displayCell = makeCell("Arvio / toteuma");
  const displayDate = validDate(train.display_time);
  if (train.cancelled) {
    displayCell.append(element("span", "cell-main no-estimate", "—"), element("span", "cell-note", "Ei lähtöä"));
  } else if ((train.unknown_delay && train.time_kind !== "actual") || !displayDate || train.time_kind === "unavailable") {
    displayCell.append(element("span", "cell-main no-estimate", "Ei arviota"));
  } else {
    let note = train.time_kind === "actual" ? "Lähtenyt" : "Arvio";
    const scheduledDate = validDate(train.scheduled_time);
    if (!scheduledDate || dateKeyFormatter.format(displayDate) !== dateKeyFormatter.format(scheduledDate)) {
      note += ` · ${showDate(train.display_time)}`;
    }
    appendTime(displayCell, train.display_time, note, train.delay_minutes > 0 ? "is-delayed" : "");
  }

  const delayCell = makeCell("Myöhästyminen");
  const presentation = delayPresentation(train);
  const badge = element("span", "delay-badge", presentation.text);
  badge.dataset.tone = presentation.tone;
  delayCell.append(badge, element("span", "cell-note", presentation.note));

  const trackCell = makeCell("Raide", "track-cell");
  const trackKnown = train.track !== null && train.track !== undefined && String(train.track).trim() !== "";
  trackCell.append(element("span", trackKnown ? "track-number" : "track-unknown", trackKnown ? train.track : "—"));

  row.append(trainCell, destinationCell, scheduledCell, displayCell, delayCell, trackCell);
  return row;
}

function clearResults() {
  ui.body.replaceChildren();
  ui.tableWrap.hidden = true;
  ui.warning.hidden = true;
  ui.warning.textContent = "";
}

function showState(tone, title, message, retry = false) {
  clearResults();
  ui.statePanel.hidden = false;
  ui.statePanel.dataset.tone = tone;
  ui.stateSymbol.textContent = tone === "error" ? "!" : tone === "empty" ? "—" : tone === "ready" ? "⌕" : "";
  ui.stateTitle.textContent = title;
  ui.stateMessage.textContent = message;
  ui.retry.hidden = !retry;
  ui.announcement.textContent = `${title}. ${message}`;
}

function setMode(mode) {
  state.mode = ALLOWED_MODES.has(mode) ? mode : "live";
  ui.demoBanner.hidden = state.mode === "live";
  ui.refreshNote.textContent = state.mode === "live"
    ? "Automaattinen päivitys 60 s"
    : "Ei automaattista päivitystä";
  for (const button of ui.exampleButtons) {
    button.setAttribute("aria-pressed", String(button.dataset.mode === state.mode));
  }
}

function stopRefresh() {
  window.clearTimeout(state.refreshTimer);
  state.refreshTimer = null;
}

function planRefresh() {
  stopRefresh();
  if (state.mode !== "live") return;
  state.refreshTimer = window.setTimeout(() => {
    if (document.hidden) {
      planRefresh();
      return;
    }
    loadDepartures("live");
  }, REFRESH_INTERVAL);
}

function renderBoard(payload) {
  const departures = payload.departures;
  ui.title.textContent = payload.station.name;
  ui.code.textContent = payload.station.code;
  ui.dataLabel.textContent = payload.source === "demo" ? "Esimerkkitiedot" : "Digitraffic · ajantasaiset tiedot";
  ui.dataLabel.dataset.tone = payload.source === "demo" ? "demo" : "live";
  ui.updatedAt.textContent = `Päivitetty ${showTime(payload.fetched_at)}`;
  if (!departures.length) {
    showState("empty", "Ei tulevia lähtöjä", "Tälle asemalle ei löytynyt seuraavia lähteviä junia. Kokeile toista asemaa tai hae tiedot uudelleen.");
  } else {
    ui.statePanel.hidden = true;
    const rows = document.createDocumentFragment();
    for (const train of departures) rows.append(departureRow(train));
    ui.body.replaceChildren(rows);
    ui.tableWrap.hidden = false;
    ui.announcement.textContent = `${payload.station.name}: ${departures.length} lähtöä. ${payload.source === "demo" ? "Kuvitteelliset esimerkkitiedot." : "Tiedot päivitetty."}`;
  }
  if (typeof payload.warning === "string" && payload.warning) {
    ui.warning.textContent = payload.warning;
    ui.warning.hidden = false;
  }
}

async function loadDepartures(mode = "live") {
  stopRefresh();
  // Uusi haku keskeyttää edellisen. Juokseva tunniste estää vanhaa vastausta
  // korvaamasta uuden aseman tietoja, vaikka kaksi pyyntöä valmistuisi eri järjestyksessä.
  if (state.controller) state.controller.abort();
  const controller = new AbortController();
  state.controller = controller;
  const requestId = ++state.requestId;
  setMode(mode);
  const station = selectedStation();
  ui.title.textContent = station.name;
  ui.code.textContent = station.code;
  ui.board.setAttribute("aria-busy", "true");
  ui.search.disabled = true;
  ui.dataLabel.textContent = "Haetaan tietoja";
  ui.dataLabel.dataset.tone = state.mode === "live" ? "live" : "demo";
  ui.updatedAt.textContent = "Hetki vielä…";
  showState("loading", "Haetaan lähteviä junia", "Noudetaan aseman viimeisimmät tiedot.");

  // Myös selaimen odotuksella on yläraja. Palvelimella on erikseen oma
  // HTTP-aikakatkaisu Digitraffic-yhteydelle.
  const timeout = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT);
  try {
    const params = new URLSearchParams({ station: station.code, mode: state.mode });
    const response = await fetch(`/api/departures?${params}`, {
      method: "GET", signal: controller.signal, cache: "no-store", headers: { Accept: "application/json" },
    });
    const payload = await response.json();
    if (requestId !== state.requestId) return;
    if (!response.ok) {
      // Palvelin palauttaa turvallisen käyttäjäviestin. Sisäisiä virheitä ei näytetä.
      const error = new Error("Palvelin ei saanut junatietoja.");
      error.userMessage = typeof payload.error === "string" ? payload.error : "Junatietojen hakeminen ei onnistunut. Yritä hetken kuluttua uudelleen.";
      throw error;
    }
    if (!payload.station || !Array.isArray(payload.departures)) throw new Error("Odottamaton tietomuoto");
    renderBoard(payload);
    planRefresh();
  } catch (error) {
    if (requestId !== state.requestId) return;
    const message = error.name === "AbortError"
      ? "Tietojen hakeminen kesti liian kauan. Tarkista yhteys ja yritä uudelleen."
      : error.userMessage || "Junatietoja ei voitu hakea. Tarkista yhteys ja yritä uudelleen.";
    ui.dataLabel.textContent = "Tietoja ei saatavilla";
    ui.dataLabel.dataset.tone = "error";
    ui.updatedAt.textContent = "Haku ei onnistunut";
    showState("error", "Yhteys ei onnistunut", message, true);
  } finally {
    window.clearTimeout(timeout);
    if (requestId === state.requestId) {
      ui.board.setAttribute("aria-busy", "false");
      ui.search.disabled = false;
      state.controller = null;
    }
  }
}

// Aseman vaihtaminen tyhjentää vanhan aseman tulokset heti. Uusi haku
// käynnistyy Hae lähdöt -painikkeesta, eikä vanha vastaus pääse näkyviin.
ui.station.addEventListener("change", () => {
  stopRefresh();
  ++state.requestId;
  if (state.controller) state.controller.abort();
  state.controller = null;
  setMode("live");
  const station = selectedStation();
  ui.title.textContent = station.name;
  ui.code.textContent = station.code;
  ui.dataLabel.textContent = "Asema valittu";
  ui.dataLabel.dataset.tone = "live";
  ui.updatedAt.textContent = "Odottamassa hakua";
  ui.board.setAttribute("aria-busy", "false");
  ui.search.disabled = false;
  showState("ready", "Asema valittu", "Paina Hae lähdöt, niin saat tämän aseman seuraavat lähdöt.");
});

ui.form.addEventListener("submit", (event) => { event.preventDefault(); loadDepartures("live"); });
ui.retry.addEventListener("click", () => loadDepartures(state.mode));
ui.backToLive.addEventListener("click", () => loadDepartures("live"));
for (const button of ui.exampleButtons) {
  button.addEventListener("click", () => loadDepartures(button.dataset.mode));
}

// Sallittu kyselyparametri helpottaa myös tietyn esimerkin avaamista suoraan.
// Tuntematon tila tai asemakoodi ei vaikuta valintaan.
const initialParams = new URLSearchParams(window.location.search);
const initialStation = initialParams.get("station");
if ([...ui.station.options].some((option) => option.value === initialStation)) ui.station.value = initialStation;
const initialMode = ALLOWED_MODES.has(initialParams.get("mode")) ? initialParams.get("mode") : "live";
updateClock();
window.setInterval(updateClock, 30_000);
loadDepartures(initialMode);
