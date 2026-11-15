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

  let G, GEO = null, cells, NW, MOD, VII, dataThrough, firstMs;
  let rect, sel = [], series, cal, months, view = "count", cursor = null, mcursor = null, range = { a: 1, b: 1 };
  let dragStart = null, cellTotals = null, mapPx = 12;
  const ML = 40, MT = 6, MB = 20;

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
  const median = (values) => {
    const s = values.slice().sort((a, b) => a - b), h = Math.floor(s.length / 2);
    return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
  };

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
      let normal = NaN, med = NaN;
      if (week <= 52) {
        const prev = [];
        for (let y = year - NORMAL_YEARS; y < year; y++) {
          const r = rows.get(y);
          if (r && !Number.isNaN(r[week])) prev.push(r[week]);
        }
        if (prev.length >= MIN_YEARS) { normal = prev.reduce((a, b) => a + b, 0) / prev.length; med = median(prev); }
      }
      const anomaly = normal >= MIN_NORMAL ? value / normal - 1 : NaN;
      cellsOut.push({ w, year, week, value, normal, median: med, anomaly, provisional: weekStartMs(w) + 6 * DAY > lastFinal });
    }
    const positive = cellsOut.map((c) => c.value).filter((v) => v > 0).sort((a, b) => a - b);
    const vmax = positive.length ? positive[Math.floor(positive.length * 0.98)] : 1;
    cal = { cells: cellsOut, rows, minY, maxY, vmax: Math.max(vmax, 1), byKey: new Map(cellsOut.map((c) => [c.year * 100 + c.week, c])) };
  }

  // ---------- months (a week belongs to the month of its Thursday, like ISO weeks to years) ----------
  const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const thursdaysIn = (y, m) => {           // m is 1..12
    let n = 0;
    for (let d = 1; d <= new Date(Date.UTC(y, m, 0)).getUTCDate(); d++) if (new Date(Date.UTC(y, m - 1, d)).getUTCDay() === 4) n++;
    return n;
  };
  function buildMonths() {
    const byKey = new Map();
    for (const c of cal.cells) {
      const thu = new Date(weekStartMs(c.w) + 3 * DAY), year = thu.getUTCFullYear(), month = thu.getUTCMonth() + 1;
      const key = year * 100 + month;
      if (!byKey.has(key)) byKey.set(key, { year, month, weeks: 0, total: 0, provisional: false });
      const g = byKey.get(key);
      g.weeks++; g.total += c.value; g.provisional = g.provisional || c.provisional;
    }
    const list = [...byKey.values()].sort((a, b) => a.year - b.year || a.month - b.month);
    for (const g of list) {
      g.expected = thursdaysIn(g.year, g.month);
      g.complete = g.weeks === g.expected;
      g.perWeek = g.total / g.weeks;
      const prev = [];
      for (let y = g.year - NORMAL_YEARS; y < g.year; y++) {
        const p = byKey.get(y * 100 + g.month);
        if (p && p.complete) prev.push(p.perWeek);
      }
      g.median = prev.length >= MIN_YEARS ? median(prev) : NaN;
      g.anomaly = g.median >= MIN_NORMAL ? g.perWeek / g.median - 1 : NaN;
    }
    const totals = list.filter((g) => g.complete).map((g) => g.total).sort((a, b) => a - b);
    const vmax = totals.length ? totals[Math.floor(totals.length * 0.98)] : 1;
    months = { list, byKey, minY: list[0].year, maxY: list[list.length - 1].year, vmax: Math.max(vmax, 1) };
  }

  function monthText(g) {
    const name = `${MONTH_NAMES[g.month - 1]} ${g.year}`;
    let text = g.complete ? `${name}: ${fmt.format(g.total)} hotspots (${fmt.format(g.perWeek)} per week).`
      : `${name}, ${g.weeks} of ${g.expected} weeks so far: ${fmt.format(g.total)} hotspots (${fmt.format(g.perWeek)} per week).`;
    if (!Number.isNaN(g.anomaly)) {
      const pct = Math.round(g.anomaly * 100);
      text += ` Median of the same month in the previous ${NORMAL_YEARS} years: ${fmt.format(g.median)} per week, so ${pct >= 0 ? "+" : "−"}${Math.abs(pct)}%.`;
    } else if (!Number.isNaN(g.median)) text += " Too few hotspots in this month historically to compare.";
    else text += " Not enough earlier years to compare.";
    if (g.provisional) text += " Provisional: includes near-real-time data.";
    return text;
  }

  function monthsHeadline() {
    const latest = months.list[months.list.length - 1];
    const byMonth = Array.from({ length: 12 }, () => []), byYear = new Map();
    for (const g of months.list) {
      if (!g.complete) continue;
      byMonth[g.month - 1].push(g.total);
      byYear.set(g.year, (byYear.get(g.year) || []).concat([g.total]));
    }
    const avg = byMonth.map((v) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : -1));
    const busiest = avg.indexOf(Math.max(...avg));
    let topYear = null, topTotal = -1;
    for (const [y, v] of byYear) {
      const t = v.reduce((a, b) => a + b, 0);
      if (v.length === 12 && t > topTotal) { topYear = y; topTotal = t; }
    }
    let text = `Latest month: ${monthText(latest)}`;
    if (busiest >= 0 && avg[busiest] > 0) text += ` On average the busiest month here is ${MONTH_NAMES[busiest]}`;
    if (topYear) text += `, and the busiest full year was ${topYear} (${fmt.format(topTotal)} hotspots).`;
    else text += ".";
    $("month-now").textContent = text;
  }

  function drawMonths() {
    const host = $("months"), L = 40, T = 20, cw = 26, ch = 12, years = months.maxY - months.minY + 1;
    const W = L + 12 * cw + 4, H = T + years * ch + 4;
    let svg = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Monthly calendar of hotspots, one row per year">`;
    for (let m = 0; m < 12; m++) svg += `<text x="${L + m * cw + cw / 2}" y="12" text-anchor="middle">${MONTHS[m].slice(0, 1)}</text>`;
    for (let y = months.minY; y <= months.maxY; y++) {
      if ((y - months.minY) % 2 === 0) svg += `<text x="${L - 6}" y="${T + (y - months.minY) * ch + 10}" text-anchor="end">${y}</text>`;
    }
    for (const g of months.list) {
      const x = L + (g.month - 1) * cw, y = T + (g.year - months.minY) * ch;
      let fill;
      if (view === "count") fill = ramp(SEQ, g.complete ? Math.sqrt(g.total / months.vmax) : Math.sqrt(g.perWeek * g.expected / months.vmax));
      else fill = Number.isNaN(g.anomaly) ? "none" : ramp(DIV, (Math.max(-1, Math.min(1, g.anomaly)) + 1) / 2);
      const dash = !g.complete || g.provisional ? ' stroke="var(--ink)" stroke-width=".6" stroke-dasharray="2 1.5"' : "";
      const none = fill === "none" ? ' stroke="var(--line)" stroke-width=".5"' : "";
      svg += `<rect x="${x}" y="${y}" width="${cw - 1}" height="${ch - 1}" fill="${fill}"${dash}${none}/>`;
    }
    if (mcursor) {
      const x = L + (mcursor.month - 1) * cw, y = T + (mcursor.year - months.minY) * ch;
      svg += `<rect x="${x - 1}" y="${y - 1}" width="${cw + 1}" height="${ch + 1}" fill="none" stroke="var(--focus)" stroke-width="2"/>`;
    }
    host.querySelector(".cal-svg").innerHTML = svg + "</svg>";
  }

  function monthReadout() {
    if (!mcursor) { $("month-readout").textContent = "Select a month in the monthly calendar, or use the arrow keys."; return; }
    const g = months.byKey.get(mcursor.year * 100 + mcursor.month);
    $("month-readout").textContent = g ? monthText(g) : "No data for this month.";
  }

  // ---------- drawing ----------
  function drawMap() {
    const cv = $("map"), css = getComputedStyle(document.documentElement);
    const ratio = window.devicePixelRatio || 1;
    const cssW = Math.min(cv.parentElement.clientWidth, 440);
    mapPx = (cssW - ML - 4) / G.cols;
    const cssH = MT + mapPx * G.rows + MB;
    cv.style.width = cssW + "px"; cv.style.height = cssH + "px";
    cv.width = Math.round(cssW * ratio); cv.height = Math.round(cssH * ratio);
    const g = cv.getContext("2d"); g.setTransform(ratio, 0, 0, ratio, 0, 0);
    const surface = css.getPropertyValue("--band").trim() || "#dfe5e8", ink = css.getPropertyValue("--ink").trim();
    g.clearRect(0, 0, cssW, cssH);
    let top = 1;
    for (let c = 0; c < cells; c++) top = Math.max(top, cellTotals[c]);
    for (let c = 0; c < cells; c++) {
      const row = Math.floor(c / G.cols), col = c % G.cols;
      const x = ML + col * mapPx, y = MT + (G.rows - 1 - row) * mapPx;
      g.fillStyle = cellTotals[c] > 0 ? ramp(SEQ, Math.sqrt(cellTotals[c] / top)) : surface;
      g.fillRect(x, y, mapPx + 0.5, mapPx + 0.5);
    }
    if (GEO) drawGeo(g, ink || "#000");
    if (rect) {
      const x = ML + (rect.w - G.origin.lon) / G.cell_degrees * mapPx;
      const y = MT + (G.rows - (rect.n - G.origin.lat) / G.cell_degrees) * mapPx;
      const w = (rect.e - rect.w) / G.cell_degrees * mapPx, h = (rect.n - rect.s) / G.cell_degrees * mapPx;
      g.lineWidth = 3; g.strokeStyle = "#ffffff"; g.strokeRect(x, y, w, h);
      g.lineWidth = 1.5; g.strokeStyle = ink || "#000"; g.strokeRect(x, y, w, h);
    }
    g.fillStyle = css.getPropertyValue("--muted").trim() || "#555"; g.font = "11px system-ui, sans-serif";
    const lat1 = G.origin.lat + G.rows * G.cell_degrees, lon1 = G.origin.lon + G.cols * G.cell_degrees;
    g.textAlign = "right"; g.textBaseline = "middle";
    for (let lat = Math.ceil(G.origin.lat); lat <= lat1; lat++) {
      g.fillText(`${Math.abs(lat)}°S`, ML - 5, MT + (lat1 - lat) / G.cell_degrees * mapPx);
    }
    g.textAlign = "center"; g.textBaseline = "top";
    for (let lon = Math.ceil(G.origin.lon); lon <= lon1; lon++) {
      g.fillText(`${Math.abs(lon)}°W`, ML + (lon - G.origin.lon) / G.cell_degrees * mapPx, MT + G.rows * mapPx + 5);
    }
  }

  // State outline and city labels (data/geo.json, IBGE). Optional: the map still works without them.
  function drawGeo(g, ink) {
    const halo = getComputedStyle(document.documentElement).getPropertyValue("--surface").trim() || "#ffffff";
    const px = (lon) => ML + (lon - G.origin.lon) / G.cell_degrees * mapPx;
    const py = (lat) => MT + (G.rows - (lat - G.origin.lat) / G.cell_degrees) * mapPx;
    g.lineJoin = "round";
    for (const [width, color] of [[3, halo], [1.2, ink]]) {
      g.lineWidth = width; g.strokeStyle = color;
      for (const ring of GEO.outline) {
        g.beginPath();
        ring.forEach(([lon, lat], i) => (i ? g.lineTo(px(lon), py(lat)) : g.moveTo(px(lon), py(lat))));
        g.stroke();
      }
    }
    g.font = "10.5px system-ui, sans-serif"; g.textAlign = "left"; g.textBaseline = "middle";
    const taken = [];                        // label boxes already drawn: later names that would overlap are skipped
    for (const p of GEO.places) {
      const x = px(p.lon), y = py(p.lat), w = g.measureText(p.name).width;
      const box = { x0: x + 5, x1: x + 5 + w, y0: y - 6, y1: y + 6 };
      if (box.x1 > ML + G.cols * mapPx + 4 || taken.some((b) => box.x0 < b.x1 && box.x1 > b.x0 && box.y0 < b.y1 && box.y1 > b.y0)) continue;
      taken.push(box);                       // a dot is drawn only together with its name
      g.beginPath(); g.arc(x, y, 2.5, 0, 2 * Math.PI);
      g.fillStyle = ink; g.fill(); g.lineWidth = 1.2; g.strokeStyle = halo; g.stroke();
      g.lineWidth = 3; g.strokeStyle = halo; g.strokeText(p.name, box.x0, y);
      g.fillStyle = ink; g.fillText(p.name, box.x0, y);
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
      const dash = c.provisional ? ' stroke="var(--ink)" stroke-width=".6" stroke-dasharray="2 1.5"' : "";
      const none = fill === "none" ? ' stroke="var(--line)" stroke-width=".5"' : "";
      svg += `<rect x="${x}" y="${y}" width="${cw - 1}" height="${ch - 1}" fill="${fill}"${dash}${none}/>`;
    }
    if (!fullRange) {                       // one outline per year around the weeks inside the chosen dates
      const spans = new Map();
      for (const c of cal.cells) {
        if (!inRange(c.w)) continue;
        const s = spans.get(c.year) || [99, 0];
        spans.set(c.year, [Math.min(s[0], c.week), Math.max(s[1], c.week)]);
      }
      for (const [year, [a, b]] of spans) {
        svg += `<rect x="${L + (a - 1) * cw - 1}" y="${T + (year - cal.minY) * ch - 1}" width="${(b - a + 1) * cw + 1}" height="${ch + 1}" fill="none" stroke="var(--ink)" stroke-width="1.5"/>`;
      }
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
      if (!Number.isNaN(c.median)) text += ` Median of those years: ${fmt.format(c.median)}.`;
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
      text += ` For the same weeks, that is ${pct >= 0 ? "+" : "−"}${Math.abs(pct)}% against the average of the previous ${NORMAL_YEARS} years`;
      // Median: total of the same weeks k years earlier, for each k = 1..10 that has all those weeks.
      const priorTotals = [];
      for (let k = 1; k <= NORMAL_YEARS; k++) {
        let t = 0, ok = true;
        for (const c of cal.cells) {
          if (c.w < range.a || c.w > range.b || c.week > 52) continue;
          const r = cal.rows.get(c.year - k), v = r ? r[c.week] : NaN;
          if (Number.isNaN(v)) { ok = false; break; }
          t += v;
        }
        if (ok) priorTotals.push(t);
      }
      const med = priorTotals.length >= MIN_YEARS ? median(priorTotals) : NaN;
      if (med >= 10) {
        let now = 0;
        for (const c of cal.cells) if (c.w >= range.a && c.w <= range.b && c.week <= 52) now += c.value;
        const pm = Math.round((now / med - 1) * 100);
        text += ` and ${pm >= 0 ? "+" : "−"}${Math.abs(pm)}% against their median.`;
      } else text += ".";
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
    buildMonths();
    updateTotals();
    $("area").textContent = `Area used: latitude ${fix(rect.s)} to ${fix(rect.n)}, longitude ${fix(rect.w)} to ${fix(rect.e)}.`;
    summary(); drawMap(); drawCalendar(); readout();
    monthsHeadline(); drawMonths(); monthReadout();
  }

  function readInputs() {
    const v = (id) => parseFloat($(id).value.replace(",", "."));
    const r = { s: v("in-s"), n: v("in-n"), w: v("in-w"), e: v("in-e") };
    const lat0 = G.origin.lat, lat1 = lat0 + G.rows * G.cell_degrees, lon0 = G.origin.lon, lon1 = lon0 + G.cols * G.cell_degrees;
    const err = $("area-error");
    if ([r.s, r.n, r.w, r.e].some(Number.isNaN)) { err.textContent = "Type all four numbers in decimal degrees, for example -10.5."; return null; }
    if (r.s >= r.n || r.w >= r.e) { err.textContent = "South must be below north and west must be left of east (west is more negative)."; return null; }
    if (r.n < lat0 || r.s > lat1 || r.e < lon0 || r.w > lon1) {
      err.textContent = `This tool covers latitude ${fix(lat0)} to ${fix(lat1)} and longitude ${fix(lon0)} to ${fix(lon1)} (the box this page was built for).`; return null;
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

  function monthlyCsv() {
    const lines = ["year,month,weeks,complete,harmonized_hotspots,per_week,median_per_week_previous_10_years,vs_median,provisional"];
    const from = isoYearWeek(range.a), to = isoYearWeek(range.b);
    for (const g of months.list) {
      if (g.year * 100 + g.month < from.year * 100 + from.month || g.year * 100 + g.month > to.year * 100 + to.month) continue;
      lines.push([g.year, g.month, g.weeks, g.complete, g.total.toFixed(2), g.perWeek.toFixed(2),
        Number.isNaN(g.median) ? "" : g.median.toFixed(2), Number.isNaN(g.anomaly) ? "" : g.anomaly.toFixed(3), g.provisional].join(","));
    }
    download(`monthly_hotspots_${areaTag()}.csv`, lines);
  }

  // ---------- images (PNG) with a caption that says what, where and from which data ----------
  function caption(what) {
    return [`Fire Season Check: ${what}, ${iso(weekStartMs(range.a))} to ${iso(weekStartMs(range.b) + 6 * DAY)}`,
      `Area: lat ${fix(rect.s)} to ${fix(rect.n)}, lon ${fix(rect.w)} to ${fix(rect.e)}. NASA FIRMS MODIS + VIIRS, harmonized to the MODIS ruler.`];
  }
  function withCaption(source, w, h, what, name) {
    const css = getComputedStyle(document.documentElement), scale = Math.max(1, w / 900);
    const lines = caption(what), pad = 12 * scale, lineH = 16 * scale;
    const out = document.createElement("canvas");
    out.width = Math.max(w, 700 * scale); out.height = h + pad * 2 + lineH * lines.length;
    const g = out.getContext("2d");
    g.fillStyle = css.getPropertyValue("--surface").trim() || "#fff"; g.fillRect(0, 0, out.width, out.height);
    g.drawImage(source, 0, 0, w, h);
    g.fillStyle = css.getPropertyValue("--ink").trim() || "#000"; g.font = `${12 * scale}px system-ui, sans-serif`; g.textBaseline = "top";
    lines.forEach((t, i) => g.fillText(t, pad, h + pad + i * lineH));
    out.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob), a = Object.assign(document.createElement("a"), { href: url, download: name });
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, "image/png");
  }
  async function svgPng(svgEl, what, name) {
    if (!svgEl) return;
    const css = getComputedStyle(document.documentElement), vb = svgEl.viewBox.baseVal, scale = 2;
    let src = new XMLSerializer().serializeToString(svgEl)
      .replace(/var\((--[\w-]+)\)/g, (_, v) => css.getPropertyValue(v).trim() || "#000");
    if (!src.includes("xmlns=")) src = src.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
    const bg = css.getPropertyValue("--surface").trim() || "#fff", ink = css.getPropertyValue("--muted").trim() || "#555";
    src = src.replace(/(<svg[^>]*>)/, `$1<rect width="100%" height="100%" fill="${bg}"/><style>text{font:10px system-ui,sans-serif;fill:${ink}}</style>`)
      .replace(/width="\d+" height="\d+"/, `width="${vb.width * scale}" height="${vb.height * scale}"`);
    const img = new Image();
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(src);
    try { await img.decode(); } catch (e) { return; }
    withCaption(img, vb.width * scale, vb.height * scale, what, name);
  }

  // ---------- individual hotspots (binary files, one per year) ----------
  const POINTS_LIMIT = 1500000;               // rows per CSV; more than this would exhaust the browser's memory
  const yearCache = new Map();
  let pointsIndex = null, pointsBusy = false;
  const say = (text) => { $("pts-status").textContent = text; };

  async function getJson(url) {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`${url}: ${res.status}`);
    return res.json();
  }
  async function getYear(entry) {
    if (!yearCache.has(entry.year)) {
      const res = await fetch(`data/points/${entry.file}`);
      if (!res.ok) throw new Error(`${entry.file}: ${res.status}`);
      const buf = await res.arrayBuffer();
      if (buf.byteLength !== entry.bytes) throw new Error(`${entry.file}: unexpected size`);
      yearCache.set(entry.year, buf);
    }
    return yearCache.get(entry.year);
  }
  function columns(buf) {                      // layout is documented in src/fogo/points.py
    const head = new DataView(buf), n = head.getUint32(4, true);
    if (head.getUint32(0, true) !== 0x00315046) throw new Error("not a points file");   // bytes "FP1\0"
    const u16 = (i) => new Uint16Array(buf, 8 + 2 * n * i, n);
    return { n, lat: u16(0), lon: u16(1), day: u16(2), time: u16(3), frp: u16(4), sensor: new Uint8Array(buf, 8 + 10 * n, n) };
  }

  async function pointsCsv() {
    if (pointsBusy || !series) return;
    pointsBusy = true; $("csv-points").disabled = true;
    try {
      say("Preparing the individual hotspots…");
      if (!pointsIndex) pointsIndex = await getJson("data/points/index.json");
      const P = pointsIndex, from = Date.parse(iso(weekStartMs(range.a)) + "T00:00:00Z"), to = weekStartMs(range.b) + 6 * DAY;
      const epoch = Date.parse(P.epoch + "T00:00:00Z");
      const years = P.years.filter((y) => Date.UTC(y.year + 1, 0, 1) > from && Date.UTC(y.year, 0, 1) <= to);
      if (!years.length) { say("There are no hotspots in the chosen dates."); return; }
      const mb = years.filter((y) => !yearCache.has(y.year)).reduce((s, y) => s + y.bytes, 0) / 1e6;
      if (mb > 0) say(`Downloading ${years.length} year file${years.length > 1 ? "s" : ""} (${mb.toFixed(1)} MB)…`);

      const south = rect.s - 0.0005, north = rect.n + 0.0005, west = rect.w - 0.0005, east = rect.e + 0.0005;
      const parts = [], out = [];
      let rows = 0, weight = 0;
      parts.push("date,time_utc,latitude,longitude,sensor,frp_mw,harmonized_weight,provisional\n");
      const provisionalFrom = Date.parse(dataThrough + "T00:00:00Z") - PROVISIONAL_DAYS * DAY;
      for (const entry of years) {
        const c = columns(await getYear(entry));
        for (let i = 0; i < c.n; i++) {
          const ms = epoch + c.day[i] * DAY;
          if (ms < from || ms > to) continue;
          const lat = P.origin.lat + c.lat[i] / P.scale, lon = P.origin.lon + c.lon[i] / P.scale;
          if (lat < south || lat > north || lon < west || lon > east) continue;
          if (++rows > POINTS_LIMIT) {
            say(`This area and period hold more than ${fmt.format(POINTS_LIMIT)} hotspots. Choose a smaller area or fewer dates.`);
            return;
          }
          const w = Math.floor((ms - firstMs) / (7 * DAY)), viirs = c.sensor[i] === P.sensors.viirs;
          const after = w >= G.viirs_from_week;
          const wt = viirs ? (after ? ratioFor(isoYearWeek(w).month) : 0) : (after ? 0 : 1);
          weight += wt;
          const t = String(c.time[i]).padStart(4, "0");
          out.push(`${iso(ms)},${t.slice(0, 2)}:${t.slice(2)},${lat.toFixed(3)},${lon.toFixed(3)},${viirs ? "VIIRS" : "MODIS"},${(c.frp[i] / P.frp_scale).toFixed(1)},${wt.toFixed(4)},${ms >= provisionalFrom}\n`);
          if (out.length >= 20000) { parts.push(out.join("")); out.length = 0; }
        }
        await new Promise((r) => setTimeout(r, 0));      // let the page breathe between years
      }
      if (!rows) { say("No hotspots were detected in this area and period."); return; }
      parts.push(out.join(""));
      const url = URL.createObjectURL(new Blob(parts, { type: "text/csv" }));
      const a = Object.assign(document.createElement("a"), { href: url, download: `hotspots_points_${areaTag()}.csv` });
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      say(`Done: ${fmt.format(rows)} individual hotspots. Sum of harmonized_weight: ${fmt.format(Math.round(weight))}.`);
    } catch (e) {
      say("Could not load the individual hotspots. Check your connection and press the button to try again.");
    } finally { pointsBusy = false; $("csv-points").disabled = false; }
  }

  // ---------- events ----------
  function cellAt(ev) {
    const box = $("map").getBoundingClientRect();
    const col = Math.min(G.cols - 1, Math.max(0, Math.floor((ev.clientX - box.left - ML) / mapPx)));
    const row = Math.min(G.rows - 1, Math.max(0, G.rows - 1 - Math.floor((ev.clientY - box.top - MT) / mapPx)));
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
      $("seq-wrap").hidden = view !== "count"; $("div-wrap").hidden = view === "count"; drawCalendar(); drawMonths();
    }));

    const mhost = $("months");
    const mpick = (g) => { mcursor = { year: g.year, month: g.month }; drawMonths(); monthReadout(); };
    mhost.addEventListener("click", (ev) => {
      const svg = mhost.querySelector("svg"); if (!svg) return;
      const box = svg.getBoundingClientRect(), k = box.width / svg.viewBox.baseVal.width;
      const month = Math.floor(((ev.clientX - box.left) / k - 40) / 26) + 1, year = months.minY + Math.floor(((ev.clientY - box.top) / k - 20) / 12);
      const g = months.byKey.get(year * 100 + month); if (g) mpick(g);
    });
    mhost.addEventListener("keydown", (ev) => {
      const d = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] }[ev.key];
      if (!d) return;
      ev.preventDefault();
      const last = months.list[months.list.length - 1], cur = mcursor || { year: last.year, month: last.month + 1 };
      const g = months.byKey.get((cur.year + d[0]) * 100 + cur.month + d[1]); if (g) mpick(g);
    });
    $("png-calendar").onclick = () => series && svgPng($("calendar").querySelector("svg"), "weekly calendar", `weekly_calendar_${areaTag()}.png`);
    $("png-months").onclick = () => series && svgPng($("months").querySelector("svg"), "monthly calendar", `monthly_calendar_${areaTag()}.png`);
    $("png-map").onclick = () => {
      if (!series) return;
      drawMap();                                // make sure the canvas matches the current layout
      const m = $("map");
      if (m.width && m.height) withCaption(m, m.width, m.height, "map of hotspots in the chosen dates", `map_${areaTag()}.png`);
    };
    $("csv-monthly").onclick = () => series && monthlyCsv();

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
    $("csv-points").onclick = () => pointsCsv();
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
    try { GEO = await getJson("data/geo.json"); } catch (e) { GEO = null; }
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
