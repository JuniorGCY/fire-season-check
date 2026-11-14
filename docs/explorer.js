/* Area explorer: pick a rectangle and a date range, see the burn calendar, anomalies and download CSVs.
   Everything runs in the browser on data/grid.json (0.25 degree cells, weekly counts per sensor). */
(() => {
  const $ = (id) => document.getElementById(id);
  const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const DAY = 864e5;
  const NORMAL_YEARS = 10, MIN_YEARS = 5, MIN_NORMAL = 3, PROVISIONAL_DAYS = 150;
  const SEQ = ["#fff7ec", "#fdd49e", "#fc8d59", "#d7301f", "#7f0000"];
  const DIV = ["#2166ac", "#67a9cf", "#f7f7f7", "#ef8a62", "#b2182b"];

  let G, cells, NW, MOD, VII, dataThrough, firstMs;
  let rect, sel = [], series, cal, view = "count", cursor = null, range = { a: 1, b: 1 };
  let dragStart = null, cellTotals = null, mapPx = 12;

  // ---------- helpers ----------
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const ramp = (stops, t) => {
    const x = Math.min(1, Math.max(0, t)) * (stops.length - 1), i = Math.min(stops.length - 2, Math.floor(x)), f = x - i;
    const a = hex(stops[i]), b = hex(stops[i + 1]);
    return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
  };
  const weekStartMs = (w) => firstMs + w * 7 * DAY;
  const iso = (ms) => new Date(ms).toISOString().slice(0, 10);
  const label = (ms) => `${MONTHS[new Date(ms).getUTCMonth()]} ${new Date(ms).getUTCDate()}`;
  const isoYearWeek = (w) => {            // ISO year/week come from the week's Thursday
    const thu = new Date(weekStartMs(w) + 3 * DAY), y = thu.getUTCFullYear();
    const doy = Math.floor((thu - Date.UTC(y, 0, 1)) / DAY) + 1;
    return { year: y, week: Math.ceil(doy / 7), month: thu.getUTCMonth() + 1 };
  };
  const ratioFor = (month) => (G.ratio.fit === "monthly" && G.ratio.monthly[month] != null)
    ? G.ratio.monthly[month] : G.ratio.single;
  const weekOfDate = (s) => Math.floor((Date.parse(s + "T00:00:00Z") - firstMs) / (7 * DAY));
  const cellCenter = (c) => ({
    lat: G.origin.lat + (Math.floor(c / G.cols) + 0.5) * G.cell_degrees,
    lon: G.origin.lon + ((c % G.cols) + 0.5) * G.cell_degrees,
  });
  const fix = (v) => (Math.round(v * 100) / 100).toFixed(2);

  function dense(part) {
    const a = new Float32Array(NW * cells);
    let w = 0;
    for (let i = 0; i < part.n.length; i++) { w += part.w[i]; a[w * cells + part.c[i]] += part.n[i]; }
    return a;
  }

  // ---------- selection ----------
  function cellsInRect(r) {
    const out = [];
    for (let c = 0; c < cells; c++) {
      const p = cellCenter(c);
      if (p.lat >= r.s && p.lat <= r.n && p.lon >= r.w && p.lon <= r.e) out.push(c);
    }
    if (!out.length) {                       // a rectangle smaller than one cell: use the cell under its centre
      const lat = (r.s + r.n) / 2, lon = (r.w + r.e) / 2;
      const row = Math.min(G.rows - 1, Math.max(0, Math.floor((lat - G.origin.lat) / G.cell_degrees)));
      const col = Math.min(G.cols - 1, Math.max(0, Math.floor((lon - G.origin.lon) / G.cell_degrees)));
      out.push(row * G.cols + col);
    }
    return out;
  }

  function computeSeries() {
    const out = new Float64Array(NW).fill(NaN), mod = new Float64Array(NW), vii = new Float64Array(NW);
    for (let w = 1; w < NW; w++) {
      let m = 0, v = 0;
      const base = w * cells;
      for (const c of sel) { m += MOD[base + c]; v += VII[base + c]; }
      mod[w] = m; vii[w] = v;
      out[w] = w < G.viirs_from_week ? m : v * ratioFor(isoYearWeek(w).month);
    }
    return { value: out, mod, vii };
  }

  function buildCalendar() {
    const rows = new Map();                 // ISO year -> array of 54 values
    let minY = 9999, maxY = 0;
    for (let w = 1; w < NW; w++) {
      const { year, week } = isoYearWeek(w);
      if (!rows.has(year)) rows.set(year, new Array(54).fill(NaN));
      rows.get(year)[week] = series.value[w];
      minY = Math.min(minY, year); maxY = Math.max(maxY, year);
    }
    const cellsOut = [];
    const lastFinal = Date.parse(dataThrough + "T00:00:00Z") - PROVISIONAL_DAYS * DAY;
    for (let w = 1; w < NW; w++) {
      const { year, week } = isoYearWeek(w), value = series.value[w];
      let normal = NaN;
      if (week <= 52) {
        const prev = [];
        for (let y = year - NORMAL_YEARS; y < year; y++) {
          const r = rows.get(y);
          if (r && !Number.isNaN(r[week])) prev.push(r[week]);
        }
        if (prev.length >= MIN_YEARS) normal = prev.reduce((a, b) => a + b, 0) / prev.length;
      }
      const anomaly = normal >= MIN_NORMAL ? value / normal - 1 : NaN;
      cellsOut.push({ w, year, week, value, normal, anomaly, provisional: weekStartMs(w) + 6 * DAY > lastFinal });
    }
    const positive = cellsOut.map((c) => c.value).filter((v) => v > 0).sort((a, b) => a - b);
    const vmax = positive.length ? positive[Math.floor(positive.length * 0.98)] : 1;
    cal = { cells: cellsOut, minY, maxY, vmax: Math.max(vmax, 1), byKey: new Map(cellsOut.map((c) => [c.year * 100 + c.week, c])) };
  }

  // ---------- drawing ----------
  function drawMap() {
    const cv = $("map"), css = getComputedStyle(document.documentElement);
    const ratio = window.devicePixelRatio || 1;
    const cssW = Math.min(cv.parentElement.clientWidth, 420);
    mapPx = cssW / G.cols;
    const cssH = mapPx * G.rows;
    cv.style.width = cssW + "px"; cv.style.height = cssH + "px";
    cv.width = Math.round(cssW * ratio); cv.height = Math.round(cssH * ratio);
    const g = cv.getContext("2d"); g.setTransform(ratio, 0, 0, ratio, 0, 0);
    const surface = css.getPropertyValue("--band").trim() || "#dfe5e8", ink = css.getPropertyValue("--ink").trim();
    g.clearRect(0, 0, cssW, cssH);
    let top = 1;
    for (let c = 0; c < cells; c++) top = Math.max(top, cellTotals[c]);
    for (let c = 0; c < cells; c++) {
      const row = Math.floor(c / G.cols), col = c % G.cols;
      const x = col * mapPx, y = (G.rows - 1 - row) * mapPx;
      g.fillStyle = cellTotals[c] > 0 ? ramp(SEQ, Math.sqrt(cellTotals[c] / top)) : surface;
      g.fillRect(x, y, mapPx + 0.5, mapPx + 0.5);
    }
    if (rect) {
      const x = (rect.w - G.origin.lon) / G.cell_degrees * mapPx;
      const y = (G.rows - (rect.n - G.origin.lat) / G.cell_degrees) * mapPx;
      const w = (rect.e - rect.w) / G.cell_degrees * mapPx, h = (rect.n - rect.s) / G.cell_degrees * mapPx;
      g.lineWidth = 3; g.strokeStyle = "#ffffff"; g.strokeRect(x, y, w, h);
      g.lineWidth = 1.5; g.strokeStyle = ink || "#000"; g.strokeRect(x, y, w, h);
    }
  }

  const scaleLegend = () => {
    $("seq-legend").style.background = `linear-gradient(90deg, ${SEQ.join(",")})`;
    $("div-legend").style.background = `linear-gradient(90deg, ${DIV.join(",")})`;
  };

  function drawCalendar() {
    const host = $("calendar");
    const years = cal.maxY - cal.minY + 1, L = 40, T = 20, cw = 10, ch = 12;
    const W = L + 53 * cw + 4, H = T + years * ch + 4;
    const inRange = (w) => w >= range.a && w <= range.b;
    const fullRange = range.a <= 1 && range.b >= NW - 1;
    let svg = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Calendar of weekly hotspots, one row per year">`;
    for (let m = 0; m < 12; m++) svg += `<text x="${L + Math.round(m * 4.35) * cw}" y="12">${MONTHS[m]}</text>`;
    for (let y = cal.minY; y <= cal.maxY; y++) {
      if ((y - cal.minY) % 2 === 0) svg += `<text x="${L - 6}" y="${T + (y - cal.minY) * ch + 10}" text-anchor="end">${y}</text>`;
    }
    for (const c of cal.cells) {
      const x = L + (c.week - 1) * cw, y = T + (c.year - cal.minY) * ch;
      let fill;
      if (view === "count") fill = c.value > 0 ? ramp(SEQ, Math.sqrt(c.value / cal.vmax)) : ramp(SEQ, 0);
      else fill = Number.isNaN(c.anomaly) ? "none" : ramp(DIV, (Math.max(-1, Math.min(1, c.anomaly)) + 1) / 2);
      const faded = !fullRange && !inRange(c.w) ? ' opacity=".28"' : "";
      const dash = c.provisional ? ' stroke="var(--ink)" stroke-width=".6" stroke-dasharray="2 1.5"' : "";
      const none = fill === "none" ? ' stroke="var(--line)" stroke-width=".5"' : "";
      svg += `<rect x="${x}" y="${y}" width="${cw - 1}" height="${ch - 1}" fill="${fill}"${faded}${dash}${none}/>`;
    }
    if (cursor) {
      const x = L + (cursor.week - 1) * cw, y = T + (cursor.year - cal.minY) * ch;
      svg += `<rect x="${x - 1}" y="${y - 1}" width="${cw + 1}" height="${ch + 1}" fill="none" stroke="var(--focus)" stroke-width="2"/>`;
    }
    host.querySelector(".cal-svg").innerHTML = svg + "</svg>";
  }

  function readout() {
    if (!cursor) { $("cal-readout").textContent = "Select a week in the calendar, or use the arrow keys."; return; }
    const c = cal.byKey.get(cursor.year * 100 + cursor.week);
    if (!c) { $("cal-readout").textContent = "No data for this week."; return; }
    const start = weekStartMs(c.w);
    let text = `Week ${c.week} of ${c.year} (${label(start)} to ${label(start + 6 * DAY)}): ${fmt.format(c.value)} hotspots`;
    text += c.w < G.viirs_from_week ? " (MODIS)." : " (VIIRS scaled to the MODIS ruler).";
    if (!Number.isNaN(c.normal)) {
      text += ` Average of the previous ${NORMAL_YEARS} years for this week: ${fmt.format(c.normal)}`;
      text += Number.isNaN(c.anomaly) ? ". Too few hotspots to compare." :
        `, so ${c.anomaly >= 0 ? "+" : "−"}${Math.abs(Math.round(c.anomaly * 100))}%.`;
    } else text += ". Not enough earlier years to compute an average.";
    if (c.provisional) text += " Provisional: near-real-time data, may change.";
    $("cal-readout").textContent = text;
  }

  function summary() {
    let total = 0, normalTotal = 0, compared = 0, weeks = 0;
    for (const c of cal.cells) {
      if (c.w < range.a || c.w > range.b) continue;
      weeks++; total += c.value;
      if (!Number.isNaN(c.normal)) { normalTotal += c.normal; compared += c.value; }
    }
    const area = `${sel.length} cells of about 28 km (${fmt.format(sel.length * 770)} km² roughly)`;
    let text = `${fmt.format(total)} hotspots in ${weeks} weeks (${iso(weekStartMs(range.a))} to ${iso(weekStartMs(range.b) + 6 * DAY)}) over ${area}.`;
    if (normalTotal >= 10) {
      const pct = Math.round((compared / normalTotal - 1) * 100);
      text += ` For the same weeks, that is ${pct >= 0 ? "+" : "−"}${Math.abs(pct)}% against the average of the previous ${NORMAL_YEARS} years.`;
    } else if (total === 0) text += " No hotspots were detected here in this period.";
    else text += " Too little history in this area and period to compare with an average.";
    $("summary").textContent = text;
    $("small-note").hidden = sel.length >= 12 ? true : false;
  }

  // ---------- state flow ----------
  function updateTotals() {
    cellTotals = new Float64Array(cells);
    for (let w = Math.max(1, range.a); w <= Math.min(NW - 1, range.b); w++) {
      const base = w * cells;
      if (w < G.viirs_from_week) for (let c = 0; c < cells; c++) cellTotals[c] += MOD[base + c];
      else { const r = ratioFor(isoYearWeek(w).month); for (let c = 0; c < cells; c++) cellTotals[c] += VII[base + c] * r; }
    }
  }

  function refresh() {
    sel = cellsInRect(rect);
    series = computeSeries();
    buildCalendar();
    updateTotals();
    $("area").textContent = `Area used: latitude ${fix(rect.s)} to ${fix(rect.n)}, longitude ${fix(rect.w)} to ${fix(rect.e)}.`;
    summary(); drawMap(); drawCalendar(); readout();
  }

  function readInputs() {
    const v = (id) => parseFloat($(id).value.replace(",", "."));
    const r = { s: v("in-s"), n: v("in-n"), w: v("in-w"), e: v("in-e") };
    const lat0 = G.origin.lat, lat1 = lat0 + G.rows * G.cell_degrees, lon0 = G.origin.lon, lon1 = lon0 + G.cols * G.cell_degrees;
    const err = $("area-error");
    if ([r.s, r.n, r.w, r.e].some(Number.isNaN)) { err.textContent = "Type all four numbers in decimal degrees, for example -10.5."; return null; }
    if (r.s >= r.n || r.w >= r.e) { err.textContent = "South must be below north and west must be left of east (west is more negative)."; return null; }
    if (r.n < lat0 || r.s > lat1 || r.e < lon0 || r.w > lon1) {
      err.textContent = `This tool covers latitude ${fix(lat0)} to ${fix(lat1)} and longitude ${fix(lon0)} to ${fix(lon1)} (Tocantins and surroundings).`; return null;
    }
    err.textContent = "";
    return { s: Math.max(r.s, lat0), n: Math.min(r.n, lat1), w: Math.max(r.w, lon0), e: Math.min(r.e, lon1) };
  }

  function writeInputs() {
    $("in-s").value = fix(rect.s); $("in-n").value = fix(rect.n); $("in-w").value = fix(rect.w); $("in-e").value = fix(rect.e);
    $("area-error").textContent = "";
  }

  function readRange() {
    const a = $("in-from").value, b = $("in-to").value, err = $("range-error");
    if (!a || !b) { err.textContent = "Pick both dates."; return false; }
    const wa = weekOfDate(a), wb = weekOfDate(b);
    if (wa > wb) { err.textContent = "The start date must be before the end date."; return false; }
    err.textContent = "";
    range = { a: Math.max(1, wa), b: Math.min(NW - 1, wb) };
    return true;
  }

  // ---------- CSV ----------
  function download(name, lines) {
    const url = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }
  const areaTag = () => `${fix(rect.s)}_${fix(rect.n)}_${fix(rect.w)}_${fix(rect.e)}`;

  function weeklyCsv() {
    const lines = ["week_start,week_end,iso_year,iso_week,modis_hotspots,viirs_hotspots,harmonized_hotspots_modis_scale,source,provisional"];
    for (const c of cal.cells) {
      if (c.w < range.a || c.w > range.b) continue;
      const s = weekStartMs(c.w);
      lines.push([iso(s), iso(s + 6 * DAY), c.year, c.week, series.mod[c.w], series.vii[c.w], c.value.toFixed(2),
        c.w < G.viirs_from_week ? "MODIS" : "VIIRS scaled", c.provisional].join(","));
    }
    download(`weekly_hotspots_${areaTag()}.csv`, lines);
  }

  function cellsCsv() {
    const lines = ["week_start,cell_lat,cell_lon,modis_hotspots,viirs_hotspots"];
    for (let w = Math.max(1, range.a); w <= Math.min(NW - 1, range.b); w++) {
      for (const c of sel) {
        const m = MOD[w * cells + c], v = VII[w * cells + c];
        if (!m && !v) continue;
        const p = cellCenter(c);
        lines.push([iso(weekStartMs(w)), p.lat.toFixed(3), p.lon.toFixed(3), m, v].join(","));
      }
    }
    download(`hotspots_by_cell_${areaTag()}.csv`, lines);
  }

  // ---------- events ----------
  function cellAt(ev) {
    const box = $("map").getBoundingClientRect();
    const col = Math.min(G.cols - 1, Math.max(0, Math.floor((ev.clientX - box.left) / mapPx)));
    const row = Math.min(G.rows - 1, Math.max(0, G.rows - 1 - Math.floor((ev.clientY - box.top) / mapPx)));
    return { row, col };
  }
  function rectFromCells(a, b) {
    const r0 = Math.min(a.row, b.row), r1 = Math.max(a.row, b.row), c0 = Math.min(a.col, b.col), c1 = Math.max(a.col, b.col);
    return {
      s: G.origin.lat + r0 * G.cell_degrees, n: G.origin.lat + (r1 + 1) * G.cell_degrees,
      w: G.origin.lon + c0 * G.cell_degrees, e: G.origin.lon + (c1 + 1) * G.cell_degrees,
    };
  }

  function wire() {
    const map = $("map");
    map.addEventListener("pointerdown", (ev) => { map.setPointerCapture(ev.pointerId); dragStart = cellAt(ev); rect = rectFromCells(dragStart, dragStart); drawMap(); });
    map.addEventListener("pointermove", (ev) => { if (!dragStart) return; rect = rectFromCells(dragStart, cellAt(ev)); drawMap(); });
    const end = (ev) => { if (!dragStart) return; rect = rectFromCells(dragStart, cellAt(ev)); dragStart = null; writeInputs(); refresh(); };
    map.addEventListener("pointerup", end);
    map.addEventListener("pointercancel", () => { dragStart = null; });

    const applyArea = () => { const r = readInputs(); if (r) { rect = r; refresh(); } };
    for (const id of ["in-s", "in-n", "in-w", "in-e"]) $(id).addEventListener("change", applyArea);
    for (const id of ["in-from", "in-to"]) $(id).addEventListener("change", () => { if (readRange()) refresh(); });

    document.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
      const p = b.dataset.preset.split(",").map(Number);
      rect = { s: p[0], n: p[1], w: p[2], e: p[3] }; writeInputs(); refresh();
    }));
    document.querySelectorAll("input[name=view]").forEach((r) => r.addEventListener("change", () => {
      view = document.querySelector("input[name=view]:checked").value;
      $("seq-wrap").hidden = view !== "count"; $("div-wrap").hidden = view === "count"; drawCalendar();
    }));

    const host = $("calendar");
    const pick = (c) => { cursor = { year: c.year, week: c.week }; drawCalendar(); readout(); };
    host.addEventListener("click", (ev) => {
      const svg = host.querySelector("svg"); if (!svg) return;
      const box = svg.getBoundingClientRect(), k = box.width / svg.viewBox.baseVal.width;
      const week = Math.floor(((ev.clientX - box.left) / k - 40) / 10) + 1, year = cal.minY + Math.floor(((ev.clientY - box.top) / k - 20) / 12);
      const c = cal.byKey.get(year * 100 + week); if (c) pick(c);
    });
    host.addEventListener("keydown", (ev) => {
      const d = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] }[ev.key];
      if (!d) return;
      ev.preventDefault();
      let cur = cursor || { year: cal.maxY, week: 1 };
      const next = { year: cur.year + d[0], week: cur.week + d[1] };
      const c = cal.byKey.get(next.year * 100 + next.week); if (c) pick(c);
    });
    $("csv-weekly").onclick = () => series && weeklyCsv();
    $("csv-cells").onclick = () => series && cellsCsv();
    window.addEventListener("resize", () => { if (cellTotals) drawMap(); });
  }

  // ---------- load ----------
  function setState(kind, message) {
    $("ex-state").hidden = kind === "ready";
    $("ex-body").hidden = kind !== "ready";
    $("ex-state").textContent = message || "";
    if (kind === "error") {
      const b = document.createElement("button");
      b.type = "button"; b.className = "ghost"; b.textContent = "Try again"; b.style.marginTop = "12px";
      b.onclick = () => init(dataThrough);
      $("ex-state").appendChild(document.createElement("br")); $("ex-state").appendChild(b);
    }
  }

  let wired = false;
  async function init(through) {
    dataThrough = through;
    setState("loading", "Loading the area explorer…");
    try {
      const res = await fetch("data/grid.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(res.status);
      G = await res.json();
    } catch (e) { setState("error", "Could not load the area data. Check your connection and try again."); return; }
    cells = G.rows * G.cols; NW = G.n_weeks; firstMs = Date.parse(G.first_week + "T00:00:00Z");
    if (!NW || !G.modis.n.length) { setState("empty", "No hotspot data is available for the explorer yet."); return; }
    MOD = dense(G.modis); VII = dense(G.viirs);
    const lat1 = G.origin.lat + G.rows * G.cell_degrees, lon1 = G.origin.lon + G.cols * G.cell_degrees;
    rect = { s: G.origin.lat, n: lat1, w: G.origin.lon, e: lon1 };
    const end = new Date(weekStartMs(NW - 1) + 6 * DAY), endIso = iso(end.getTime());
    $("in-from").min = $("in-to").min = iso(weekStartMs(1)); $("in-from").max = $("in-to").max = endIso;
    $("in-from").value = `${new Date(weekStartMs(NW - 1)).getUTCFullYear()}-01-01`; $("in-to").value = endIso;
    $("data-end").textContent = endIso;
    setState("ready");
    scaleLegend(); readRange(); writeInputs();
    if (!wired) { wire(); wired = true; }
    refresh();
    cursor = null; readout();
  }

  window.FireExplorer = { init };
})();
