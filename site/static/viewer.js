// Results viewer: depth maps (exact and models) with a player, a probe read on every map at once, the difference
// from exact, and grid convergence. Data: data/viewer/<test>.json (site/viewer.py).
(function () {
  "use strict";
  var IDX = JSON.parse(document.getElementById("vw-index").textContent);
  function $(id) { return document.getElementById(id); }
  var sel = $("vw-test"), link = $("vw-link");
  var mapsSec = $("vw-maps-sec"), mapsEl = $("vw-maps");
  var convSec = $("vw-conv-sec"), convSvg = $("vw-conv");
  var legend = $("vw-legend"), note = $("vw-maps-note"), staleNote = $("vw-stale-note");
  var timeBox = $("vw-time"), scrub = $("vw-scrub"), tlabel = $("vw-tlabel"), play = $("vw-play");
  var chipsA = $("vw-chips"), chipsB = $("vw-chips2"), hint = $("vw-hint");
  var NS = "http://www.w3.org/2000/svg";
  var D = null, mode = "depth", frame = 0, timer = null, hmax = 1, dmax = 0.01, times = null, speed = 1;
  var hidden = {}, probe = null, ext = null;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fmt(v) { if (v === null || v === undefined || !isFinite(v)) return "–"; var a = Math.abs(v); return a === 0 ? "0" : a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(2) : v.toPrecision(2); }
  function depthStr(v) { if (v === null || v === undefined || !isFinite(v)) return "–"; if (v < 1e-4) return "dry"; return v >= 1 ? v.toFixed(2) + " m" : v >= 0.01 ? (v * 100).toFixed(1) + " cm" : (v * 1000).toFixed(1) + " mm"; }
  function sdepthStr(v) {
    if (v === null || v === undefined || !isFinite(v)) return "–";
    var a = Math.abs(v), sg = v > 0 ? "+" : "−";
    if (a < 5e-7) return "±0";
    return sg + (a >= 1 ? a.toFixed(2) + " m" : a >= 0.01 ? (a * 100).toFixed(1) + " cm" : a >= 1e-3 ? (a * 1000).toFixed(1) + " mm" : (a * 1000).toPrecision(2) + " mm");
  }

  // depth: a perceptual ramp from pale aqua to deep navy; difference: blue (too shallow) to orange (too deep)
  var DEPTH = [[214, 238, 245], [158, 210, 232], [94, 170, 214], [44, 125, 190], [18, 82, 150], [8, 46, 102]];
  function ramp(stops, t) {
    t = Math.max(0, Math.min(1, t)) * (stops.length - 1);
    var i = Math.min(stops.length - 2, Math.floor(t)), k = t - i, a = stops[i], b = stops[i + 1];
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  }
  function depthColor(t) { return ramp(DEPTH, Math.pow(Math.max(0, t), 0.85)); }
  var NEG = [[244, 244, 244], [146, 197, 222], [67, 147, 195], [33, 102, 172], [5, 48, 97]];
  var POS = [[244, 244, 244], [244, 165, 130], [214, 96, 77], [178, 24, 43], [103, 0, 31]];
  function diffColor(t) { t = Math.max(-1, Math.min(1, t)); return ramp(t < 0 ? NEG : POS, Math.abs(t)); }

  function clock(t) {
    if (t < 120) return "t = " + fmt(t) + " s";
    var hh = Math.floor(t / 3600), mm = Math.round((t - hh * 3600) / 60);
    if (mm === 60) { hh++; mm = 0; }
    return "t = " + (hh ? hh + " h " : "") + (mm < 10 && hh ? "0" : "") + mm + " min";
  }
  function frameIndexFor(f, t) {
    if (!f || !f.frames) return null;
    var best = 0, bd = Infinity;
    f.frames.t.forEach(function (ft, k) { var d = Math.abs(ft - t); if (d < bd) { bd = d; best = k; } });
    return bd <= 0.51 * (times.length > 1 ? (times[times.length - 1] - times[0]) / (times.length - 1) : Infinity) ? best : null;
  }
  function cellAt(g, h, x, y) {  // a field's value at a world point (its own cell)
    if (!g || !h) return null;
    var i = Math.floor((x - g.x0) / g.dx), j = Math.floor((y - g.y0) / g.dx);
    if (i < 0 || j < 0 || i >= g.nx || j >= g.ny) return null;
    var v = h[j * g.nx + i];
    return v === undefined ? null : v;
  }
  function exactAt(h, x, y) { return D.exact ? cellAt(D.exact, h, x, y) : null; }

  // what one tile shows now: {g: grid, h: values, t: its time, exact: the exact values on g (difference mode)}
  function tileState(key) {
    var isExact = key === "exact";
    var f = isExact ? D.exact : (D.models.filter(function (m) { return m.key === key; })[0] || {}).field;
    if (!f) return null;
    var t = times ? times[frame] : D.t_end, idx = times ? frameIndexFor(f, t) : null;
    // depth: every map follows the player; difference: models are compared at the end of the run, where the exact
    // answer has been computed on each model's own grid
    var useFrame = !!(times && f.frames && idx !== null && (isExact || mode !== "diff"));
    return { f: f, g: useFrame ? f.frames.grid : f, h: useFrame ? f.frames.h[idx] : f.h, t: useFrame ? f.frames.t[idx] : (f.t || D.t_end), isExact: isExact };
  }
  function valueOf(st, x, y) {
    var v = cellAt(st.g, st.h, x, y);
    if (mode !== "diff" || st.isExact || v === null) return v;
    var f = st.f, e = null;
    if (f.exact_h) e = cellAt(f, f.exact_h, x, y); else if (D.exact) e = exactAt(D.exact.h, x, y);
    return e === null ? null : v - e;
  }

  function drawMap(canvas, st) {
    var W = canvas.width, H = canvas.height, ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, W, H);
    if (!st || !st.h) return;
    var f = st.g, h = st.h;
    var sx = W / (ext.x1 - ext.x0), sy = H / (ext.y1 - ext.y0);
    var img = ctx.createImageData(f.nx, f.ny), px = img.data;
    var diff = mode === "diff" && !st.isExact;
    for (var j = 0; j < f.ny; j++) for (var i = 0; i < f.nx; i++) {
      var v = h[j * f.nx + i], o = ((f.ny - 1 - j) * f.nx + i) * 4;
      if (v === null || v === undefined) { px[o + 3] = 0; continue; }
      var c;
      if (diff) {
        var e = st.f.exact_h ? st.f.exact_h[j * f.nx + i] : exactAt(D.exact.h, f.x0 + (i + 0.5) * f.dx, f.y0 + (j + 0.5) * f.dx);
        if (e === null || e === undefined) { px[o + 3] = 0; continue; }
        if (v < 1e-4 && e < 1e-4) { px[o + 3] = 0; continue; }
        c = diffColor((v - e) / dmax);
      } else {
        if (v < 1e-4) { px[o + 3] = 0; continue; }
        c = depthColor(v / hmax);
      }
      px[o] = c[0]; px[o + 1] = c[1]; px[o + 2] = c[2]; px[o + 3] = 255;
    }
    var off = document.createElement("canvas"); off.width = f.nx; off.height = f.ny; off.getContext("2d").putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(off, (f.x0 - ext.x0) * sx, H - (f.y0 + f.ny * f.dx - ext.y0) * sy, f.nx * f.dx * sx, f.ny * f.dx * sy);
    if (probe) {  // the crosshair, at the same world point on every map
      var px0 = (probe.x - ext.x0) * sx, py0 = H - (probe.y - ext.y0) * sy, r = Math.max(5, W / 60);
      ctx.save();
      ctx.lineWidth = Math.max(1.5, W / 400);
      ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.beginPath(); ctx.arc(px0, py0, r, 0, 2 * Math.PI); ctx.stroke();
      ctx.strokeStyle = "#111"; ctx.lineWidth *= 0.6;
      ctx.beginPath(); ctx.arc(px0, py0, r, 0, 2 * Math.PI);
      ctx.moveTo(px0 - 2.4 * r, py0); ctx.lineTo(px0 - r, py0); ctx.moveTo(px0 + r, py0); ctx.lineTo(px0 + 2.4 * r, py0);
      ctx.moveTo(px0, py0 - 2.4 * r); ctx.lineTo(px0, py0 - r); ctx.moveTo(px0, py0 + r); ctx.lineTo(px0, py0 + 2.4 * r);
      ctx.stroke(); ctx.restore();
    }
  }

  function extent() {
    var fs = (D.exact ? [D.exact] : []).concat(D.models.filter(function (m) { return m.field; }).map(function (m) { return m.field; }));
    var e = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
    fs.forEach(function (f) { e.x0 = Math.min(e.x0, f.x0); e.y0 = Math.min(e.y0, f.y0); e.x1 = Math.max(e.x1, f.x0 + f.nx * f.dx); e.y1 = Math.max(e.y1, f.y0 + f.ny * f.dx); });
    return e;
  }

  function scales() {
    hmax = 0; var diffs = [];
    var fs = (D.exact ? [D.exact] : []).concat(D.models.filter(function (m) { return m.field; }).map(function (m) { return m.field; }));
    fs.forEach(function (f) {
      [f.h].concat(f.frames ? f.frames.h : []).forEach(function (h) { h.forEach(function (v) { if (v !== null && v > hmax) hmax = v; }); });
    });
    hmax = hmax || 1;
    if (D.exact) D.models.forEach(function (m) {
      var f = m.field; if (!f) return;
      for (var j = 0; j < f.ny; j += 2) for (var i = 0; i < f.nx; i += 2) {
        var v = f.h[j * f.nx + i], e = f.exact_h ? f.exact_h[j * f.nx + i] : exactAt(D.exact.h, f.x0 + (i + 0.5) * f.dx, f.y0 + (j + 0.5) * f.dx);
        if (v !== null && e !== null && e !== undefined) diffs.push(Math.abs(v - e));
      }
    });
    diffs.sort(function (a, b) { return a - b; });
    dmax = diffs.length ? Math.max(diffs[Math.floor(0.95 * (diffs.length - 1))], 1e-4) : 0.01;
  }

  function legendHtml() {
    var stops = [], k;
    if (mode === "diff") {
      for (k = 0; k <= 20; k++) { var c = diffColor(-1 + k / 10); stops.push("rgb(" + c.map(Math.round).join(",") + ") " + k * 5 + "%"); }
      legend.innerHTML = '<div class="vw-bar" style="background:linear-gradient(90deg,' + stops.join(",") + ')"></div><div class="vw-ticks"><span>' + sdepthStr(-dmax) + ' too shallow</span><span>matches</span><span>' + sdepthStr(dmax) + " too deep</span></div>";
    } else {
      for (k = 0; k <= 10; k++) { var d = depthColor(k / 10); stops.push("rgb(" + d.map(Math.round).join(",") + ") " + k * 10 + "%"); }
      legend.innerHTML = '<div class="vw-leg-row"><span class="vw-dry" title="dry"></span><div class="vw-bar" style="background:linear-gradient(90deg,' + stops.join(",") + ')"></div></div><div class="vw-ticks"><span>dry</span><span>' + depthStr(hmax / 2) + "</span><span>" + depthStr(hmax) + " deep</span></div>";
    }
  }

  function readouts() {  // each tile's value at the probe
    mapsEl.querySelectorAll("figure").forEach(function (fig) {
      var out = fig.querySelector(".vw-read"), key = fig.getAttribute("data-key");
      if (!probe) { out.textContent = ""; return; }
      var st = tileState(key), v = st ? valueOf(st, probe.x, probe.y) : null;
      out.textContent = mode === "diff" && key !== "exact" ? sdepthStr(v) : depthStr(v);
    });
  }

  function renderMaps() {
    if (!D || !D.two_d) return;
    var t = times ? times[frame] : D.t_end, stale = 0;
    mapsEl.querySelectorAll("figure").forEach(function (fig) {
      var cv = fig.querySelector("canvas"), st = tileState(fig.getAttribute("data-key"));
      if (!st) return;
      var isStale = !!(times && Math.abs(t - st.t) > 1e-6 * Math.max(1, t));
      fig.classList.toggle("vw-stale", isStale);
      if (isStale && !fig.hidden) stale++;
      drawMap(cv, st);
    });
    readouts();
    if (times) {
      tlabel.textContent = clock(t);
      scrub.style.setProperty("--pct", (times.length > 1 ? 100 * frame / (times.length - 1) : 100) + "%");
    }
    staleNote.hidden = !stale;
    staleNote.textContent = mode === "diff" ? "Differences are taken at the end of the run, where the exact answer is computed on each model's own grid." :
      stale ? "Faded maps: the model kept no snapshot at this time, so its final state is shown." : "";
    if (mode === "diff") staleNote.hidden = false;
    legendHtml();
  }

  function scoreChip(sc) { return sc ? '<span class="vw-chip-v score ' + sc.k + '">' + esc(sc.l) + '</span>' : ''; }
  // ── model chips (shared by the maps and the convergence chart) ────────────
  function chipModels() {
    return D.models.filter(function (m) { return m.field || (m.conv && m.conv.errors && m.conv.errors.length > 1); });
  }
  function renderChips() {
    var ms = chipModels();
    var html = ms.length > 1 ? ms.map(function (m) {
      var on = !hidden[m.key];
      return '<button type="button" class="vw-chip" data-key="' + esc(m.key) + '" aria-pressed="' + on + '"><span class="sw" style="background:' + esc(m.color) + '"></span>' +
        esc(m.label.split(" · ")[0]) + (m.label.indexOf(" · ") > 0 ? ' <span class="vw-chip-sub">' + esc(m.label.split(" · ").slice(1).join(" · ")) + "</span>" : "") +
        scoreChip(m.score) + "</button>";
    }).join("") + '<span class="vw-chip-all"><button type="button" class="linkish" data-all="1">All</button> · <button type="button" class="linkish" data-all="best">Closest half</button></span>' : "";
    [chipsA, chipsB].forEach(function (box) {
      box.innerHTML = html;
      box.querySelectorAll("[data-key]").forEach(function (b) {
        b.addEventListener("click", function () { var k = b.getAttribute("data-key"); hidden[k] = !hidden[k]; applyHidden(); });
      });
      box.querySelectorAll("[data-all]").forEach(function (b) {
        b.addEventListener("click", function () {
          var w = b.getAttribute("data-all");
          var sc = ms.map(function (m) { return m.score && m.score.s !== null ? m.score.s : Infinity; }).sort(function (a, b) { return a - b; });
          var cut = sc[Math.max(0, Math.ceil(sc.length / 2) - 1)];
          ms.forEach(function (m) { hidden[m.key] = w === "1" ? false : !(m.score && m.score.s !== null && m.score.s <= cut); });
          applyHidden();
        });
      });
    });
  }
  function applyHidden() {
    [chipsA, chipsB].forEach(function (box) {
      box.querySelectorAll("[data-key]").forEach(function (b) { b.setAttribute("aria-pressed", hidden[b.getAttribute("data-key")] ? "false" : "true"); });
    });
    mapsEl.querySelectorAll("figure").forEach(function (fig) { var k = fig.getAttribute("data-key"); fig.hidden = k !== "exact" && !!hidden[k]; });
    convSvg.querySelectorAll("[data-key]").forEach(function (e) { e.style.display = hidden[e.getAttribute("data-key")] ? "none" : ""; });
    document.querySelectorAll("#vw-table tbody tr").forEach(function (tr) { tr.classList.toggle("vw-off", !!hidden[tr.getAttribute("data-key")]); });
    renderMaps();
  }

  // ── maps ───────────────────────────────────────────────────────────────────
  function buildMaps() {
    mapsEl.innerHTML = ""; probe = null;
    var ms = D.models.filter(function (m) { return m.field; });
    if (!D.two_d || (!ms.length && !D.exact)) { mapsSec.hidden = true; return; }
    mapsSec.hidden = false;
    ext = extent();
    var aspect = (ext.y1 - ext.y0) / (ext.x1 - ext.x0);
    var W = 720, H = Math.max(80, Math.round(W * aspect));
    if (H > 840) { W = Math.round(840 / aspect); H = 840; }
    var cards = (D.exact ? [{ key: "exact", label: "Exact answer", color: "var(--water)", score: null }] : []).concat(ms);
    cards.forEach(function (m) {
      var fig = document.createElement("figure"); fig.className = "vw-map" + (m.key === "exact" ? " vw-exact" : ""); fig.setAttribute("data-key", m.key);
      var b = m.score ? '<span class="score sm ' + m.score.k + '">' + esc(m.score.l) + " off</span>" : "";
      fig.innerHTML = '<figcaption><span class="sw" style="background:' + esc(m.color) + '"></span><span class="vw-name">' + esc(m.label) + "</span> " + b + '<output class="vw-read" aria-live="off"></output></figcaption>';
      var cv = document.createElement("canvas"); cv.width = W; cv.height = H; cv.setAttribute("data-key", m.key);
      cv.setAttribute("role", "img"); cv.setAttribute("aria-label", "Depth map: " + m.label);
      cv.title = "Click to enlarge";
      fig.appendChild(cv); mapsEl.appendChild(fig);
      function at(e) {
        var r = cv.getBoundingClientRect();
        return { x: ext.x0 + (e.clientX - r.left) / r.width * (ext.x1 - ext.x0), y: ext.y1 - (e.clientY - r.top) / r.height * (ext.y1 - ext.y0) };
      }
      cv.addEventListener("pointermove", function (e) { probe = at(e); renderMaps(); });
      cv.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") { probe = null; renderMaps(); } });
      cv.addEventListener("click", function (e) {
        if (e.pointerType === "touch") return;  // a tap places the probe; the button enlarges on touch
        var big = !fig.classList.contains("vw-big");
        mapsEl.querySelectorAll(".vw-big").forEach(function (o) { o.classList.remove("vw-big"); });
        if (big) fig.classList.add("vw-big");
        renderMaps();
      });
    });
    var ts = [];
    [D.exact].concat(ms.map(function (m) { return m.field; })).forEach(function (f) { if (f && f.frames) ts = ts.concat(f.frames.t); });
    ts = ts.filter(function (v, i, a) { return a.indexOf(v) === i; }).sort(function (a, b) { return a - b; });
    times = ts.length > 1 ? ts : null;
    timeBox.hidden = !times;
    if (times) { scrub.max = String(times.length - 1); frame = times.length - 1; scrub.value = String(frame); }
    document.querySelector('[data-mode="diff"]').hidden = !D.exact;
    if (!D.exact) setMode("depth", true);
    note.textContent = (D.exact ? "The exact answer and each model's finest grid, on one colour scale." : "Each model's finest grid, on one colour scale (this test has no exact map: it is judged on gauges and water balance).") +
      " Dry ground is shown in sand. Maps are binned to at most 96 cells along the longer side" + (times ? ", frames over time to 48." : ".");
    scales(); renderMaps();
  }

  // ── convergence ────────────────────────────────────────────────────────────
  function highlight(key) {
    convSvg.classList.toggle("vw-hl", !!key);
    convSvg.querySelectorAll("[data-key]").forEach(function (e) { e.classList.toggle("on", e.getAttribute("data-key") === key); });
    document.querySelectorAll("#vw-table tbody tr").forEach(function (tr) { tr.classList.toggle("vw-on", tr.getAttribute("data-key") === key); });
  }
  function buildConv() {
    var ms = D.models.filter(function (m) { return m.conv && m.conv.errors && m.conv.errors.length > 1; });
    convSec.hidden = !ms.length;
    if (!ms.length) return;
    while (convSvg.firstChild) convSvg.removeChild(convSvg.firstChild);
    var xs = [], ys = [];
    ms.forEach(function (m) { m.conv.spacings.forEach(function (v) { xs.push(v); }); m.conv.errors.forEach(function (v) { if (v > 0) ys.push(v); }); });
    var lx0 = Math.log10(Math.min.apply(null, xs)) - 0.1, lx1 = Math.log10(Math.max.apply(null, xs)) + 0.1;
    var ly0 = Math.floor(Math.log10(Math.min.apply(null, ys)) - 0.2), ly1 = Math.ceil(Math.log10(Math.max.apply(null, ys)) + 0.1);
    var narrow = (convSvg.clientWidth || 1000) < 600, L = narrow ? 104 : 80, R = narrow ? 585 : 980, T = 20, B = 370;
    convSvg.setAttribute("viewBox", "0 0 " + (narrow ? 600 : 1000) + " 420");
    function px(v) { return L + (Math.log10(v) - lx0) / (lx1 - lx0) * (R - L); }
    function py(v) { return B - (Math.log10(v) - ly0) / (ly1 - ly0) * (B - T); }
    function node(n, a, p) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); (p || convSvg).appendChild(e); return e; }
    for (var d = ly0; d <= ly1; d++) {
      node("line", { x1: L, x2: R, y1: py(Math.pow(10, d)), y2: py(Math.pow(10, d)), "class": "grid" });
      var tx = node("text", { x: L - 8, y: py(Math.pow(10, d)) + 4, "text-anchor": "end", "class": "axl" }); tx.textContent = d >= -4 && d <= 4 ? String(+Math.pow(10, d).toPrecision(1)) : "1e" + d;
    }
    var xt = []; ms.forEach(function (m) { m.conv.spacings.forEach(function (v) { if (xt.indexOf(v) < 0) xt.push(v); }); });
    xt.forEach(function (v) { var t = node("text", { x: px(v), y: B + 18, "text-anchor": "middle", "class": "axl" }); t.textContent = fmt(v); });
    var xl = node("text", { x: (L + R) / 2, y: B + 42, "text-anchor": "middle", "class": "axl" }); xl.textContent = "Grid spacing (m)";
    var yl = node("text", { x: narrow ? 26 : 18, y: (T + B) / 2, transform: "rotate(-90 " + (narrow ? 26 : 18) + " " + (T + B) / 2 + ")", "text-anchor": "middle", "class": "axl" });
    yl.textContent = (ms[0].conv.norm || "L1") + " error in " + (ms[0].conv.variable || "h");
    var best = ms.slice().sort(function (a, b) { return a.conv.errors[0] - b.conv.errors[0]; })[0], pmin = best.conv.min || 0.8;
    var sp = best.conv.spacings, er = best.conv.errors, ic = sp.indexOf(Math.max.apply(null, sp));
    var xa = Math.min.apply(null, sp), ya = er[ic] * Math.pow(xa / sp[ic], pmin);
    node("line", { x1: px(sp[ic]), y1: py(er[ic]), x2: px(xa), y2: py(ya), "class": "need" });
    var nl = node("text", { x: (px(xa) + px(sp[ic])) / 2, y: (py(ya) + py(er[ic])) / 2 + 22, "class": "axl need-l", "text-anchor": "middle" }); nl.textContent = "minimum rate " + pmin;
    var tb = document.querySelector("#vw-table tbody"), rows = "";
    ms.forEach(function (m) {
      var pts = m.conv.spacings.map(function (s, i) { return [s, m.conv.errors[i]]; }).filter(function (p) { return p[1] > 0; }).sort(function (a, b) { return a[0] - b[0]; });
      var g = node("g", { "data-key": m.key, "class": "vw-series" });
      var path = node("path", { d: pts.map(function (p, i) { return (i ? "L" : "M") + px(p[0]).toFixed(1) + "," + py(p[1]).toFixed(1); }).join(" "), fill: "none", stroke: m.color, "stroke-width": 2.2 }, g);
      var hitp = node("path", { d: path.getAttribute("d"), fill: "none", stroke: "transparent", "stroke-width": 14 }, g);
      void hitp;
      pts.forEach(function (p) {
        var c = node("circle", { cx: px(p[0]), cy: py(p[1]), r: 4, fill: m.color, stroke: "var(--sheet)", "stroke-width": 1.5 }, g);
        var tt = document.createElementNS(NS, "title"); tt.textContent = m.label + ": error " + fmt(p[1]) + " at grid " + fmt(p[0]) + " m"; c.appendChild(tt);
      });
      g.addEventListener("mouseenter", function () { highlight(m.key); });
      g.addEventListener("mouseleave", function () { highlight(null); });
      var cv = { pass: "as designed", fail: "slower", inconclusive: "not settled", at_floor: "at its precision" }[m.conv.verdict] || "–";
      rows += '<tr data-key="' + esc(m.key) + '"><td><span class="sw" style="background:' + esc(m.color) + '"></span> ' + esc(m.label) + "</td><td class=\"num\">" + (m.score ? '<span class="score sm ' + m.score.k + '">' + esc(m.score.l) + "</span>" : "–") +
        '</td><td class="num">' + fmt(m.conv.order) + "</td><td>" + (m.conv.ci ? fmt(m.conv.ci[0]) + " to " + fmt(m.conv.ci[1]) : "–") + "</td><td>" + cv + "</td></tr>";
    });
    tb.innerHTML = rows;
    tb.querySelectorAll("tr").forEach(function (tr) {
      tr.addEventListener("mouseenter", function () { highlight(tr.getAttribute("data-key")); });
      tr.addEventListener("mouseleave", function () { highlight(null); });
    });
  }

  // ── player ─────────────────────────────────────────────────────────────────
  var ICON_PLAY = '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg>';
  var ICON_PAUSE = '<svg viewBox="0 0 18 18" aria-hidden="true"><rect x="3" y="2" width="4" height="14"/><rect x="11" y="2" width="4" height="14"/></svg>';
  function stop() { if (timer) { clearInterval(timer); timer = null; } play.setAttribute("aria-label", "Play"); play.innerHTML = ICON_PLAY; }
  function goto(i) { if (!times) return; frame = Math.max(0, Math.min(times.length - 1, i)); scrub.value = String(frame); renderMaps(); }
  function start() {
    if (!times) return;
    if (frame >= times.length - 1) frame = 0;
    play.setAttribute("aria-label", "Pause"); play.innerHTML = ICON_PAUSE;
    timer = setInterval(function () {
      if (frame >= times.length - 1) { stop(); return; }
      goto(frame + 1);
    }, 220 / speed);
  }
  play.addEventListener("click", function () { if (timer) stop(); else start(); });
  $("vw-back").addEventListener("click", function () { stop(); goto(frame - 1); });
  $("vw-fwd").addEventListener("click", function () { stop(); goto(frame + 1); });
  scrub.addEventListener("input", function () { stop(); goto(+scrub.value); });
  document.querySelectorAll("[data-speed]").forEach(function (b) {
    b.addEventListener("click", function () {
      speed = +b.getAttribute("data-speed");
      document.querySelectorAll("[data-speed]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      if (timer) { stop(); start(); }
    });
  });
  document.addEventListener("keydown", function (e) {
    if (!times || mapsSec.hidden || e.altKey || e.ctrlKey || e.metaKey) return;
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "select" || tag === "textarea" || (tag === "button" && e.key === " ")) return;
    if (e.key === " ") { e.preventDefault(); if (timer) stop(); else start(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); stop(); goto(frame + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); stop(); goto(frame - 1); }
    else if (e.key === "Home") { stop(); goto(0); }
    else if (e.key === "End") { stop(); goto(times.length - 1); }
  });

  function setMode(m, quiet) {
    mode = m;
    document.querySelectorAll("[data-mode]").forEach(function (o) { o.setAttribute("aria-pressed", o.getAttribute("data-mode") === m ? "true" : "false"); });
    hint.textContent = "Point at any map to read every model's " + (m === "diff" ? "difference from the exact depth" : "depth") + " at that spot. Click a map to enlarge it.";
    if (!quiet) renderMaps();
  }
  document.querySelectorAll("[data-mode]").forEach(function (b) { b.addEventListener("click", function () { setMode(b.getAttribute("data-mode")); }); });

  function load(sid) {
    stop();
    link.href = "tests/" + encodeURIComponent(sid) + ".html";
    try { history.replaceState(null, "", "#" + sid); } catch (e) { /* file:// */ }
    fetch("data/viewer/" + encodeURIComponent(sid) + ".json").then(function (r) { return r.json(); }).then(function (d) {
      D = d; hidden = {};
      buildMaps(); buildConv(); renderChips(); chipsB.hidden = !mapsSec.hidden; applyHidden();
    }).catch(function () { mapsSec.hidden = true; convSec.hidden = true; });
  }
  sel.addEventListener("change", function () { load(sel.value); });
  function stickTop() { var h = document.querySelector(".site-head"); if (h) $("vw-player").style.top = h.offsetHeight + "px"; }
  stickTop(); window.addEventListener("resize", stickTop);
  window.addEventListener("hashchange", function () {
    var w = decodeURIComponent((location.hash || "").slice(1));
    if (w && w !== sel.value && IDX.tests.some(function (t) { return t.sid === w; })) { sel.value = w; load(w); }
  });
  var want = decodeURIComponent((location.hash || "").slice(1)) || IDX.first;
  if (IDX.tests.some(function (t) { return t.sid === want; })) sel.value = want;
  if (sel.value) load(sel.value);
})();
