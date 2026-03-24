'use strict';

/* ── Constants ───────────────────────────────────────────────── */
const TRAIN_STATION = '8506131';
const BUS_STATION   = '8581697';
const API_BASE      = 'https://transport.opendata.ch/v1';
const WEATHER_URL   =
  'https://api.open-meteo.com/v1/forecast' +
  '?latitude=47.6465&longitude=9.1764' +
  '&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m' +
  '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max' +
  '&timezone=Europe%2FBerlin';
const ZRH_URL =
  'https://api.open-meteo.com/v1/forecast' +
  '?latitude=47.3769&longitude=8.5417' +
  '&hourly=precipitation_probability,precipitation' +
  '&timezone=Europe%2FBerlin';
const POLLEN_URL =
  'https://air-quality-api.open-meteo.com/v1/air-quality' +
  '?latitude=47.64&longitude=9.17' +
  '&current=alder_pollen,birch_pollen,grass_pollen,mugwort_pollen,olive_pollen,ragweed_pollen';

const DE_DAYS   = ['So.', 'Mo.', 'Di.', 'Mi.', 'Do.', 'Fr.', 'Sa.'];
const DE_MONTHS = ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni',
                   'Juli', 'Aug.', 'Sep.', 'Okt.', 'Nov.', 'Dez.'];

/* ── Helpers ─────────────────────────────────────────────────── */
function pad(n) { return String(n).padStart(2, '0'); }

function fmtTime(iso) {
  if (!iso) return '--:--';
  const d = new Date(iso);
  return pad(d.getHours()) + ':' + pad(d.getMinutes());
}

function calWeek(date) {
  const t = new Date(date.valueOf());
  const dayNr = (date.getDay() + 6) % 7;
  t.setDate(t.getDate() - dayNr + 3);
  const thu = t.valueOf();
  t.setMonth(0, 1);
  if (t.getDay() !== 4) t.setMonth(0, 1 + ((4 - t.getDay()) + 7) % 7);
  return 1 + Math.ceil((thu - t.valueOf()) / 604800000);
}

function viaText(passList) {
  if (!passList || passList.length === 0) return '';
  const zrhIdx = passList.findIndex(function (p) {
    const name = (p.location && p.location.name) || '';
    return name.includes('Zürich HB') || name.includes('Zurich HB');
  });
  var stops, hasMore;
  if (zrhIdx !== -1) {
    const zrh = passList[zrhIdx];
    const t   = zrh.departure || zrh.arrival;
    const ts  = t ? ' (' + fmtTime(t) + ')' : '';
    stops   = passList.slice(0, zrhIdx + 1).map(function (p) {
      const name = (p.location && p.location.name) || '';
      return p === zrh ? name + ts : name;
    });
    hasMore = zrhIdx < passList.length - 1;
  } else {
    stops   = passList.slice(0, 3).map(function (p) {
      return (p.location && p.location.name) || '';
    });
    hasMore = passList.length > 3;
  }
  stops = stops.filter(function (s) { return s.trim(); });
  if (!stops.length) return '';
  return 'via ' + stops.join(', ') + (hasMore ? ' ...' : '');
}

function pollenIdx(grains) {
  if (grains < 10)  return Math.max(1, Math.round(grains / 5));
  if (grains < 50)  return Math.min(4, 2 + Math.round(grains / 20));
  if (grains < 100) return 5;
  return 6;
}

/* ── SVG assets ──────────────────────────────────────────────── */
const TRAIN_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  '<rect x="4" y="3" width="16" height="16" rx="2"/>' +
  '<path d="M4 11h16M12 3v8M8 19l-2 3M18 22l-2-3M8 15h0M16 15h0"/></svg>';

const BUS_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M8 6v6M15 6v6M2 12h19.6"/>' +
  '<path d="M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"/>' +
  '<circle cx="7" cy="18" r="2"/><path d="M9 18h5"/><circle cx="16" cy="18" r="2"/></svg>';

const UMBRELLA_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M22 12a10.06 10.06 1 0 0-20 0Z"/>' +
  '<path d="M12 12v8a2 2 0 0 0 4 0"/>' +
  '<path d="M12 2v1"/></svg>';

function wxIcon(code, size) {
  size = size || 20;
  const a = 'xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size +
    '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round"';
  if (code === 0)
    return '<svg ' + a + '><circle cx="12" cy="12" r="4"/>' +
      '<path d="M12 2v2M12 20v2M5 5l1.5 1.5M17.5 17.5L19 19M2 12h2M20 12h2M5 19l1.5-1.5M17.5 6.5L19 5"/></svg>';
  if (code >= 1 && code <= 3)
    return '<svg ' + a + '><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>';
  if (code === 45 || code === 48)
    return '<svg ' + a + '><path d="M5 10h14M5 14h14M5 18h14"/></svg>';
  if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82))
    return '<svg ' + a + '><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9"/>' +
      '<path d="M16 14v6M8 14v6M12 16v6"/></svg>';
  if ((code >= 71 && code <= 77) || code === 85 || code === 86)
    return '<svg ' + a + '><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9"/>' +
      '<path d="M8 14l4 4 4-4M12 14v6"/></svg>';
  if (code >= 95 && code <= 99)
    return '<svg ' + a + '><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9"/>' +
      '<path d="M13 14l-4 4h6l-4 4"/></svg>';
  return '<svg ' + a + '><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>';
}

function pollenSVG(value) {
  function arc(v, d) {
    return '<path d="' + d + '" stroke="' + (value >= v ? 'currentColor' : 'none') + '"/>';
  }
  return '<svg width="20" height="20" viewBox="-4 8 32 18" fill="none" stroke-width="2.5" stroke-linecap="round">' +
    arc(6, 'M -1.8 10.2 A 19.5 19.5 0 0 1 25.8 10.2') +
    arc(5, 'M 0.7 12.7 A 16 16 0 0 1 23.3 12.7') +
    arc(4, 'M 3.2 15.2 A 12.5 12.5 0 0 1 20.8 15.2') +
    arc(3, 'M 5.6 17.6 A 9 9 0 0 1 18.4 17.6') +
    arc(2, 'M 8.1 20.1 A 5.5 5.5 0 0 1 15.9 20.1') +
    '<circle cx="12" cy="24" r="2.5" fill="' + (value >= 1 ? 'currentColor' : 'none') + '" stroke="none"/>' +
    '</svg>';
}

/* ── API fetch ────────────────────────────────────────────────── */
function nowDT() {
  const d = new Date();
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
    ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

async function get(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
  return r.json();
}

function processZurichRain(res) {
  if (!res || !res.hourly) return null;
  const times  = res.hourly.time;
  const probs  = res.hourly.precipitation_probability;
  const precip = res.hourly.precipitation;
  const today  = new Date().toISOString().split('T')[0];
  let maxProb = 0, totalMm = 0, found = 0;
  for (let i = 0; i < times.length; i++) {
    if (!times[i].startsWith(today)) continue;
    const h = parseInt(times[i].split('T')[1], 10);
    if (h >= 8 && h <= 17) {
      if (probs[i] > maxProb) maxProb = probs[i];
      totalMm += precip[i] || 0;
      found++;
    }
  }
  return found > 0 ? { prob: maxProb, mm: +totalMm.toFixed(1) } : null;
}

function processPollen(res) {
  if (!res || !res.current) return [];
  const c = res.current;
  const allergens = [
    { name: 'Erle',     g: c.alder_pollen   || 0 },
    { name: 'Birke',    g: c.birch_pollen    || 0 },
    { name: 'Gräser',   g: c.grass_pollen    || 0 },
    { name: 'Beifuss',  g: c.mugwort_pollen  || 0 },
    { name: 'Olive',    g: c.olive_pollen    || 0 },
    { name: 'Ambrosia', g: c.ragweed_pollen  || 0 },
  ];
  return allergens
    .map(function (a) { return { name: a.name, value: pollenIdx(a.g) }; })
    .filter(function (a) { return a.value > 2; })
    .sort(function (a, b) { return b.value - a.value; });
}

/* ── Render ──────────────────────────────────────────────────── */
function renderClock() {
  const now = new Date(Date.now() + 60_000);
  document.getElementById('clock').textContent =
    pad(now.getHours()) + ':' + pad(now.getMinutes());
  const kw = calWeek(now);
  const yr = String(now.getFullYear()).slice(2);
  document.getElementById('kw-line').textContent = 'KW ' + kw;
  document.getElementById('date-line').textContent =
    DE_DAYS[now.getDay()] + ' ' + now.getDate() + '. ' +
    DE_MONTHS[now.getMonth()] + " '" + yr;
}

function renderWeather(w) {
  const el = document.getElementById('weather-block');
  if (!w) { el.innerHTML = ''; return; }
  const cur  = w.current;
  const day  = w.daily;
  const temp  = Math.round(cur.temperature_2m);
  const feels = Math.round(cur.apparent_temperature);
  const minT  = Math.round(day.temperature_2m_min[0]);
  const maxT  = Math.round(day.temperature_2m_max[0]);
  const wind  = Math.round(cur.wind_speed_10m);
  const rainP = day.precipitation_probability_max[0];
  el.innerHTML =
    '<span class="wx-icon">' + wxIcon(cur.weather_code, 40) + '</span>' +
    '<span class="wx-temp">' + temp + '°</span>' +
    '<div class="wx-details">' +
      '<span>' + minT + '°–' + maxT + '° (' + feels + '°)</span>' +
      '<span>' + wind + 'km/h · ' + rainP + '%</span>' +
    '</div>';
}

function renderForecast(w) {
  const el = document.getElementById('forecast-block');
  if (!w || !w.daily || w.daily.time.length < 2) { el.innerHTML = ''; return; }
  const day = w.daily;
  let html = '';
  for (let i = 1; i <= 4 && i < day.time.length; i++) {
    const d   = new Date(day.time[i] + 'T12:00:00');
    const min = Math.round(day.temperature_2m_min[i]);
    const max = Math.round(day.temperature_2m_max[i]);
    html +=
      '<div class="fc-day">' +
        '<span class="fc-name">' + DE_DAYS[d.getDay()].replace('.', '') + '</span>' +
        '<span class="fc-icon">' + wxIcon(day.weather_code[i], 18) + '</span>' +
        '<span class="fc-temps">' + min + '°–' + max + '°</span>' +
      '</div>';
  }
  el.innerHTML = html;
}

function depRow(dep) {
  const stop      = dep.stop || {};
  const cancelled = !!stop.cancelled;
  const delay     = stop.delay || 0;
  const plat      = stop.platform || '';
  const isIR      = dep.category === 'IR';
  const depMin    = stop.departure ? new Date(stop.departure).getMinutes() : -1;
  const highlight = isIR && depMin === 16;
  const via       = viaText(dep.passList);
  const pillCls   = 'cat-pill' + (isIR ? ' ir' : '');
  const icon      = isIR ? TRAIN_ICON : BUS_ICON;

  let badges = '';
  if (!cancelled && delay > 0)
    badges += '<span class="badge delay">+' + delay + 'm</span>';
  if (!cancelled && plat.includes('!'))
    badges += '<span class="badge platform">Gl. ' + plat.replace('!', '') + '</span>';
  if (cancelled)
    badges += '<span class="badge cancelled">Ausfall</span>';

  return '<div class="dep-row' + (cancelled ? ' cancelled' : '') + (highlight ? ' highlight' : '') + '">' +
    '<span class="' + pillCls + '">' + dep.category + ' ' + dep.number + '</span>' +
    '<span class="transport-icon">' + icon + '</span>' +
    '<span class="dep-time">' + fmtTime(stop.departure) + '</span>' +
    '<span class="dep-info">' +
      '<span class="dep-dest">' + dep.to + '</span>' +
      (via ? '<span class="dep-via">' + via + '</span>' : '') +
    '</span>' +
    (badges ? '<span class="dep-badges">' + badges + '</span>' : '') +
  '</div>';
}

function renderTrains(data) {
  const board = (data && data.stationboard) ? data.stationboard : [];
  const irs   = board.filter(function (d) { return d.category === 'IR'; }).slice(0, 7);
  document.getElementById('trains-list').innerHTML = irs.map(depRow).join('');
}

function renderBuses(data) {
  const board = (data && data.stationboard) ? data.stationboard.slice(0, 6) : [];
  document.getElementById('buses-list').innerHTML = board.map(depRow).join('');
}

function renderZRH(rain) {
  const el = document.getElementById('zrh-overlay');
  if (!rain) { el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  el.innerHTML =
    '<span class="zrh-label">ZRH</span>' +
    '<div class="zrh-body">' +
      UMBRELLA_ICON +
      '<span class="zrh-rain">' + rain.prob + '% (' + rain.mm + 'mm)<br>08:00–17:00</span>' +
    '</div>';
}

function renderPollen(pollen) {
  const el = document.getElementById('pollen-overlay');
  if (!pollen || pollen.length === 0) { el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  const pills = pollen.slice(0, 6).map(function (p) {
    return '<span class="pollen-pill"><span>' + p.name + '</span>' + pollenSVG(p.value) + '</span>';
  }).join('');
  document.getElementById('pollen-pills').innerHTML = pills;
}

/* ── Data loading ────────────────────────────────────────────── */
async function tryDataJson() {
  try {
    const r = await fetch('/data.json?t=' + Date.now());
    if (!r.ok) return null;
    return r.json();
  } catch (e) { return null; }
}

async function refresh() {
  const cached = await tryDataJson();
  var trains, buses, weather, zurichRain, pollen;

  if (cached) {
    trains    = cached.trains;
    buses     = cached.buses;
    weather   = cached.weather;
    zurichRain = processZurichRain(cached.zurich_rain);
    pollen    = processPollen(cached.pollen);
  } else {
    const results = await Promise.all([
      get(API_BASE + '/stationboard?station=' + TRAIN_STATION + '&limit=40&passlist=1&datetime=' + encodeURIComponent(nowDT())),
      get(API_BASE + '/stationboard?station=' + BUS_STATION   + '&limit=8&passlist=1&datetime='  + encodeURIComponent(nowDT())),
      get(WEATHER_URL),
      get(ZRH_URL),
      get(POLLEN_URL),
    ]);
    trains    = results[0];
    buses     = results[1];
    weather   = results[2];
    zurichRain = processZurichRain(results[3]);
    pollen    = processPollen(results[4]);
  }

  renderTrains(trains);
  renderBuses(buses);
  renderWeather(weather);
  renderForecast(weather);
  renderZRH(zurichRain);
  renderPollen(pollen);
}

/* ── Init ────────────────────────────────────────────────────── */
renderClock();
setInterval(renderClock, 1000);

refresh();
setInterval(refresh, 60000);
