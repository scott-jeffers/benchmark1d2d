// Case-page chart: the exact answer (optionally replayed over time) and each
// model's final result along the same line. Data: <script id="chart-data">.
(function () {
  var el = document.getElementById("chart-data"), svg = document.getElementById("chart");
  if (!el || !svg) return;
  var D = JSON.parse(el.textContent), E = D.exact, S = D.series || [];
  var NS = "http://www.w3.org/2000/svg";
  var narrow = svg.getBoundingClientRect().width < 620;
  var L = narrow ? 64 : 72, R = narrow ? 580 : 980, T = 24, B = narrow ? 300 : 322;
  if (narrow) { svg.setAttribute("viewBox", "0 0 600 380"); svg.classList.add("narrow"); }
  var shown = { exact: true };
  S.forEach(function (s) { var b = document.querySelector('[data-series="' + s.key + '"]'); shown[s.key] = !b || b.getAttribute("aria-pressed") !== "false"; });
  var frame = E && E.frames ? E.frames.length - 1 : 0;
  var playing = false, timer = null;
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function finite(v) { return v !== null && v !== undefined && isFinite(v); }
  var xs = [], ys = [];
  if (E) {
    xs = xs.concat(E.x);
    (E.frames || [E.y]).forEach(function (f) { f.forEach(function (v) { if (finite(v)) ys.push(v); }); });
    if (E.floor) E.floor.forEach(function (v) { if (finite(v)) ys.push(v); });
  }
  S.forEach(function (s) { xs = xs.concat(s.x); s.y.forEach(function (v) { if (finite(v)) ys.push(v); }); });
  var x0 = Math.min.apply(null, E ? E.x : xs), x1 = Math.max.apply(null, E ? E.x : xs);
  var y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
  if (!E || !E.floor) y0 = Math.min(0, y0);
  var pad = (y1 - y0) * 0.08 || 0.1; y1 += pad; if (E && E.floor) y0 -= pad * 0.5;
  function px(x) { return L + (x - x0) / (x1 - x0) * (R - L); }
  function py(y) { return B - (y - y0) / (y1 - y0) * (B - T); }
  function ticks(lo, hi, n) {
    var span = hi - lo, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = mag;
    [1, 2, 2.5, 5, 10].some(function (m) { if (m * mag >= raw) { step = m * mag; return true; } return false; });
    var out = [], v = Math.ceil(lo / step) * step;
    for (; v <= hi + step * 1e-9; v += step) out.push(Math.round(v / step) * step);
    return out;
  }
  function fmt(v) { var a = Math.abs(v); if (a === 0) return "0"; if (a >= 1000) return v.toLocaleString(); return String(+v.toPrecision(4)); }
  function node(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    (parent || svg).appendChild(n); return n;
  }
  function path(x, y, close) {
    var d = "", pen = false;
    for (var i = 0; i < x.length; i++) {
      if (!finite(y[i]) || x[i] < x0 || x[i] > x1) { pen = false; continue; }
      d += (pen ? "L" : "M") + px(x[i]).toFixed(1) + "," + py(y[i]).toFixed(1) + " "; pen = true;
    }
    return d;
  }
  function stepPath(x, y) {
    var d = "";
    for (var i = 0; i < x.length; i++) {
      if (!finite(y[i])) continue;
      var X = px(x[i]).toFixed(1), Y = py(y[i]).toFixed(1);
      d += (d ? "L" + X + "," + (i ? py(y[i - 1]).toFixed(1) : Y) + " L" : "M") + X + "," + Y + " ";
    }
    return d;
  }
  function frontOf(x, y) { var f = null; for (var i = 0; i < x.length; i++) if (finite(y[i]) && y[i] >= 0.001) f = Math.max(f === null ? -Infinity : f, x[i]); return f; }

  function draw() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    ticks(y0, y1, 4).forEach(function (v) {
      node("line", { x1: L, x2: R, y1: py(v), y2: py(v), "class": "gl" });
      var t = node("text", { x: L - 8, y: py(v) + 4, "text-anchor": "end", "class": "ax" }); t.textContent = fmt(v);
    });
    ticks(x0, x1, narrow ? 4 : 8).forEach(function (v) {
      var t = node("text", { x: px(v), y: B + 22, "text-anchor": "middle", "class": "ax" }); t.textContent = fmt(v);
    });
    var xl = node("text", { x: (L + R) / 2, y: B + 46, "text-anchor": "middle", "class": "axl" }); xl.textContent = D.xlabel;
    var yl = node("text", { x: 14, y: (T + B) / 2, "text-anchor": "middle", "class": "axl", transform: "rotate(-90 14 " + (T + B) / 2 + ")" }); yl.textContent = D.ylabel;
    if (E && E.floor) node("path", { d: path(E.x, E.floor) + "L" + px(E.x[E.x.length - 1]) + "," + B + " L" + px(E.x[0]) + "," + B + " Z", "class": "bedfill" });
    else node("rect", { x: L, y: B, width: R - L, height: 8, fill: "var(--bed-soft)" });
    if (D.dam !== null && D.dam !== undefined && D.dam >= x0 && D.dam <= x1) {
      node("line", { x1: px(D.dam), x2: px(D.dam), y1: T + 10, y2: B, "class": "dam" });
      var dl = node("text", { x: px(D.dam) + 6, y: T + 14, "class": "axl", "font-size": 12 }); dl.textContent = "dam";
    }
    var final = !E || !E.frames || frame === E.frames.length - 1;
    if (E && shown.exact) {
      var ey = E.frames ? E.frames[frame] : E.y;
      if (!E.step && !E.floor) node("path", { d: path(E.x, ey) + "L" + px(E.x[E.x.length - 1]) + "," + B + " L" + px(E.x[0]) + "," + B + " Z", "class": "exact-area" });
      node("path", { d: E.step ? stepPath(E.x, ey) : path(E.x, ey), "class": "exact" });
    }
    if (final) {
      S.forEach(function (s) {
        if (!shown[s.key]) return;
        if (s.dots) {
          var step = Math.max(1, Math.ceil(s.x.length / 90));
          for (var i = 0; i < s.x.length; i += step) {
            if (!finite(s.y[i]) || s.x[i] < x0 || s.x[i] > x1) continue;
            node("circle", { cx: px(s.x[i]).toFixed(1), cy: py(s.y[i]).toFixed(1), r: 3.2, fill: "var(--sheet)", stroke: s.color, "stroke-width": 1.5 });
          }
        } else {
          var p = node("path", { d: path(s.x, s.y), "class": "model", stroke: s.color });
          var tt = document.createElementNS(NS, "title"); tt.textContent = s.label; p.appendChild(tt);
        }
      });
    }
    var tl = document.getElementById("tlabel");
    if (tl && E && E.times) tl.textContent = "t = " + fmt(E.times[frame]) + " s";
    var ro = document.getElementById("readout");
    if (ro) {
      if (!final) ro.textContent = "Exact answer at t = " + fmt(E.times[frame]) + " s. Models are compared at the end, t = " + fmt(E.t_end) + " s.";
      else if (D.front && E) {
        var ef = frontOf(E.x, E.frames ? E.frames[frame] : E.y), parts = [];
        S.forEach(function (s) { if (shown[s.key] && D.fronts && D.fronts[s.key] !== undefined) parts.push(s.label + " " + fmt(D.fronts[s.key]) + " m"); });
        ro.textContent = "Exact front (1 mm depth) at " + Math.round(ef).toLocaleString() + " m. Distance from it: " + (parts.length ? parts.join(", ") + " (allowed 2.5 m)." : "none shown.");
      } else if (S.length) ro.textContent = "Lines are each model's result on its finest grid at the end of the run" + (E ? "; the blue line is the exact answer." : ".");
    }
  }

  document.querySelectorAll("[data-series]").forEach(function (b) {
    b.addEventListener("click", function () {
      var k = b.getAttribute("data-series"); shown[k] = !shown[k];
      b.setAttribute("aria-pressed", shown[k] ? "true" : "false"); draw();
    });
  });
  var play = document.getElementById("play"), scrub = document.getElementById("scrub");
  function setPlay(on) {
    playing = on;
    if (play) {
      play.setAttribute("aria-label", on ? "Pause" : "Play");
      play.innerHTML = on ? '<svg viewBox="0 0 18 18" aria-hidden="true"><rect x="3" y="2" width="4" height="14"/><rect x="11" y="2" width="4" height="14"/></svg>'
                          : '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg>';
    }
    if (timer) { clearInterval(timer); timer = null; }
    if (on) {
      if (frame >= E.frames.length - 1) frame = 0;
      timer = setInterval(function () {
        frame++; if (scrub) scrub.value = frame;
        if (frame >= E.frames.length - 1) { frame = E.frames.length - 1; setPlay(false); }
        draw();
      }, Math.max(40, 6000 / E.frames.length));
    }
  }
  if (play && E && E.frames) play.addEventListener("click", function () { setPlay(!playing); });
  if (scrub) scrub.addEventListener("input", function () { frame = +scrub.value; setPlay(false); draw(); });
  draw();
  if (E && E.frames && !reduced && "IntersectionObserver" in window) {
    var once = false;
    new IntersectionObserver(function (es) {
      if (!once && es[0].isIntersecting) { once = true; frame = 0; if (scrub) scrub.value = 0; setPlay(true); }
    }, { threshold: 0.4 }).observe(svg);
  }
})();
