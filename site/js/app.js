/* app.js — bootstrap and glue: loads data, wires map ↔ timeline ↔ panel.
 * The browser only ever sees the small pre-aggregated files in site/data/
 * (PLAN.md §3); city series are lazy-loaded on first click and cached. */

import { createMap } from "./map.js";
import { initTimeline } from "./timeline.js";

/* Which city detail series to show for a clicked NUTS-1 region. Only
 * countries with a downloaded city get the June line chart; everywhere else
 * the panel shows the region's own 14-day series. */
const CITY_FOR_REGION = (id, country) => ({
  UK: id.startsWith("UKH") ? "norwich" : "london",
  FR: id === "FRI" ? "bordeaux" : "paris",
  NL: "amsterdam", BE: "brussels", DE: "berlin", CH: "zurich",
  AT: "vienna", HU: "budapest", ES: "madrid", IT: "milan",
}[country]);

const state = { daily: null, events: [], index: 0, region: null };
const cityCache = new Map();

async function fetchJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${url}: HTTP ${resp.status}`);
  return resp.json();
}

/* ------------------------------------------------------------------ */
/* Event card: show any dated events for the current timeline step.   */
/* ------------------------------------------------------------------ */
function renderEvents() {
  const el = document.getElementById("event-card");
  const today = state.daily.dates[state.index];
  const todays = state.events.filter((e) => e.date === today);
  el.hidden = todays.length === 0;
  el.innerHTML = todays.map((e) => `
    <strong>${e.title}</strong> ${e.detail}
    ${e.provisional ? '<em class="prov">provisional</em>' : ""}
  `).join("<hr>");
}

/* ------------------------------------------------------------------ */
/* Detail panel                                                        */
/* ------------------------------------------------------------------ */
async function openPanel(props) {
  state.region = props.id;
  const region = state.daily.regions[props.id];
  const panel = document.getElementById("panel");
  panel.hidden = false;
  document.getElementById("panel-title").textContent = props.name;

  drawRegionBars(region);
  updatePanelStats(region);

  const cityEl = document.getElementById("city-section");
  const city = CITY_FOR_REGION(props.id, props.country);
  cityEl.hidden = !city;
  if (!city) return;

  if (!cityCache.has(city)) {
    cityCache.set(city, await fetchJson(`data/cities/${city}.json`));
  }
  const c = cityCache.get(city);
  document.getElementById("city-title").textContent =
    `${city[0].toUpperCase()}${city.slice(1)} — June 2026 vs 1991–2020`;
  document.getElementById("tropical-count").textContent =
    `${c.tropical_nights_2026} tropical night${c.tropical_nights_2026 === 1 ? "" : "s"} (min ≥ 20 °C)`;
  drawCityChart(c);
}

function updatePanelStats(region) {
  const i = state.index;
  document.getElementById("panel-stats").innerHTML =
    `<span class="big">${region.anomaly[i] > 0 ? "+" : ""}${region.anomaly[i]}°C</span> vs June normal
     · mean max ${region.tx[i]}°C · hottest cell ${region.tx_max[i]}°C
     · tropical nights across ${region.tropical[i]}% of region`;
}

/* 14-day anomaly bars for the clicked region (always available). */
function drawRegionBars(region) {
  const canvas = document.getElementById("region-canvas");
  const ctx = setupCanvas(canvas);
  const { width: W, height: H } = canvas.getBoundingClientRect();
  const n = region.anomaly.length;
  const max = 20, zero = H - 18;
  const barW = (W - 8) / n;

  region.anomaly.forEach((a, i) => {
    const h = (Math.abs(a) / max) * (zero - 6);
    ctx.fillStyle = a >= 0 ? "#ef8a62" : "#67a9cf";
    ctx.fillRect(4 + i * barW, a >= 0 ? zero - h : zero, barW - 2, Math.max(h, 1));
  });
  ctx.strokeStyle = "#555";
  ctx.beginPath(); ctx.moveTo(0, zero); ctx.lineTo(W, zero); ctx.stroke();
  ctx.fillStyle = "#9aa"; ctx.font = "11px system-ui";
  ctx.fillText("17 Jun", 4, H - 4);
  ctx.fillText("30 Jun", W - 42, H - 4);
}

/* June 2026 max/min vs climatology for the region's city. */
function drawCityChart(c) {
  const canvas = document.getElementById("city-canvas");
  const ctx = setupCanvas(canvas);
  const { width: W, height: H } = canvas.getBoundingClientRect();
  const all = [...c.tx, ...c.tn, ...c.clim_tx, ...c.clim_tn];
  const lo = Math.floor(Math.min(...all)) - 1;
  const hi = Math.ceil(Math.max(...all)) + 1;
  const x = (i) => 4 + (i / (c.dates.length - 1)) * (W - 8);
  const y = (v) => H - 16 - ((v - lo) / (hi - lo)) * (H - 24);

  const line = (vals, colour, dash) => {
    ctx.strokeStyle = colour; ctx.lineWidth = dash ? 1 : 2;
    ctx.setLineDash(dash ? [4, 3] : []);
    ctx.beginPath();
    vals.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.stroke();
    ctx.setLineDash([]);
  };
  line(c.clim_tx, "#8a6d5c", true);  // normal daily max
  line(c.clim_tn, "#5c6d8a", true);  // normal daily min
  line(c.tx, "#ef8a62");             // 2026 daily max
  line(c.tn, "#67a9cf");             // 2026 daily min

  // 20 °C tropical-night threshold.
  ctx.strokeStyle = "#775"; ctx.setLineDash([2, 4]);
  ctx.beginPath(); ctx.moveTo(4, y(20)); ctx.lineTo(W - 4, y(20)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#9aa"; ctx.font = "11px system-ui";
  ctx.fillText(`${hi}°`, 4, 12);
  ctx.fillText(`${lo}°`, 4, H - 18);
}

/* HiDPI-aware canvas reset. */
function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const { width, height } = canvas.getBoundingClientRect();
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);
  return ctx;
}

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */
async function main() {
  const [daily, events] = await Promise.all([
    fetchJson("data/daily_anomaly.json"),
    fetchJson("data/events.json"),
  ]);
  state.daily = daily;
  state.events = events;

  const { ready, setDate } = createMap({
    container: "map",
    regionsUrl: "data/regions.geojson",
    onRegionClick: openPanel,
  });
  await ready;

  initTimeline({
    dates: daily.dates,
    events,
    onChange: (i) => {
      state.index = i;
      setDate(i, daily.regions);
      renderEvents();
      if (state.region) updatePanelStats(daily.regions[state.region]);
    },
  });

  document.getElementById("panel-close").addEventListener("click", () => {
    document.getElementById("panel").hidden = true;
    state.region = null;
  });
}

main().catch((err) => {
  document.getElementById("map").innerHTML =
    `<p class="load-error">Failed to load data: ${err.message}</p>`;
});
