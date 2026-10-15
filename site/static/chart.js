// Case-page charts: the exact answer (optionally replayed over time) and each
// model's result along the same line. Every <section class="replay"> on a page
// is one chart; its data is the JSON <script class="chart-data"> inside it.
// Options in the data: exact.line_only (no fill), exact.floor (bed),
// exact.step, band [lo, hi] (shaded pass limit), symmetric (y range around 0),
// series[].dots and series[].join (markers, joined by a thin line).
(function () {
  var NS = "http://www.w3.org/2000/svg";
  function finite(v) { return v !== null && v !== undefined && isFinite(v); }
  function fmt(v) { var a = Math.abs(v); if (a === 0) return "0"; if (a >= 1000) return Math.round(v).toLocaleString(); return String(+v.toPrecision(4)); }

  function init(sec) {
    var el = sec.querySelector("script.chart-data"), svg = sec.querySelector("svg.chart");
    if (!el || !svg) return;
    var D = JSON.parse(el.textContent), E = D.exact, S = D.series || [];
    var narrow = svg.getBoundingClientRect().width < 620;
    var L = narrow ? 64 : 76, R = narrow ? 580 : 980, T = 24, B = narrow ? 300 : 322;
    if (narrow) { svg.setAttribute("viewBox", "0 0 600 380"); svg.classList.add("narrow"); }
    var shown = { exact: true };
    S.forEach(function (s) { var b = sec.querySelector('[data-series="' + s.key + '"]'); shown[s.key] = !b || b.getAttribute("aria-pressed") !== "false"; });
    var frame = E && E.frames ? E.frames.length - 1 : 0;
    var playing = false, timer = null, hoverX = null;
    var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var readout = sec.querySelector(".readout"), tlabel = sec.querySelector(".tlabel");
    var baseText = readout ? readout.textContent : "";

    var x0, x1, y0, y1;
    function ranges() {
    var xs = [], ys = [];
    if (E) {
      E.x.forEach(function (v) { if (finite(v)) xs.push(v); });
      (E.frames || [E.y]).forEach(function (f) { f.forEach(function (v) { if (finite(v)) ys.push(v); }); });
      if (E.floor) E.floor.forEach(function (v) { if (finite(v)) ys.push(v); });
    }
    S.forEach(function (s) {
      s.x.forEach(function (v) { if (finite(v)) xs.push(v); });
      if (shown[s.key] || !D.rescale) s.y.forEach(function (v) { if (finite(v)) ys.push(v); });
    });
    if (D.band) ys.push(D.band[0] * 1.6, D.band[1] * 1.6);
    if (!ys.length) ys = [0, 1];
    x0 = Math.min.apply(null, xs); x1 = Math.max.apply(null, xs);
    y0 = Math.min.apply(null, ys); y1 = Math.max.apply(null, ys);
    if (E && E.x.length > 2 && !D.symmetric && !D.band) {
      // keep the exact answer readable: a model far off the scale is clipped at 60 % of the exact range beyond it
      var ey = [];
      (E.frames || [E.y]).forEach(function (f) { f.forEach(function (v) { if (finite(v)) ey.push(v); }); });
      if (E.floor) E.floor.forEach(function (v) { if (finite(v)) ey.push(v); });
      if (ey.length) {
        var lo = Math.min.apply(null, ey), hi = Math.max.apply(null, ey), sp = (hi - lo) || Math.abs(hi) || 1;
        y1 = Math.min(y1, hi + 0.6 * sp); y0 = Math.max(y0, lo - 0.6 * sp);
      }
    }
    if (D.symmetric) { var a = Math.max(Math.abs(y0), Math.abs(y1)) || 1; y0 = -a; y1 = a; }
    else if (!D.free && (!E || (!E.floor && !E.line_only))) y0 = Math.min(0, y0);
    var pad = (y1 - y0) * 0.08 || 0.1; y1 += pad; if (D.free || D.symmetric || (E && (E.floor || E.line_only))) y0 -= pad;
    if (x1 === x0) x1 = x0 + 1;
    if (y1 === y0) { y1 += 0.5; y0 -= 0.5; }
    }
    ranges();
    var snapX = [];
    if (E) E.x.forEach(function (v, i) { if (finite(v) && finite(E.y ? E.y[i] : 0)) snapX.push(v); });
    S.forEach(function (s) { s.x.forEach(function (v) { if (finite(v)) snapX.push(v); }); });
    function px(x) { return L + (x - x0) / (x1 - x0) * (R - L); }
    function py(y) { return B - (y - y0) / (y1 - y0) * (B - T); }
    function ticks(lo, hi, n) {
      var span = hi - lo, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = mag;
      [1, 2, 2.5, 5, 10].some(function (m) { if (m * mag >= raw) { step = m * mag; return true; } return false; });
      var out = [], v = Math.ceil(lo / step) * step;
      for (; v <= hi + step * 1e-9; v += step) out.push(Math.round(v / step) * step);
      return out;
    }
    function node(tag, attrs, parent) {
      var n = document.createElementNS(NS, tag);
      for (var k in attrs) n.setAttribute(k, attrs[k]);
      (parent || svg).appendChild(n); return n;
    }
    function path(x, y) {
      var d = "", pen = false;
      for (var i = 0; i < x.length; i++) {
        if (!finite(y[i]) || !finite(x[i]) || x[i] < x0 || x[i] > x1) { pen = false; continue; }
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
    function nearest(x, y, at) {
      var best = -1, bd = Infinity;
      for (var i = 0; i < x.length; i++) {
        if (!finite(y[i]) || !finite(x[i])) continue;
        var d = Math.abs(x[i] - at); if (d < bd) { bd = d; best = i; }
      }
      return best < 0 || bd > (x1 - x0) * 0.02 ? null : { x: x[best], y: y[best] };
    }

    function interp(x, y, at) {
      for (var i = 1; i < x.length; i++) {
        if (!finite(y[i]) || !finite(y[i - 1]) || !finite(x[i]) || !finite(x[i - 1])) continue;
        var a = Math.min(x[i - 1], x[i]), b = Math.max(x[i - 1], x[i]);
        if (at >= a && at <= b) { var f = b > a ? (at - x[i - 1]) / (x[i] - x[i - 1]) : 0; return { x: at, y: y[i - 1] + f * (y[i] - y[i - 1]) }; }
      }
      return null;
    }
    function draw() {
      if (D.rescale) ranges();
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var cid = "clip" + Math.random().toString(36).slice(2, 8);
      var defs = node("defs", {}); var cp = node("clipPath", { id: cid }, defs);
      node("rect", { x: L - 6, y: T - 6, width: R - L + 12, height: B - T + 12 }, cp);
      if (D.band) node("rect", { x: L, y: py(D.band[1]), width: R - L, height: Math.max(0, py(D.band[0]) - py(D.band[1])), "class": "band" });
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
      else if (!D.symmetric && !D.free && !(E && E.line_only)) node("rect", { x: L, y: B, width: R - L, height: 8, fill: "var(--bed-soft)" });
      (D.labels || []).forEach(function (lb) {
        var t = node("text", { x: px(lb.x), y: T + 2, "text-anchor": "middle", "class": "axl", "font-weight": 600 }); t.textContent = lb.text;
      });
      if (D.dam !== null && D.dam !== undefined && D.dam >= x0 && D.dam <= x1) {
        node("line", { x1: px(D.dam), x2: px(D.dam), y1: T + 10, y2: B, "class": "dam" });
        var dl = node("text", { x: px(D.dam) + 6, y: T + 14, "class": "axl", "font-size": 12 }); dl.textContent = "dam";
      }
      var final = !E || !E.frames || frame === E.frames.length - 1;
      if (E && shown.exact) {
        var ey = E.frames ? E.frames[frame] : E.y;
        if (!E.step && !E.floor && !E.line_only) node("path", { d: path(E.x, ey) + "L" + px(E.x[E.x.length - 1]) + "," + B + " L" + px(E.x[0]) + "," + B + " Z", "class": "exact-area" });
        node("path", { d: E.step ? stepPath(E.x, ey) : path(E.x, ey), "class": "exact" + (E.target ? " target" : "") });
      }
      if (final) {
        S.forEach(function (s) {
          if (!shown[s.key]) return;
          if (s.dots) {
            if (s.join) node("path", { d: path(s.x, s.y), "class": "model thin", stroke: s.color, "clip-path": "url(#" + cid + ")" });
            var step = Math.max(1, Math.ceil(s.x.length / 120));
            for (var i = 0; i < s.x.length; i += step) {
              if (!finite(s.y[i]) || s.x[i] < x0 || s.x[i] > x1 || s.y[i] < y0 || s.y[i] > y1) continue;
              var c = node("circle", { cx: px(s.x[i]).toFixed(1), cy: py(s.y[i]).toFixed(1), r: s.join ? 3.6 : 3.2, fill: s.join ? s.color : "var(--sheet)", stroke: s.join ? "var(--sheet)" : s.color, "stroke-width": s.join ? 1 : 1.5 });
              var ct = document.createElementNS(NS, "title"); ct.textContent = s.label + ": " + fmt(s.y[i]); c.appendChild(ct);
            }
          } else {
            var p = node("path", { d: path(s.x, s.y), "class": "model", stroke: s.color, "clip-path": "url(#" + cid + ")" });
            var tt = document.createElementNS(NS, "title"); tt.textContent = s.label; p.appendChild(tt);
          }
        });
      }
      if (hoverX !== null && final) node("line", { x1: px(hoverX), x2: px(hoverX), y1: T, y2: B, "class": "hover" });
      if (tlabel && E && E.times) tlabel.textContent = "t = " + fmt(E.times[frame]) + " s";
      if (!readout) return;
      if (!final) { readout.textContent = "Exact answer at t = " + fmt(E.times[frame]) + " s. Models are compared at the end, t = " + fmt(E.t_end) + " s."; return; }
      if (hoverX !== null) {
        var parts = [(D.xshort || D.xlabel.replace(/ \(.*$/, "")) + " " + fmt(hoverX) + ":"];
        if (E && shown.exact) { var ey2 = E.frames ? E.frames[frame] : E.y, e = interp(E.x, ey2, hoverX) || nearest(E.x, ey2, hoverX); if (e) parts.push((E.label || "exact") + " " + fmt(e.y)); }
        S.forEach(function (s) { if (!shown[s.key]) return; var n = s.dots ? nearest(s.x, s.y, hoverX) : interp(s.x, s.y, hoverX); if (n) parts.push(s.label + " " + fmt(n.y)); });
        readout.textContent = parts.join("  ·  ") + (D.unit ? " " + D.unit : "");
        return;
      }
      if (D.front && E) {
        var fp = [];
        S.forEach(function (s) {
          var f = D.fronts && D.fronts[s.key];
          if (shown[s.key] && f !== undefined) fp.push(s.label + " " + fmt(Math.abs(f)) + " m " + (f < 0 ? "behind" : "ahead"));
        });
        readout.textContent = "Exact front (where the last 5 % of the released water begins) at " + Math.round(D.front_exact).toLocaleString() + " m. Models: " + (fp.length ? fp.join(", ") + " (allowed 2.5 m)." : "none shown.");
      } else readout.textContent = baseText || (S.length ? "Lines are each model's result on its finest grid at the end of the run" + (E ? "; the blue line is the exact answer." : ".") : "");
    }

    sec.querySelectorAll("[data-series]").forEach(function (b) {
      b.addEventListener("click", function () {
        var k = b.getAttribute("data-series"); shown[k] = !shown[k];
        b.setAttribute("aria-pressed", shown[k] ? "true" : "false"); draw();
      });
    });
    svg.addEventListener("pointermove", function (ev) {
      var r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
      var sx = (ev.clientX - r.left) / r.width * vb.width;
      if (sx < L || sx > R) { if (hoverX !== null) { hoverX = null; draw(); } return; }
      var hx = x0 + (sx - L) / (R - L) * (x1 - x0);
      if (D.snap && snapX.length) { var b = snapX[0]; snapX.forEach(function (v) { if (Math.abs(v - hx) < Math.abs(b - hx)) b = v; }); hx = b; }
      hoverX = hx; draw();
    });
    svg.addEventListener("pointerleave", function () { hoverX = null; draw(); });
    var play = sec.querySelector(".play"), scrub = sec.querySelector(".scrub");
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
  }
  document.querySelectorAll("section.replay").forEach(init);
})();
