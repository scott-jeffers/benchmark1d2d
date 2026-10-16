// Results viewer: depth maps (exact and models) with a time slider, difference from exact,
// and grid convergence. Data: data/viewer/<test>.json (site/viewer.py).
(function () {
  "use strict";
  var IDX = JSON.parse(document.getElementById("vw-index").textContent);
  var sel = document.getElementById("vw-test"), link = document.getElementById("vw-link");
  var mapsSec = document.getElementById("vw-maps-sec"), mapsEl = document.getElementById("vw-maps");
  var convSec = document.getElementById("vw-conv-sec"), convSvg = document.getElementById("vw-conv");
  var legend = document.getElementById("vw-legend"), note = document.getElementById("vw-maps-note");
  var timeBox = document.getElementById("vw-time"), scrub = document.getElementById("vw-scrub"), tlabel = document.getElementById("vw-tlabel");
  var play = document.getElementById("vw-play");
  var NS = "http://www.w3.org/2000/svg";
  var D = null, mode = "depth", frame = 0, timer = null, hmax = 1, dmax = 0.01, times = null;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fmt(v) { if (v === null || v === undefined || !isFinite(v)) return "–"; var a = Math.abs(v); return a === 0 ? "0" : a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(2) : v.toPrecision(2); }
  function dark() { return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.getAttribute("data-theme") !== "light" || document.documentElement.getAttribute("data-theme") === "dark"; }

  // sequential blues for depth, diverging for differences (blue: too shallow, orange: too deep)
  function depthColor(t) {
    t = Math.max(0, Math.min(1, t));
    var a = [222, 238, 250], b = [8, 69, 148];
    return [a[0] + (b[0] - a[0]) * Math.pow(t, 0.8), a[1] + (b[1] - a[1]) * Math.pow(t, 0.8), a[2] + (b[2] - a[2]) * Math.pow(t, 0.8)];
  }
  function diffColor(t) {
    t = Math.max(-1, Math.min(1, t));
    var mid = [242, 242, 242], neg = [33, 102, 172], pos = [214, 96, 77];
    var e = t < 0 ? neg : pos, k = Math.abs(t);
    return [mid[0] + (e[0] - mid[0]) * k, mid[1] + (e[1] - mid[1]) * k, mid[2] + (e[2] - mid[2]) * k];
  }

  function clock(t) {
    if (t < 120) return "t = " + fmt(t) + " s";
    var hh = Math.floor(t / 3600), mm = Math.round((t - hh * 3600) / 60);
    if (mm === 60) { hh++; mm = 0; }
    return "t = " + (hh ? hh + " h " : "") + (mm < 10 && hh ? "0" : "") + mm + " min";
  }
  function fieldAt(f, i) { if (!f) return null; if (f.frames && i !== null && i < f.frames.h.length) return f.frames.h[i]; return f.h; }
  function frameIndexFor(f, t) {
    if (!f || !f.frames) return null;
    var best = 0, bd = Infinity;
    f.frames.t.forEach(function (ft, k) { var d = Math.abs(ft - t); if (d < bd) { bd = d; best = k; } });
    return bd <= 0.51 * (times.length > 1 ? (times[times.length - 1] - times[0]) / (times.length - 1) : Infinity) ? best : null;
  }
  // exact value at a world point (nearest bin)
  function exactAt(h, x, y) {
    var E = D.exact; if (!E || !h) return null;
    var i = Math.floor((x - E.x0) / E.dx), j = Math.floor((y - E.y0) / E.dx);
    if (i < 0 || j < 0 || i >= E.nx || j >= E.ny) return null;
    return h[j * E.nx + i];
  }

  function drawMap(canvas, f, h, ext, exactH, depthOnly) {
    var W = canvas.width, H = canvas.height, ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, W, H);
    if (!f || !h) return;
    var sx = W / (ext.x1 - ext.x0), sy = H / (ext.y1 - ext.y0);
    var img = ctx.createImageData(f.nx, f.ny), px = img.data;
    for (var j = 0; j < f.ny; j++) for (var i = 0; i < f.nx; i++) {
      var v = h[j * f.nx + i], o = ((f.ny - 1 - j) * f.nx + i) * 4;
      if (v === null || v === undefined) { px[o + 3] = 0; continue; }
      var c;
      if (mode === "diff" && !depthOnly) {
        // the exact depth on this model's own grid (computed at build time); else the nearest exact bin
        var e = f.exact_h ? f.exact_h[j * f.nx + i] : exactAt(exactH, f.x0 + (i + 0.5) * f.dx, f.y0 + (j + 0.5) * f.dx);
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
      for (k = 0; k <= 10; k++) { var c = diffColor(-1 + k / 5); stops.push("rgb(" + c.map(Math.round).join(",") + ") " + k * 10 + "%"); }
      legend.innerHTML = '<div class="vw-bar" style="background:linear-gradient(90deg,' + stops.join(",") + ')"></div><div class="vw-ticks"><span>' + fmt(-dmax) + ' m (too shallow)</span><span>0</span><span>+' + fmt(dmax) + ' m (too deep)</span></div>';
    } else {
      for (k = 0; k <= 10; k++) { var d = depthColor(k / 10); stops.push("rgb(" + d.map(Math.round).join(",") + ") " + k * 10 + "%"); }
      legend.innerHTML = '<div class="vw-bar" style="background:linear-gradient(90deg,' + stops.join(",") + ')"></div><div class="vw-ticks"><span>dry</span><span>' + fmt(hmax / 2) + ' m</span><span>' + fmt(hmax) + ' m deep</span></div>';
    }
  }

  function renderMaps() {
    if (!D || !D.two_d) return;
    var ext = extent();
    var t = times ? times[frame] : D.t_end;
    var exactH = D.exact ? D.exact.h : null;  // differences are taken at the end of the run
    mapsEl.querySelectorAll("canvas").forEach(function (cv) {
      var key = cv.getAttribute("data-key");
      var f = key === "exact" ? D.exact : (D.models.filter(function (m) { return m.key === key; })[0] || {}).field;
      if (!f) return;
      var isExact = key === "exact";
      var idx = times ? frameIndexFor(f, t) : null;
      // depth: every map follows the time slider; difference: models are compared at the end of the run,
      // where the exact answer has been computed on each model's own grid
      var useFrame = !!(times && f.frames && idx !== null && (isExact || mode !== "diff"));
      var g = useFrame ? f.frames.grid : f, h = useFrame ? f.frames.h[idx] : f.h;
      var shownT = useFrame ? f.frames.t[idx] : (f.t || D.t_end);
      cv.parentNode.classList.toggle("vw-stale", !!(times && Math.abs(t - shownT) > 1e-6 * Math.max(1, t)));
      drawMap(cv, g, h, ext, mode === "diff" && !isExact ? exactH : null, isExact);
    });
    if (times) tlabel.textContent = clock(t) + (mode === "diff" ? " · differences are at the end of the run" :
      D.models.some(function (m) { return m.field && !m.field.frames; }) ? " · models without snapshots show their final state, faded" : "");
    legendHtml();
  }

  function buildMaps() {
    mapsEl.innerHTML = "";
    var ms = D.models.filter(function (m) { return m.field; });
    if (!D.two_d || (!ms.length && !D.exact)) { mapsSec.hidden = true; return; }
    mapsSec.hidden = false;
    var ext = extent(), aspect = (ext.y1 - ext.y0) / (ext.x1 - ext.x0);
    var W = 360, H = Math.max(60, Math.round(W * aspect));
    if (H > 420) { W = Math.round(420 / aspect); H = 420; }
    var cards = (D.exact ? [{ key: "exact", label: "Exact answer", color: "var(--water)", verdict: null }] : []).concat(ms);
    cards.forEach(function (m) {
      var fig = document.createElement("figure"); fig.className = "vw-map";
      var b = m.verdict ? '<span class="badge sm ' + (m.verdict === "pass" ? "pass" : "fail") + '">' + (m.verdict === "pass" ? "✓ Passes" : "✗ Fails") + "</span>" : "";
      fig.innerHTML = '<figcaption><span class="sw" style="background:' + esc(m.color) + '"></span>' + esc(m.label) + " " + b + "</figcaption>";
      var cv = document.createElement("canvas"); cv.width = W; cv.height = H; cv.setAttribute("data-key", m.key);
      cv.setAttribute("role", "img"); cv.setAttribute("aria-label", "Depth map: " + m.label);
      fig.appendChild(cv); mapsEl.appendChild(fig);
    });
    // time: the union of frame times (exact frames, model snapshots)
    var ts = [];
    [D.exact].concat(ms.map(function (m) { return m.field; })).forEach(function (f) { if (f && f.frames) ts = ts.concat(f.frames.t); });
    ts = ts.filter(function (v, i, a) { return a.indexOf(v) === i; }).sort(function (a, b) { return a - b; });
    times = ts.length > 1 ? ts : null;
    timeBox.hidden = !times;
    if (times) { scrub.max = String(times.length - 1); frame = times.length - 1; scrub.value = String(frame); }
    document.querySelector('[data-mode="diff"]').hidden = !D.exact;
    if (!D.exact) mode = "depth";
    note.textContent = (D.exact ? "Exact answer and each model's finest grid, on one colour scale." : "Each model's finest grid, on one colour scale (this test has no exact map: it is judged on gauges and water balance).") +
      " Dry cells are blank. Maps are binned to at most 96 cells along the longer side, frames over time to 48.";
    scales(); renderMaps();
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
    var L = 80, R = 980, T = 20, B = 370;
    function px(v) { return L + (Math.log10(v) - lx0) / (lx1 - lx0) * (R - L); }
    function py(v) { return B - (Math.log10(v) - ly0) / (ly1 - ly0) * (B - T); }
    function node(n, a, p) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); (p || convSvg).appendChild(e); return e; }
    for (var d = ly0; d <= ly1; d++) {
      node("line", { x1: L, x2: R, y1: py(Math.pow(10, d)), y2: py(Math.pow(10, d)), "class": "grid" });
      var tx = node("text", { x: L - 8, y: py(Math.pow(10, d)) + 4, "text-anchor": "end", "class": "axl" }); tx.textContent = "1e" + d;
    }
    var xt = []; ms.forEach(function (m) { m.conv.spacings.forEach(function (v) { if (xt.indexOf(v) < 0) xt.push(v); }); });
    xt.forEach(function (v) { var t = node("text", { x: px(v), y: B + 18, "text-anchor": "middle", "class": "axl" }); t.textContent = fmt(v); });
    var xl = node("text", { x: (L + R) / 2, y: B + 42, "text-anchor": "middle", "class": "axl" }); xl.textContent = "Grid spacing (m)";
    var yl = node("text", { x: 18, y: (T + B) / 2, transform: "rotate(-90 18 " + (T + B) / 2 + ")", "text-anchor": "middle", "class": "axl" });
    yl.textContent = (ms[0].conv.norm || "L1") + " error in " + (ms[0].conv.variable || "h");
    // the minimum rate, through the best model's coarsest point
    var best = ms.slice().sort(function (a, b) { return a.conv.errors[0] - b.conv.errors[0]; })[0], pmin = best.conv.min || 0.8;
    var sp = best.conv.spacings, er = best.conv.errors, ic = sp.indexOf(Math.max.apply(null, sp));
    var xa = Math.min.apply(null, sp), ya = er[ic] * Math.pow(xa / sp[ic], pmin);
    node("line", { x1: px(sp[ic]), y1: py(er[ic]), x2: px(xa), y2: py(ya), "class": "need" });
    var nl = node("text", { x: px(xa) + 6, y: py(ya) + 14, "class": "axl" }); nl.textContent = "rate " + pmin;
    var tb = document.querySelector("#vw-table tbody"), rows = "";
    ms.forEach(function (m) {
      var pts = m.conv.spacings.map(function (s, i) { return [s, m.conv.errors[i]]; }).filter(function (p) { return p[1] > 0; }).sort(function (a, b) { return a[0] - b[0]; });
      node("path", { d: pts.map(function (p, i) { return (i ? "L" : "M") + px(p[0]).toFixed(1) + "," + py(p[1]).toFixed(1); }).join(" "), fill: "none", stroke: m.color, "stroke-width": 2.2 });
      pts.forEach(function (p) {
        var c = node("circle", { cx: px(p[0]), cy: py(p[1]), r: 4, fill: m.color, stroke: "var(--sheet)", "stroke-width": 1.5 });
        var tt = document.createElementNS(NS, "title"); tt.textContent = m.label + ": error " + fmt(p[1]) + " at grid " + fmt(p[0]) + " m"; c.appendChild(tt);
      });
      var cv = { pass: "✓ yes", fail: "✗ no", inconclusive: "? not settled", at_floor: "at its precision" }[m.conv.verdict] || "–";
      rows += "<tr><td><span class=\"sw\" style=\"background:" + esc(m.color) + "\"></span> " + esc(m.label) + "</td><td>" + (m.verdict === "pass" ? '<span class="badge sm pass">✓ Passes</span>' : '<span class="badge sm fail">✗ Fails</span>') +
        '</td><td class="num">' + fmt(m.conv.order) + "</td><td>" + (m.conv.ci ? fmt(m.conv.ci[0]) + " to " + fmt(m.conv.ci[1]) : "–") + "</td><td>" + cv +
        '</td><td class="num">' + (m.worst_margin === null || m.worst_margin === undefined ? "–" : (m.worst_margin < 0.01 ? "under 1 % of limit" : m.worst_margin < 1 ? Math.round(m.worst_margin * 100) + " % of limit" : fmt(m.worst_margin) + "× limit")) + "</td></tr>";
    });
    tb.innerHTML = rows;
  }

  function load(sid) {
    stop();
    link.href = "tests/" + encodeURIComponent(sid) + ".html";
    try { history.replaceState(null, "", "#" + sid); } catch (e) { /* file:// */ }
    fetch("data/viewer/" + encodeURIComponent(sid) + ".json").then(function (r) { return r.json(); }).then(function (d) {
      D = d; buildMaps(); buildConv();
    }).catch(function () { mapsSec.hidden = true; convSec.hidden = true; });
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; } play.setAttribute("aria-label", "Play"); play.innerHTML = '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg>'; }
  play.addEventListener("click", function () {
    if (timer) { stop(); return; }
    if (frame >= times.length - 1) frame = 0;
    play.setAttribute("aria-label", "Pause"); play.innerHTML = '<svg viewBox="0 0 18 18" aria-hidden="true"><rect x="3" y="2" width="4" height="14"/><rect x="11" y="2" width="4" height="14"/></svg>';
    timer = setInterval(function () { frame++; if (frame >= times.length) { frame = times.length - 1; stop(); } scrub.value = String(frame); renderMaps(); }, 160);
  });
  scrub.addEventListener("input", function () { stop(); frame = +scrub.value; renderMaps(); });
  document.querySelectorAll("[data-mode]").forEach(function (b) {
    b.addEventListener("click", function () {
      mode = b.getAttribute("data-mode");
      document.querySelectorAll("[data-mode]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      renderMaps();
    });
  });
  sel.addEventListener("change", function () { load(sel.value); });
  var want = decodeURIComponent((location.hash || "").slice(1)) || IDX.first;
  if (IDX.tests.some(function (t) { return t.sid === want; })) sel.value = want;
  if (sel.value) load(sel.value);
})();
