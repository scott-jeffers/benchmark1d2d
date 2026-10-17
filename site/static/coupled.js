// 1D/2D viewer: a coupled sewer/surface run replayed. The surface depth from above, the pipes in long section, the
// exchange at each manhole and the volume accounts, on one clock. Data: data/coupled/<test>/<model>.json (site/coupledview.py).
(function () {
  "use strict";
  var IDX = JSON.parse(document.getElementById("cv-index").textContent);
  function scoreChip(sc) { return sc ? '<span class="vw-chip-v score ' + sc.k + '">' + esc(sc.l) + '</span>' : ''; }
  function $(id) { return document.getElementById(id); }
  var sel = $("cv-test"), modelsBox = $("cv-models"), link = $("cv-link"), story = $("cv-story");
  var map = $("cv-map"), prof = $("cv-prof"), qSvg = $("cv-q"), lvSvg = $("cv-lv"), volSvg = $("cv-vol"), bal = $("cv-bal"), leg = $("cv-leg"), read = $("cv-read");
  var scrub = $("cv-scrub"), tlabel = $("cv-tlabel"), play = $("cv-play");
  var NS = "http://www.w3.org/2000/svg";
  var T = null, R = null, fi = 0, timer = null, speed = 1, hmax = 1, qmax = 1, zlo = 0, zhi = 1, exag = 1, probe = null, chain = null;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fmt(v, d) { if (v === null || v === undefined || !isFinite(v)) return "–"; var a = Math.abs(v); return a === 0 ? "0" : a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 1 ? v.toFixed(d === undefined ? 2 : d) : v.toPrecision(2); }
  function tick(v, range) { var d = range < 0.05 ? 3 : range < 1 ? 2 : range < 10 ? 1 : 0, r = v.toFixed(d); return r === "-0" || /^-0\.0*$/.test(r) ? r.slice(1) : r; }
  function depthStr(v) { if (!isFinite(v) || v < 1e-4) return "dry"; return v >= 1 ? v.toFixed(2) + " m" : v >= 0.01 ? (v * 100).toFixed(1) + " cm" : (v * 1000).toFixed(1) + " mm"; }
  function clock(t) {
    if (t < 120) return "t = " + Math.round(t) + " s";
    var h = Math.floor(t / 3600), m = Math.floor((t - h * 3600) / 60), s = Math.round(t - h * 3600 - m * 60);
    return "t = " + (h ? h + " h " : "") + (h && m < 10 ? "0" : "") + m + " min" + (h ? "" : " " + (s < 10 ? "0" : "") + s + " s");
  }
  function css(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "#888"; }
  function dark() { var e = document.documentElement.getAttribute("data-theme"); return e === "dark" || (e !== "light" && window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches); }
  var DEPTH = [[214, 238, 245], [158, 210, 232], [94, 170, 214], [44, 125, 190], [18, 82, 150], [8, 46, 102]];
  function ramp(stops, t) {
    t = Math.max(0, Math.min(1, t)) * (stops.length - 1);
    var i = Math.min(stops.length - 2, Math.floor(t)), k = t - i, a = stops[i], b = stops[i + 1];
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  }
  function groundColor(t) {  // the bed: low ground darker sand, high ground lighter
    var lo = dark() ? [52, 48, 40] : [214, 200, 176], hi = dark() ? [86, 80, 68] : [244, 238, 226];
    t = Math.max(0, Math.min(1, t));
    return [lo[0] + (hi[0] - lo[0]) * t, lo[1] + (hi[1] - lo[1]) * t, lo[2] + (hi[2] - lo[2]) * t];
  }
  var UP = "#D9622B", DOWN = "#1F78C8";

  // ── surface ──────────────────────────────────────────────────────────────
  var mapGeom = null;
  function sizeMap() {
    var S = R.surface, w = map.clientWidth || 600, lx = S.nx * S.dx, ly = S.ny * S.dx, aspect = ly / lx;
    exag = aspect < 0.3 ? 0.3 / aspect : 1;  // a long thin street is stretched across so it can be seen
    var h = Math.round(Math.min(w * aspect * exag, 560));
    var dpr = window.devicePixelRatio || 1;
    map.style.height = h + "px"; map.width = Math.round(w * dpr); map.height = Math.round(h * dpr);
    mapGeom = { w: w, h: h, dpr: dpr, sx: w / lx, sy: h / ly };
  }
  function drawMap() {
    var S = R.surface, g = mapGeom, ctx = map.getContext("2d"), hs = S.h[fi];
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    var img = ctx.createImageData(S.nx, S.ny), px = img.data;
    var zr = Math.max(zhi - zlo, 1e-9);
    for (var j = 0; j < S.ny; j++) for (var i = 0; i < S.nx; i++) {
      var k = j * S.nx + i, o = ((S.ny - 1 - j) * S.nx + i) * 4, v = hs[k], c;
      if (v >= 1e-4) {
        c = ramp(DEPTH, Math.pow(v / hmax, 0.75));
        // shallow water lets the ground show through
        var a = Math.min(1, 0.35 + v / (0.15 * hmax + 1e-9) * 0.65), gr = groundColor((S.z[k] - zlo) / zr);
        c = [gr[0] + (c[0] - gr[0]) * a, gr[1] + (c[1] - gr[1]) * a, gr[2] + (c[2] - gr[2]) * a];
      } else c = groundColor((S.z[k] - zlo) / zr);
      px[o] = c[0]; px[o + 1] = c[1]; px[o + 2] = c[2]; px[o + 3] = 255;
    }
    var off = document.createElement("canvas"); off.width = S.nx; off.height = S.ny; off.getContext("2d").putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = S.nx * S.ny > 4000;
    ctx.drawImage(off, 0, 0, map.width, map.height);
    ctx.setTransform(g.dpr, 0, 0, g.dpr, 0, 0);
    // the manholes: a ring, and the exchange as an arrow (up: out of the pipe, down: into it) sized by its rate
    R.manholes.forEach(function (mh) {
      var x = (mh.x - S.x0) * g.sx, y = g.h - (mh.y - S.y0) * g.sy, q = mh.q[fi];
      var r = 7, k = Math.sqrt(Math.min(1, Math.abs(q) / qmax));
      if (Math.abs(q) > 1e-5) {
        var col = q > 0 ? UP : DOWN, pulse = (performance.now() / 600) % 1;
        ctx.beginPath(); ctx.arc(x, y, r + 6 + 22 * k * (q > 0 ? pulse : 1 - pulse), 0, Math.PI * 2);
        ctx.strokeStyle = col; ctx.globalAlpha = 0.55 * (q > 0 ? 1 - pulse : pulse); ctx.lineWidth = 2.5; ctx.stroke(); ctx.globalAlpha = 1;
      }
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = dark() ? "#1c2a35" : "#fff"; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = dark() ? "#e2eaf0" : "#16202a"; ctx.stroke();
      ctx.beginPath(); ctx.arc(x, y, r - 3.5, 0, Math.PI * 2); ctx.fillStyle = Math.abs(q) > 1e-5 ? (q > 0 ? UP : DOWN) : (dark() ? "#4a5c6a" : "#a7b4bc"); ctx.fill();
      var lbl = mh.id + (Math.abs(q) > 1e-5 ? (q > 0 ? "  ↑ " : "  ↓ ") + fmt(Math.abs(q), 3) + " m³/s" : "");
      ctx.font = "600 12.5px " + css("--sans"); ctx.textBaseline = "middle";
      var tx = x + r + 8 + 120 > g.w ? x - r - 8 - ctx.measureText(lbl).width : x + r + 8, ty = Math.max(10, Math.min(g.h - 10, y));
      ctx.lineWidth = 4; ctx.strokeStyle = dark() ? "rgba(11,22,30,.9)" : "rgba(255,255,255,.92)"; ctx.lineJoin = "round"; ctx.strokeText(lbl, tx, ty);
      ctx.fillStyle = dark() ? "#e2eaf0" : "#16202a"; ctx.fillText(lbl, tx, ty);
    });
    if (probe) {
      var px0 = probe.px, py0 = probe.py;
      ctx.beginPath(); ctx.arc(px0, py0, 6, 0, Math.PI * 2); ctx.strokeStyle = "#111"; ctx.lineWidth = 1.5; ctx.stroke();
      var i2 = Math.floor(px0 / g.sx / S.dx), j2 = S.ny - 1 - Math.floor(py0 / g.sy / S.dx);
      if (i2 >= 0 && j2 >= 0 && i2 < S.nx && j2 < S.ny) {
        var kk = j2 * S.nx + i2;
        read.textContent = depthStr(hs[kk]) + " · ground " + fmt(S.z[kk], 2) + " m";
      }
    } else read.textContent = "";
  }
  map.addEventListener("pointermove", function (e) { var r = map.getBoundingClientRect(); probe = { px: e.clientX - r.left, py: e.clientY - r.top }; drawMap(); });
  map.addEventListener("pointerleave", function () { probe = null; drawMap(); });

  // ── long section ───────────────────────────────────────────────────────────
  function buildChain() {  // the longest path from an upstream end to an outfall, by length
    var N = R.network, nodes = {}, out = {}, inc = {};
    N.nodes.forEach(function (n) { nodes[n.id] = n; out[n.id] = []; inc[n.id] = 0; });
    N.links.forEach(function (l) { if (out[l.from] && nodes[l.to]) { out[l.from].push(l); inc[l.to]++; } });
    var best = null;
    function walk(id, path, len, seen) {
      if (!out[id].length || seen[id]) { if (!best || len > best.len) best = { path: path.slice(), len: len }; return; }
      seen[id] = true;
      out[id].forEach(function (l) { path.push(l); walk(l.to, path, len + l.length, seen); path.pop(); });
      seen[id] = false;
    }
    N.nodes.forEach(function (n) { if (!inc[n.id]) walk(n.id, [], 0, {}); });
    var links = best ? best.path : [], pts = [], x = 0;
    if (links.length) {
      pts.push({ node: nodes[links[0].from], x: 0 });
      links.forEach(function (l) { x += l.length; pts.push({ node: nodes[l.to], x: x }); });
    }
    return { links: links, pts: pts, len: x, nodes: nodes };
  }
  function el(tag, a, p) { var e = document.createElementNS(NS, tag); for (var k in a) e.setAttribute(k, a[k]); (p || prof).appendChild(e); return e; }
  function drawProfile() {
    while (prof.firstChild) prof.removeChild(prof.firstChild);
    if (!chain || !chain.links.length) return;
    var W = Math.max(300, Math.round(prof.clientWidth || 640)), H = W < 480 ? 280 : 340, L = 54, Rr = 16, Tp = 22, B = 40;
    prof.setAttribute("viewBox", "0 0 " + W + " " + H);
    var mhById = {}; R.manholes.forEach(function (m) { mhById[m.id] = m; });
    // vertical range: inverts to the highest of the rims, heads and street water over the run (a deep dummy junction's top is left out)
    var lo = Infinity, hi = -Infinity;
    chain.pts.forEach(function (p) {
      var n = p.node; lo = Math.min(lo, n.invert);
      if (n.kind === "manhole") hi = Math.max(hi, n.top);
      var hd = n.kind === "outfall" ? [] : R.network.head[n.id] || [];  // an outfall's fixed stage (a capped end) is not a water level to draw
      hd.forEach(function (v) { if (isFinite(v)) hi = Math.max(hi, v); });
      if (mhById[n.id]) mhById[n.id].eta.forEach(function (v) { hi = Math.max(hi, v); });
    });
    chain.links.forEach(function (l) { hi = Math.max(hi, chain.nodes[l.from].invert + l.D); });
    hi += 0.15 * (hi - lo); lo -= 0.06 * (hi - lo);
    function X(x) { return L + x / chain.len * (W - L - Rr); }
    function Y(z) { return Tp + (hi - z) / (hi - lo) * (H - Tp - B); }
    var ink = css("--ink"), ink2 = css("--ink-2"), rule = css("--rule"), water = dark() ? "#5BA7DB" : "#2C7DBE";
    // grid
    for (var k = 0; k <= 4; k++) {
      var z = lo + (hi - lo) * k / 4;
      el("line", { x1: L, x2: W - Rr, y1: Y(z), y2: Y(z), stroke: css("--rule-2") });
      el("text", { x: L - 6, y: Y(z) + 4, "text-anchor": "end", "class": "cv-ax" }).textContent = tick(z, hi - lo);
    }
    el("text", { x: (L + W - Rr) / 2, y: H - 8, "text-anchor": "middle", "class": "cv-ax" }).textContent = "distance along the pipes (m)";
    el("text", { x: 14, y: (Tp + H - B) / 2, "text-anchor": "middle", "class": "cv-ax", transform: "rotate(-90 14 " + (Tp + H - B) / 2 + ")" }).textContent = "level (m)";
    // pipes, and the water in them up to the head (or full)
    chain.links.forEach(function (l, i) {
      var a = chain.pts[i], b = chain.pts[i + 1];
      var ia = a.node.invert + (l.in_offset || 0), ib = b.node.invert + (l.out_offset || 0);
      var ha = (R.network.head[a.node.id] || [])[fi], hb = (R.network.head[b.node.id] || [])[fi];
      if (b.node.closed) hb = ha;  // a capped end: the water stands at the upstream head
      var wa = Math.max(ia, Math.min(isFinite(ha) ? ha : ia, ia + l.D)), wb = Math.max(ib, Math.min(isFinite(hb) ? hb : ib, ib + l.D));
      var d = (R.network.depth[l.id] || [])[fi];
      if (isFinite(d) && b.node.kind === "outfall") wb = Math.max(ib, Math.min(ib + d, ib + l.D));
      el("path", { d: "M" + X(a.x) + "," + Y(ia) + "L" + X(b.x) + "," + Y(ib) + "L" + X(b.x) + "," + Y(wb) + "L" + X(a.x) + "," + Y(wa) + "Z", fill: water, opacity: 0.55 });
      el("path", { d: "M" + X(a.x) + "," + Y(ia) + "L" + X(b.x) + "," + Y(ib) + "M" + X(a.x) + "," + Y(ia + l.D) + "L" + X(b.x) + "," + Y(ib + l.D), stroke: ink2, "stroke-width": 2.2, fill: "none" });
      var f = (R.network.flow[l.id] || [])[fi];
      var mx = (X(a.x) + X(b.x)) / 2, my = (Y(ia + l.D) + Y(ib + l.D)) / 2 - 8;
      el("text", { x: mx, y: my, "text-anchor": "middle", "class": "cv-lbl" }).textContent = l.id + "  " + fmt(f, 3) + " m³/s" + (Math.abs(f) > 1e-6 ? (f > 0 ? " →" : " ←") : "");
    });
    // the head (hydraulic grade line) through the nodes
    var hgl = chain.pts.filter(function (p) { return !(p.node.kind === "outfall" && p.node.closed); }).map(function (p, i) {
      var v = (R.network.head[p.node.id] || [])[fi];
      if (p.node.kind === "outfall") v = Math.min(isFinite(v) ? v : p.node.invert, hi);
      return (i ? "L" : "M") + X(p.x) + "," + Y(isFinite(v) ? v : p.node.invert);
    }).join("");
    el("path", { d: hgl, stroke: water, "stroke-width": 2.4, fill: "none", "stroke-dasharray": "6 4" });
    // nodes: manhole shafts up to the rim, with the street and the water on it
    chain.pts.forEach(function (p) {
      var n = p.node, x = X(p.x), hd = (R.network.head[n.id] || [])[fi];
      if (n.kind === "manhole") {
        var w = 9;
        el("rect", { x: x - w / 2, y: Y(n.top), width: w, height: Math.max(1, Y(n.invert) - Y(n.top)), fill: "none", stroke: ink, "stroke-width": 1.6 });
        if (isFinite(hd)) el("rect", { x: x - w / 2 + 1.5, y: Y(Math.min(hd, n.top)), width: w - 3, height: Math.max(0, Y(n.invert) - Y(Math.min(hd, n.top))), fill: water });
        el("line", { x1: x - 40, x2: x + 40, y1: Y(n.top), y2: Y(n.top), stroke: css("--bed"), "stroke-width": 3 });
        var mh = mhById[n.id];
        if (mh) {
          var eta = mh.eta[fi], q = mh.q[fi];
          if (eta > n.top + 1e-4) el("rect", { x: x - 40, y: Y(eta), width: 80, height: Math.max(1, Y(n.top) - Y(eta)), fill: water, opacity: 0.4 });
          if (Math.abs(q) > 1e-5) {
            var up = q > 0, col = up ? UP : DOWN, y0 = Y(n.top) + (up ? 16 : -26), y1 = Y(n.top) + (up ? -26 : 16);
            el("path", { d: "M" + (x + 14) + "," + y0 + "L" + (x + 14) + "," + y1 + "M" + (x + 8) + "," + (y1 + (up ? 7 : -7)) + "L" + (x + 14) + "," + y1 + "L" + (x + 20) + "," + (y1 + (up ? 7 : -7)), stroke: col, "stroke-width": 3, fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round" });
          }
          el("text", { x: x < W / 2 ? x + 26 : x - 12, y: Y(Math.max(eta, n.top)) - 10, "text-anchor": x < W / 2 ? "start" : "end", "class": "cv-lbl cv-strong cv-halo" }).textContent = n.id + " (manhole)";
        }
      } else {
        el("circle", { cx: x, cy: Y(n.invert + 0.0), r: 4, fill: n.kind === "outfall" ? css("--bed") : ink2 });
        el("text", { x: x + (p.x === 0 ? 6 : -6), y: Y(n.invert) + 16, "text-anchor": p.x === 0 ? "start" : "end", "class": "cv-lbl" }).textContent = n.id + (n.kind === "outfall" ? (n.closed ? " (closed end)" : " (outfall)") : "");
      }
    });
  }

  // ── time charts ──────────────────────────────────────────────────────────
  function chart(svg, series, opts) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = Math.max(280, Math.round(svg.clientWidth || 640)), H = 200, L = 50, Rr = 10, Tp = opts.legend ? 30 : 10, B = 24, t = R.t, t0 = t[0], t1 = t[t.length - 1] || 1;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var lo = opts.lo !== undefined ? opts.lo : Infinity, hi = -Infinity;
    series.forEach(function (s) { s.v.forEach(function (v) { if (isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }); });
    if (opts.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    if (hi - lo < 1e-9) { hi += 0.5; lo -= 0.5; }
    var pad = (hi - lo) * 0.08; hi += pad; if (!(opts.zero && lo === 0)) lo -= pad;
    function X(v) { return L + (v - t0) / (t1 - t0) * (W - L - Rr); }
    function Y(v) { return Tp + (hi - v) / (hi - lo) * (H - Tp - B); }
    function e(tag, a) { var n = document.createElementNS(NS, tag); for (var k in a) n.setAttribute(k, a[k]); svg.appendChild(n); return n; }
    [lo + pad, (lo + hi) / 2, hi - pad].forEach(function (v) {
      e("line", { x1: L, x2: W - Rr, y1: Y(v), y2: Y(v), stroke: css("--rule-2") });
      e("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "cv-ax" }).textContent = tick(v, hi - lo);
    });
    if (opts.zero) e("line", { x1: L, x2: W - Rr, y1: Y(0), y2: Y(0), stroke: css("--ink-2"), "stroke-width": 1 });
    var tsc = t1 > 5400 ? 3600 : 60, tu = tsc === 3600 ? " h" : " min";
    [0, 0.5, 1].forEach(function (f) { var v = t0 + f * (t1 - t0); e("text", { x: X(v), y: H - 6, "text-anchor": f === 0 ? "start" : f === 1 ? "end" : "middle", "class": "cv-ax" }).textContent = (Math.round(v / tsc * 10) / 10) + (f === 1 ? tu : ""); });
    series.forEach(function (s) {
      var d = s.v.map(function (v, i) { return (i ? "L" : "M") + X(t[i]).toFixed(1) + "," + Y(isFinite(v) ? v : 0).toFixed(1); }).join("");
      if (s.fill) {
        if (s.fill === "split") {  // above zero orange, below blue
          var id = "cl" + Math.random().toString(36).slice(2);
          var defs = e("defs", {}); var cp = document.createElementNS(NS, "clipPath"); cp.setAttribute("id", id + "u"); defs.appendChild(cp);
          var r1 = document.createElementNS(NS, "rect"); r1.setAttribute("x", 0); r1.setAttribute("y", 0); r1.setAttribute("width", W); r1.setAttribute("height", Y(0)); cp.appendChild(r1);
          var cp2 = document.createElementNS(NS, "clipPath"); cp2.setAttribute("id", id + "d"); defs.appendChild(cp2);
          var r2 = document.createElementNS(NS, "rect"); r2.setAttribute("x", 0); r2.setAttribute("y", Y(0)); r2.setAttribute("width", W); r2.setAttribute("height", H); cp2.appendChild(r2);
          var area = d + "L" + X(t[t.length - 1]) + "," + Y(0) + "L" + X(t[0]) + "," + Y(0) + "Z";
          e("path", { d: area, fill: UP, opacity: 0.35, "clip-path": "url(#" + id + "u)" });
          e("path", { d: area, fill: DOWN, opacity: 0.35, "clip-path": "url(#" + id + "d)" });
        } else e("path", { d: d + "L" + X(t[t.length - 1]) + "," + Y(s.base || 0) + "L" + X(t[0]) + "," + Y(s.base || 0) + "Z", fill: s.color, opacity: 0.25 });
      }
      e("path", { d: d, fill: "none", stroke: s.color, "stroke-width": s.w || 2, "stroke-dasharray": s.dash || "" });
    });
    e("line", { x1: X(t[fi]), x2: X(t[fi]), y1: Tp, y2: H - B, stroke: css("--fail"), "stroke-width": 1.5, "stroke-dasharray": "3 3" });
    if (opts.legend) {
      var lx = 4;
      opts.legend.forEach(function (s) {
        e("line", { x1: lx, x2: lx + 16, y1: 10, y2: 10, stroke: s.color, "stroke-width": 3, "stroke-dasharray": s.dash || "" });
        var tx = e("text", { x: lx + 20, y: 14, "class": "cv-ax" }); tx.textContent = s.name; lx += 30 + s.name.length * 6.2;
      });
    }
    svg.onclick = function (ev) {
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * W, tt = t0 + (x - L) / (W - L - Rr) * (t1 - t0), best = 0, bd = Infinity;
      t.forEach(function (v, i) { if (Math.abs(v - tt) < bd) { bd = Math.abs(v - tt); best = i; } });
      stop(); go(best);
    };
  }
  function drawCharts() {
    var mh = R.manholes[0], gone = R.volume.outflow.map(function (v) { return v; });
    chart(qSvg, R.manholes.map(function (m, i) { return { v: m.q, color: i ? css("--ink-2") : css("--ink"), fill: i ? null : "split" }; }), { zero: true });
    var crest = R.t.map(function () { return mh.crest; });
    chart(lvSvg, [{ v: mh.H, color: dark() ? "#5BA7DB" : "#2C7DBE", w: 2.2, dash: "6 4" }, { v: mh.eta, color: css("--ink"), w: 2 }, { v: crest, color: css("--bed"), w: 2.5 }],
      { legend: [{ name: "pipe head", color: dark() ? "#5BA7DB" : "#2C7DBE", dash: "6 4" }, { name: "street water", color: css("--ink") }, { name: "rim", color: css("--bed") }] });
    var surf = R.volume.surface, net = R.volume.network, stack = surf.map(function (v, i) { return v + net[i]; });
    chart(volSvg, [{ v: stack, color: dark() ? "#5BA7DB" : "#2C7DBE", fill: true }, { v: net, color: css("--ink-2"), fill: true }, { v: gone, color: css("--bed"), w: 2.2 }, { v: R.volume.inflow, color: css("--ink"), w: 1.5, dash: "5 4" }],
      { lo: 0, legend: [{ name: "street", color: dark() ? "#5BA7DB" : "#2C7DBE" }, { name: "pipes", color: css("--ink-2") }, { name: "out", color: css("--bed") }, { name: "in", color: css("--ink"), dash: "5 4" }] });
    var v0 = R.volume.surface[0] + R.volume.network[0];
    var inn = R.volume.inflow[fi], s = R.volume.surface[fi], n = R.volume.network[fi], o = R.volume.outflow[fi];
    var err = s + n + o - v0 - inn, base = Math.max(v0 + inn, 1e-9);
    bal.innerHTML = "At " + esc(clock(R.t[fi])) + ": started with " + fmt(v0, 1) + " m³, came in " + fmt(inn, 1) + " m³ → on the street " + fmt(s, 1) + ", in the pipes " + fmt(n, 1) + ", gone out " + fmt(o, 1) +
      ". Not accounted for (so far): <b>" + (err >= 0 ? "+" : "") + fmt(err, 2) + " m³</b> (" + fmt(100 * err / base, 2) + " %).";
  }

  // ── what is happening, in words ──────────────────────────────────────────
  function tell() {
    var mh = R.manholes[0], q = mh.q[fi], eta = mh.eta[fi], H = mh.H[fi], crest = mh.crest, surf = R.volume.surface[fi];
    var node = chain && chain.nodes[mh.id], crown = null;
    if (chain) chain.links.forEach(function (l) { if (l.to === mh.id || l.from === mh.id) crown = Math.max(crown === null ? -Infinity : crown, chain.nodes[mh.id].invert + l.D); });
    var s;
    if (q > 1e-5) s = "The pipe is full and pressurised: water is <b class=\"cv-up\">spilling out of " + esc(mh.id) + " onto the street</b> at " + fmt(q, 3) + " m³/s.";
    else if (q < -1e-5) s = "Water on the street is <b class=\"cv-down\">draining back into the pipe through " + esc(mh.id) + "</b> at " + fmt(-q, 3) + " m³/s.";
    else if (surf > 0.05) s = "Water is standing on the street, but " + esc(mh.id) + " is not exchanging" + (H >= eta - 1e-4 && eta > crest ? " (the pipe is as high as the street water)." : ".");
    else if (crown !== null && H > crown + 1e-3) s = "The pipe is surcharged (its water is above the crown) but still below the rim of " + esc(mh.id) + ": nothing reaches the street yet.";
    else if (H > (node ? node.invert + 1e-3 : -Infinity)) s = "Water is flowing in the pipes only; the street is dry.";
    else s = "Nothing is moving yet.";
    story.innerHTML = '<span class="cv-clock">' + esc(clock(R.t[fi])) + "</span> " + s;
  }

  // ── player ───────────────────────────────────────────────────────────────
  function render() { drawMap(); drawProfile(); drawCharts(); tell(); scrub.value = String(fi); tlabel.textContent = clock(R.t[fi]); }
  function go(i) { if (!R) return; fi = Math.max(0, Math.min(R.t.length - 1, i)); render(); }
  var ICON_PLAY = '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg>';
  var ICON_PAUSE = '<svg viewBox="0 0 18 18" aria-hidden="true"><rect x="3" y="2" width="4" height="14"/><rect x="11" y="2" width="4" height="14"/></svg>';
  function stop() { if (timer) { clearInterval(timer); timer = null; } play.innerHTML = ICON_PLAY; play.setAttribute("aria-label", "Play"); }
  function start() {
    if (!R) return;
    if (fi >= R.t.length - 1) fi = 0;
    play.innerHTML = ICON_PAUSE; play.setAttribute("aria-label", "Pause");
    timer = setInterval(function () { if (fi >= R.t.length - 1) { stop(); return; } go(fi + 1); }, Math.max(40, 12000 / R.t.length) / speed);
  }
  play.addEventListener("click", function () { if (timer) stop(); else start(); });
  $("cv-back").addEventListener("click", function () { stop(); go(fi - 1); });
  $("cv-fwd").addEventListener("click", function () { stop(); go(fi + 1); });
  scrub.addEventListener("input", function () { stop(); go(+scrub.value); });
  document.querySelectorAll("[data-cvspeed]").forEach(function (b) {
    b.addEventListener("click", function () {
      speed = +b.getAttribute("data-cvspeed");
      document.querySelectorAll("[data-cvspeed]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      if (timer) { stop(); start(); }
    });
  });
  document.addEventListener("keydown", function (e) {
    if (!R || e.altKey || e.ctrlKey || e.metaKey) return;
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "select" || tag === "textarea" || (tag === "button" && e.key === " ")) return;
    if (e.key === " ") { e.preventDefault(); if (timer) stop(); else start(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); stop(); go(fi + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); stop(); go(fi - 1); }
  });
  (function pulse() {  // keep the exchange rings moving while water is crossing
    if (R && R.manholes.some(function (m) { return Math.abs(m.q[fi]) > 1e-5; }) && !document.hidden) drawMap();
    setTimeout(function () { requestAnimationFrame(pulse); }, 50);
  })();
  function stickTop() { var h = document.querySelector(".site-head"); if (h) $("cv-player").style.top = h.offsetHeight + "px"; }
  stickTop();
  window.addEventListener("resize", function () { stickTop(); if (R) { sizeMap(); render(); } });

  // ── loading ──────────────────────────────────────────────────────────────
  function loadModel(m) {
    stop();
    modelsBox.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-key") === m.key ? "true" : "false"); });
    fetch(m.url).then(function (r) { return r.json(); }).then(function (d) {
      R = d; chain = buildChain();
      var S = R.surface;
      hmax = 1e-3; S.h.forEach(function (fr) { fr.forEach(function (v) { if (v > hmax) hmax = v; }); });
      zlo = Math.min.apply(null, S.z); zhi = Math.max.apply(null, S.z);
      qmax = 1e-6; R.manholes.forEach(function (mh) { mh.q.forEach(function (v) { qmax = Math.max(qmax, Math.abs(v)); }); });
      scrub.max = String(R.t.length - 1);
      // open where something is happening: the first frame with water crossing a manhole
      fi = 0;
      for (var i = 0; i < R.t.length; i++) if (R.manholes.some(function (mh) { return Math.abs(mh.q[i]) > 0.25 * qmax; })) { fi = i; break; }
      sizeMap();
      var stops = []; for (var k = 0; k <= 10; k++) { var c = ramp(DEPTH, Math.pow(k / 10, 0.75)); stops.push("rgb(" + c.map(Math.round).join(",") + ") " + k * 10 + "%"); }
      leg.innerHTML = '<div class="vw-leg-row"><span class="vw-dry" title="dry ground"></span><div class="vw-bar" style="background:linear-gradient(90deg,' + stops.join(",") + ')"></div></div>' +
        '<div class="vw-ticks"><span>dry</span><span>' + depthStr(hmax / 2) + "</span><span>" + depthStr(hmax) + " deep</span></div>" +
        '<p class="cv-leg-note">Ground shaded light (high) to dark (low).' + (exag > 1.01 ? " The street is stretched ×" + fmt(exag, 0) + " across so it can be seen." : "") +
        ' <span class="cv-up">●</span> water leaving the pipe · <span class="cv-down">●</span> water entering it.</p>';
      render();
    });
  }
  function load(sid) {
    var t = IDX.tests.filter(function (x) { return x.sid === sid; })[0];
    if (!t) return;
    T = t;
    link.href = "tests/" + encodeURIComponent(sid) + ".html";
    try { history.replaceState(null, "", "#" + sid); } catch (e) { /* file:// */ }
    modelsBox.innerHTML = t.models.map(function (m) {
      return '<button type="button" class="vw-chip" data-key="' + esc(m.key) + '" aria-pressed="false"><span class="sw" style="background:' + esc(m.color) + '"></span>' + esc(m.label) +
        scoreChip(m.score) + "</button>";
    }).join("");
    modelsBox.querySelectorAll("button").forEach(function (b) { b.addEventListener("click", function () { loadModel(t.models.filter(function (m) { return m.key === b.getAttribute("data-key"); })[0]); }); });
    if (t.models.length) loadModel(t.models[0]);
  }
  sel.addEventListener("change", function () { load(sel.value); });
  window.addEventListener("hashchange", function () { var w = decodeURIComponent(location.hash.slice(1)); if (w && w !== sel.value) { sel.value = w; load(w); } });
  var want = decodeURIComponent((location.hash || "").slice(1)) || IDX.first;
  if (IDX.tests.some(function (t) { return t.sid === want; })) sel.value = want;
  if (sel.value) load(sel.value);
})();
