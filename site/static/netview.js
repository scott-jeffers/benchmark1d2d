// Network viewer: a SWMM or EPANET .inp file parsed in the browser and drawn as a map, with every
// engine's results over time. Data: data/network/<test>.json (site/netresults.py) and the .inp it names.
(function () {
  "use strict";
  var IDX = JSON.parse(document.getElementById("nv-index").textContent);
  function $(id) { return document.getElementById(id); }
  var testSel = $("nv-test"), engines = $("nv-engines"), modeBox = $("nv-mode"), flowBox = $("nv-flow"), dl = $("nv-dl"), summary = $("nv-summary");
  var canvas = $("nv-canvas"), tip = $("nv-tip"), legend = $("nv-legend"), side = $("nv-side");
  var timeBox = $("nv-time"), scrub = $("nv-scrub"), tlabel = $("nv-tlabel"), play = $("nv-play");
  var tabMap = $("nv-tab-map"), tabFile = $("nv-tab-file"), paneMap = $("nv-map-pane"), paneFile = $("nv-file-pane");
  var secNav = $("nv-sections"), src = $("nv-src"), find = $("nv-find"), findN = $("nv-find-n"), foot = $("nv-foot");
  var NS = "http://www.w3.org/2000/svg";

  var D = null, P = null, N = null;            // data file, parsed .inp, network
  var cur = null, ref = null, mode = "value";  // shown result, reference result
  var ti = 0, timer = null, selected = null, hover = null, view = null, scales = null, fileSec = null, speed = 1;
  var phase = 0, raf = null, lastFrame = 0, sparse = false;
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  flowBox.checked = !reduced;

  // ── helpers ────────────────────────────────────────────────────────────────
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fmt(v) {
    if (v === null || v === undefined || !isFinite(v)) return "–";
    var a = Math.abs(v);
    return a === 0 ? "0" : a >= 1000 ? v.toFixed(0) : a >= 100 ? v.toFixed(1) : a >= 1 ? v.toFixed(3) : v.toPrecision(3);
  }
  function kb(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB"; }
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888"; }
  function rgb(c) { return "rgb(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + ")"; }
  function seqColor(t) {  // light to deep blue
    t = Math.max(0, Math.min(1, t));
    var a = [205, 228, 246], b = [8, 48, 120], k = Math.pow(t, 0.85);
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  }
  function divColor(t) {  // blue below the reference, orange above
    t = Math.max(-1, Math.min(1, t));
    var mid = [236, 236, 236], neg = [33, 102, 172], pos = [214, 96, 39], e = t < 0 ? neg : pos, k = Math.pow(Math.abs(t), 0.8);
    return [mid[0] + (e[0] - mid[0]) * k, mid[1] + (e[1] - mid[1]) * k, mid[2] + (e[2] - mid[2]) * k];
  }
  function clock(t) {
    if (!D) return "";
    if (D.t0) {  // a real storm: the calendar time
      var dt = new Date(Date.parse(D.t0 + "Z") + t * 1000), mo = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      var p2 = function (n) { return (n < 10 ? "0" : "") + n; };
      return dt.getUTCDate() + " " + mo[dt.getUTCMonth()] + " " + dt.getUTCFullYear() + ", " + p2(dt.getUTCHours()) + ":" + p2(dt.getUTCMinutes());
    }
    if (t < 120) return "t = " + fmt(t) + " s";
    var d = Math.floor(t / 86400), r = t - d * 86400, hh = Math.floor(r / 3600), mm = Math.round((r - hh * 3600) / 60);
    if (mm === 60) { hh++; mm = 0; }
    return "t = " + (d ? d + " d " : "") + (hh || d ? hh + " h " : "") + (mm < 10 && (hh || d) ? "0" : "") + mm + " min";
  }

  // ── .inp parsing ───────────────────────────────────────────────────────────
  function tokenize(s) {
    var out = [], re = /"([^"]*)"|(\S+)/g, m;
    while ((m = re.exec(s))) out.push(m[1] !== undefined ? m[1] : m[2]);
    return out;
  }
  function parseInp(text) {
    var lines = text.split(/\r?\n/), secs = {}, order = [], header = {}, sec = null;
    for (var i = 0; i < lines.length; i++) {
      var s = lines[i].trim();
      if (!s) continue;
      if (s.charAt(0) === "[") {
        sec = s.replace(/[\[\]]/g, "").trim().toUpperCase();
        if (!secs[sec]) { secs[sec] = []; order.push({ name: sec, line: i }); }
        continue;
      }
      if (s.slice(0, 2) === ";;") {
        if (sec && !header[sec] && !secs[sec].length && /[A-Za-z]/.test(s)) header[sec] = s.slice(2).trim().split(/\s+/);
        continue;
      }
      if (s.charAt(0) === ";" || !sec) continue;
      var body = s.split(";")[0].trim();
      if (body) secs[sec].push({ tok: tokenize(body), line: i });
    }
    order.forEach(function (o, k) { o.end = k + 1 < order.length ? order[k + 1].line : lines.length; o.rows = secs[o.name].length; });
    return { lines: lines, secs: secs, order: order, header: header };
  }

  var FIELDS = {
    swmm: {
      JUNCTIONS: "Name Elevation MaxDepth InitDepth SurDepth Aponded", OUTFALLS: "Name Elevation Type StageData Gated RouteTo",
      STORAGE: "Name Elevation MaxDepth InitDepth Shape Curve/Coefficients", DIVIDERS: "Name Elevation DivertedLink Type Parameters",
      CONDUITS: "Name FromNode ToNode Length Roughness InOffset OutOffset InitFlow MaxFlow", PUMPS: "Name FromNode ToNode PumpCurve Status Startup Shutoff",
      ORIFICES: "Name FromNode ToNode Type Offset Qcoeff Gated CloseTime", WEIRS: "Name FromNode ToNode Type CrestHt Qcoeff Gated EndCon EndCoeff",
      OUTLETS: "Name FromNode ToNode Offset Type QTable/Qcoeff Qexpon Gated", XSECTIONS: "Link Shape Geom1 Geom2 Geom3 Geom4 Barrels Culvert",
      SUBCATCHMENTS: "Name RainGage Outlet Area %Imperv Width %Slope CurbLen SnowPack"
    },
    epanet: {
      JUNCTIONS: "ID Elevation Demand Pattern", RESERVOIRS: "ID Head Pattern", TANKS: "ID Elevation InitLevel MinLevel MaxLevel Diameter MinVol VolCurve",
      PIPES: "ID Node1 Node2 Length Diameter Roughness MinorLoss Status", PUMPS: "ID Node1 Node2 Parameters", VALVES: "ID Node1 Node2 Diameter Type Setting MinorLoss"
    }
  };
  var TYPE = {
    swmm: { JUNCTIONS: "Junction (manhole)", OUTFALLS: "Outfall", STORAGE: "Storage unit", DIVIDERS: "Divider",
            CONDUITS: "Conduit", PUMPS: "Pump", ORIFICES: "Orifice", WEIRS: "Weir", OUTLETS: "Outlet" },
    epanet: { JUNCTIONS: "Junction", RESERVOIRS: "Reservoir", TANKS: "Tank", PIPES: "Pipe", PUMPS: "Pump", VALVES: "Valve" }
  };
  function fieldsFor(sec) {
    var h = P.header[sec], d = (FIELDS[D.kind][sec] || "").split(" ");
    if (h && h.length >= 3 && !/^-+$/.test(h[0])) return h;
    return d;
  }

  function buildNet(kind) {
    var nodeSecs = kind === "swmm" ? ["JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS"] : ["JUNCTIONS", "RESERVOIRS", "TANKS"];
    var linkSecs = kind === "swmm" ? ["CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS"] : ["PIPES", "PUMPS", "VALVES"];
    var net = { nodes: {}, links: {}, nodeList: [], linkList: [], polys: [], subs: [], counts: [], options: {} };
    nodeSecs.forEach(function (s) {
      (P.secs[s] || []).forEach(function (r) {
        var n = { id: r.tok[0], sec: s, row: r, x: null, y: null };
        net.nodes[n.id] = n; net.nodeList.push(n);
      });
      if ((P.secs[s] || []).length) net.counts.push([P.secs[s].length, TYPE[kind][s]]);
    });
    linkSecs.forEach(function (s) {
      (P.secs[s] || []).forEach(function (r) {
        if (r.tok.length < 3) return;
        var l = { id: r.tok[0], sec: s, row: r, from: r.tok[1], to: r.tok[2], v: [], len: kind === "swmm" ? (s === "CONDUITS" ? +r.tok[3] : NaN) : (s === "PIPES" ? +r.tok[3] : NaN) };
        net.links[l.id] = l; net.linkList.push(l);
      });
      if ((P.secs[s] || []).length) net.counts.push([P.secs[s].length, TYPE[kind][s]]);
    });
    (P.secs.XSECTIONS || []).forEach(function (r) { var l = net.links[r.tok[0]]; if (l) l.xs = r; });
    (P.secs.COORDINATES || []).forEach(function (r) { var n = net.nodes[r.tok[0]]; if (n) { n.x = +r.tok[1]; n.y = +r.tok[2]; } });
    (P.secs.VERTICES || []).forEach(function (r) { var l = net.links[r.tok[0]]; if (l) l.v.push([+r.tok[1], +r.tok[2]]); });
    var polys = {};
    (P.secs.POLYGONS || []).forEach(function (r) { (polys[r.tok[0]] = polys[r.tok[0]] || []).push([+r.tok[1], +r.tok[2]]); });
    (P.secs.SUBCATCHMENTS || []).forEach(function (r) {
      var pts = polys[r.tok[0]];
      if (pts && pts.length > 2) net.polys.push({ id: r.tok[0], pts: pts, outlet: r.tok[2], row: r });
    });
    if ((P.secs.SUBCATCHMENTS || []).length) net.counts.push([P.secs.SUBCATCHMENTS.length, "Subcatchments"]);
    (P.secs.OPTIONS || []).forEach(function (r) { net.options[String(r.tok[0]).toUpperCase()] = r.tok.slice(1).join(" "); });
    var placed = net.nodeList.filter(function (n) { return isFinite(n.x) && n.x !== null; }).length;
    net.laidOut = placed < net.nodeList.length;
    if (net.laidOut) autoLayout(net);
    return net;
  }

  // A schematic for a file without map coordinates: nodes along their distance from the network's upstream ends,
  // independent lines stacked.
  function autoLayout(net) {
    var out = {}, inc = {}, adj = {};
    net.nodeList.forEach(function (n) { out[n.id] = []; inc[n.id] = 0; adj[n.id] = []; });
    var lens = net.linkList.map(function (l) { return l.len; }).filter(function (v) { return isFinite(v) && v > 0; }).sort(function (a, b) { return a - b; });
    var unit = lens.length ? lens[Math.floor(lens.length / 2)] : 1;
    net.linkList.forEach(function (l) {
      if (!(l.from in out) || !(l.to in out)) return;
      var len = isFinite(l.len) && l.len > 0 ? l.len : unit;
      out[l.from].push([l.to, len]); inc[l.to]++; adj[l.from].push(l.to); adj[l.to].push(l.from);
    });
    var comp = {}, comps = [];
    net.nodeList.forEach(function (n) {
      if (n.id in comp) return;
      var stack = [n.id], c = []; comp[n.id] = comps.length;
      while (stack.length) { var u = stack.pop(); c.push(u); adj[u].forEach(function (w) { if (!(w in comp)) { comp[w] = comps.length; stack.push(w); } }); }
      comps.push(c);
    });
    var y0 = 0;
    comps.forEach(function (c) {
      var dist = {};
      c.forEach(function (u) { dist[u] = inc[u] ? -Infinity : 0; });
      if (!c.some(function (u) { return dist[u] === 0; })) dist[c[0]] = 0;
      for (var pass = 0; pass < c.length; pass++) {
        var changed = false;
        c.forEach(function (u) {
          if (!isFinite(dist[u])) return;
          out[u].forEach(function (e) { if (dist[u] + e[1] > dist[e[0]] + 1e-9) { dist[e[0]] = dist[u] + e[1]; changed = true; } });
        });
        if (!changed) break;
      }
      c.forEach(function (u) { if (!isFinite(dist[u])) dist[u] = 0; });
      var groups = {};
      c.forEach(function (u) { var k = Math.round(dist[u] / (unit * 0.25)); (groups[k] = groups[k] || []).push(u); });
      var width = 0;
      Object.keys(groups).forEach(function (k) {
        var g = groups[k];
        g.forEach(function (u, i) { var n = net.nodes[u]; n.x = dist[u]; n.y = y0 - (i - (g.length - 1) / 2) * unit * 0.6; });
        width = Math.max(width, g.length);
      });
      y0 -= Math.max(1, width) * unit * 0.6 + unit * 0.8;
    });
  }

  function linkPath(l) {
    var a = N.nodes[l.from], b = N.nodes[l.to];
    if (!a || !b) return null;
    return [[a.x, a.y]].concat(l.v).concat([[b.x, b.y]]);
  }

  // ── results ────────────────────────────────────────────────────────────────
  function nearestIndex(ts, t) {
    var best = 0, bd = Infinity;
    for (var i = 0; i < ts.length; i++) { var d = Math.abs(ts[i] - t); if (d < bd) { bd = d; best = i; } }
    return best;
  }
  // the reference's value at the shown result's time (an exact answer that holds only at the end is compared there only)
  function refAt(kind, id, t) {
    if (!ref || ref === cur) return null;
    var s = ref[kind][id]; if (!s) return null;
    var j = nearestIndex(ref.t, t);
    var step = cur.t.length > 1 ? (cur.t[cur.t.length - 1] - cur.t[0]) / (cur.t.length - 1) : Infinity;
    if (Math.abs(ref.t[j] - t) > Math.max(0.51 * step, 1e-6) && ref.t.length > 1) return null;
    if (ref.t.length === 1 && cur.t.length > 1 && Math.abs(ref.t[0] - t) > 0.51 * step) return null;
    return s[j];
  }
  function valueAt(kind, id) {
    if (!cur) return null;
    var s = cur[kind][id];
    if (!s) return null;
    var v = s[ti];
    if (mode === "diff") { var r = refAt(kind, id, cur.t[ti]); return v === null || r === null || r === undefined ? null : v - r; }
    return v;
  }
  function computeScales() {
    scales = null;
    if (!cur) return;
    function collect(kind, abs) {
      var vals = [];
      Object.keys(cur[kind]).forEach(function (id) {
        cur[kind][id].forEach(function (v, i) {
          if (v === null) return;
          if (mode === "diff") { var r = refAt(kind, id, cur.t[i]); if (r === null || r === undefined) return; v = v - r; }
          vals.push(abs || mode === "diff" ? Math.abs(v) : v);
        });
      });
      vals.sort(function (a, b) { return a - b; });
      return vals;
    }
    var nv = collect("nodes", false), lv = collect("links", true);
    function pct(v, p) { return v.length ? v[Math.min(v.length - 1, Math.floor(p * (v.length - 1)))] : null; }
    if (mode === "diff") {
      scales = { node: { lim: Math.max(pct(nv, 0.98) || 0, 1e-9) }, link: { lim: Math.max(pct(lv, 0.98) || 0, 1e-12) } };
    } else {
      scales = { node: { lo: nv.length ? pct(nv, 0.02) : 0, hi: nv.length ? pct(nv, 0.98) : 1 }, link: { hi: Math.max(pct(lv, 0.98) || 0, 1e-12) } };
      if (scales.node.hi - scales.node.lo < 1e-9) scales.node.hi = scales.node.lo + 1;
    }
  }
  function nodeColor(id) {
    var v = valueAt("nodes", id);
    if (v === null || v === undefined || !scales) return null;
    if (mode === "diff") return rgb(divColor(v / scales.node.lim));
    return rgb(seqColor((v - scales.node.lo) / (scales.node.hi - scales.node.lo)));
  }
  function linkStyle(id) {
    var v = valueAt("links", id);
    if (v === null || v === undefined || !scales) return null;
    if (mode === "diff") {
      var t = v / scales.link.lim, c = divColor(t), g = 1 - Math.min(1, Math.abs(t));  // near zero: mid grey, so the pipe still shows
      var raw = cur.links[id][ti];
      return { color: rgb([c[0] - 70 * g, c[1] - 70 * g, c[2] - 70 * g]), w: 2 + 4 * Math.min(1, Math.abs(t)), k: 0.5, q: raw ? raw : 0 };
    }
    var k = Math.min(1, Math.abs(v) / scales.link.hi);
    return { color: rgb(seqColor(0.3 + 0.7 * k)), w: 2 + 5 * k, k: k, q: Math.abs(v) > 1e-3 * scales.link.hi ? v : 0 };
  }

  // ── map drawing ────────────────────────────────────────────────────────────
  function bounds() {
    var x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    function add(x, y) { if (!isFinite(x) || !isFinite(y)) return; x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
    N.nodeList.forEach(function (n) { add(n.x, n.y); });
    N.linkList.forEach(function (l) { l.v.forEach(function (p) { add(p[0], p[1]); }); });
    if (!isFinite(x0)) N.polys.forEach(function (p) { p.pts.forEach(function (q) { add(q[0], q[1]); }); });
    if (!isFinite(x0)) { x0 = 0; x1 = 1; y0 = 0; y1 = 1; }
    return { x0: x0, x1: x1, y0: y0, y1: y1 };
  }
  function size() {
    var dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    return { w: w, h: h, dpr: dpr };
  }
  function fit() {
    var b0 = bounds(), w0 = canvas.clientWidth || 600;
    var aspect = (b0.y1 - b0.y0) / Math.max(b0.x1 - b0.x0, 1e-9);
    var want = Math.max(300, Math.min(window.innerHeight * 0.72, 780, (w0 - 86) * aspect + 170));
    canvas.style.height = Math.round(want) + "px";
    var b = b0, sz = size(), pad = 28, padR = 58, padB = (getComputedStyle(legend).position === "absolute" && !legend.hidden ? legend.offsetHeight + 14 : 0) + 18;  // room for the zoom buttons and the legend
    var dx = Math.max(b.x1 - b.x0, 1e-9), dy = Math.max(b.y1 - b.y0, 1e-9);
    var s = Math.min((sz.w - pad - padR) / dx, (sz.h - pad - padB) / dy);
    if (b.y1 - b.y0 < 1e-9) s = (sz.w - pad - padR) / dx;
    if (b.x1 - b.x0 < 1e-9) s = (sz.h - pad - padB) / dy;
    view = { cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2, s: s, s0: s };
    // centre the network in the space the overlays leave free
    var w0s = toWorld(pad + (sz.w - pad - padR) / 2, pad + (sz.h - pad - padB) / 2), mid = toWorld(sz.w / 2, sz.h / 2);
    view.cx -= w0s[0] - mid[0]; view.cy -= w0s[1] - mid[1];
  }
  function toScreen(x, y) { var sz = size(); return [(x - view.cx) * view.s + sz.w / 2, sz.h / 2 - (y - view.cy) * view.s]; }
  function toWorld(px, py) { var sz = size(); return [(px - sz.w / 2) / view.s + view.cx, view.cy - (py - sz.h / 2) / view.s]; }

  function draw() {
    if (!N || !view) return;
    var sz = size(), ctx = canvas.getContext("2d");
    ctx.setTransform(sz.dpr, 0, 0, sz.dpr, 0, 0);
    ctx.clearRect(0, 0, sz.w, sz.h);
    var C = { ink: css("--ink"), ink2: css("--ink-2"), rule: css("--rule"), sheet: css("--sheet"), water: css("--water"), soft: css("--water-soft"),
              bed: css("--bed"), grey: css("--draft"), sel: css("--fail"), paper: css("--paper"), wash: css("--rule-2") };
    // subcatchments
    if (N.polys.length) {
      ctx.lineWidth = 0.7;
      N.polys.forEach(function (p) {
        ctx.beginPath();
        p.pts.forEach(function (q, i) { var s = toScreen(q[0], q[1]); if (i) ctx.lineTo(s[0], s[1]); else ctx.moveTo(s[0], s[1]); });
        ctx.closePath();
        ctx.globalAlpha = 0.55; ctx.fillStyle = C.wash; ctx.fill();
        ctx.globalAlpha = 0.8; ctx.strokeStyle = C.rule; ctx.stroke();
      });
      ctx.globalAlpha = 1;
    }
    var hasRes = !!cur;
    // links
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    N.linkList.forEach(function (l) {
      var pts = linkPath(l); if (!pts) return;
      var st = hasRes ? linkStyle(l.id) : null;
      ctx.beginPath();
      pts.forEach(function (q, i) { var s = toScreen(q[0], q[1]); if (i) ctx.lineTo(s[0], s[1]); else ctx.moveTo(s[0], s[1]); });
      ctx.strokeStyle = st ? st.color : (hasRes && Object.keys(cur.links).length ? C.grey : sparse ? C.rule : C.ink2);
      ctx.lineWidth = st ? st.w : sparse ? 1.4 : 2;
      if (l.sec !== "CONDUITS" && l.sec !== "PIPES") ctx.setLineDash([5, 4]); else ctx.setLineDash([]);
      ctx.stroke();
      ctx.setLineDash([]);
      if (st && st.q && flowOn()) {  // marching dashes along the flow, faster for more flow
        ctx.beginPath();
        pts.forEach(function (q, i) { var s = toScreen(q[0], q[1]); if (i) ctx.lineTo(s[0], s[1]); else ctx.moveTo(s[0], s[1]); });
        ctx.setLineDash([3, 11]);
        ctx.lineDashOffset = -(phase * (0.25 + 1.75 * st.k) % 14) * (st.q > 0 ? 1 : -1);
        ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = Math.max(1.6, st.w * 0.5);
        ctx.stroke(); ctx.setLineDash([]); ctx.lineDashOffset = 0;
      }
      if (l.sec !== "CONDUITS" && l.sec !== "PIPES") {  // a mark for pumps, weirs, orifices, outlets and valves
        var mid = pts[Math.floor(pts.length / 2)], prev = pts[Math.max(0, Math.floor(pts.length / 2) - 1)];
        var m = pts.length === 2 ? toScreen((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2) : toScreen(mid[0], mid[1]);
        void prev;
        ctx.beginPath();
        ctx.moveTo(m[0], m[1] - 6); ctx.lineTo(m[0] + 6, m[1]); ctx.lineTo(m[0], m[1] + 6); ctx.lineTo(m[0] - 6, m[1]); ctx.closePath();
        ctx.fillStyle = l.sec === "PUMPS" ? C.ink : C.sheet; ctx.fill();
        ctx.lineWidth = 1.5; ctx.strokeStyle = C.ink; ctx.stroke();
      }
      if (selected && selected.kind === "links" && selected.id === l.id) {
        ctx.beginPath();
        pts.forEach(function (q, i) { var s = toScreen(q[0], q[1]); if (i) ctx.lineTo(s[0], s[1]); else ctx.moveTo(s[0], s[1]); });
        ctx.strokeStyle = C.sel; ctx.lineWidth = (st ? st.w : 2) + 5; ctx.globalAlpha = 0.45; ctx.stroke(); ctx.globalAlpha = 1;
      }
    });
    // nodes
    var r0 = N.nodeList.length > 400 ? 3 : N.nodeList.length > 100 ? 4 : 5.5;
    if (view.s / view.s0 > 3) r0 += 1.5;
    var labelled = [];
    // a few reported elements among many (the level meters of a real network): the rest recede, the reported ones stand out
    var order = sparse && cur ? N.nodeList.filter(function (n) { return !cur.nodes[n.id]; }).concat(N.nodeList.filter(function (n) { return cur.nodes[n.id]; })) : N.nodeList;
    order.forEach(function (n) {
      var s = toScreen(n.x, n.y), col = hasRes ? nodeColor(n.id) : null;
      var resFill = hasRes && Object.keys(cur.nodes).length;
      var r = r0;
      if (sparse && hasRes) {
        if (!cur.nodes[n.id]) { ctx.globalAlpha = 0.45; r = Math.max(2, r0 - 1); }
        else {
          r = 8; labelled.push(n);
          ctx.beginPath(); ctx.arc(s[0], s[1], r + 5, 0, Math.PI * 2); ctx.fillStyle = C.sheet; ctx.globalAlpha = 0.85; ctx.fill(); ctx.globalAlpha = 1;
        }
      }
      ctx.beginPath();
      var big = n.sec === "STORAGE" || n.sec === "TANKS" || n.sec === "RESERVOIRS";
      if (n.sec === "OUTFALLS") { var k = r * 1.5; ctx.moveTo(s[0], s[1] - k); ctx.lineTo(s[0] + k, s[1] + k * 0.8); ctx.lineTo(s[0] - k, s[1] + k * 0.8); ctx.closePath(); }
      else if (big) { var q = r * 1.35; ctx.rect(s[0] - q, s[1] - q, 2 * q, 2 * q); }
      else ctx.arc(s[0], s[1], r, 0, Math.PI * 2);
      ctx.fillStyle = col || (resFill ? C.paper : (n.sec === "OUTFALLS" || n.sec === "RESERVOIRS" ? C.bed : big ? C.soft : C.sheet));
      ctx.fill();
      ctx.lineWidth = col ? (sparse ? 2 : 1) : 1.5; ctx.strokeStyle = col ? C.ink : (resFill ? C.grey : C.ink2); ctx.stroke();
      ctx.globalAlpha = 1;
      if (selected && selected.kind === "nodes" && selected.id === n.id) {
        ctx.beginPath(); ctx.arc(s[0], s[1], r + 6, 0, Math.PI * 2); ctx.lineWidth = 3; ctx.strokeStyle = C.sel; ctx.stroke();
      }
    });
    if (labelled.length) {  // name the reported elements
      ctx.font = "600 12px " + css("--sans"); ctx.textBaseline = "middle"; ctx.lineJoin = "round";
      var boxes = [];  // place each label where it does not cover another (right, left, above, below), else leave it out
      labelled.forEach(function (n) {
        var s = toScreen(n.x, n.y), v = valueAt("nodes", n.id), txt = n.id + (v === null || v === undefined ? "" : "  " + fmt(v));
        var w = ctx.measureText(txt).width, hgt = 15;
        var spots = [[s[0] + 13, s[1]], [s[0] - 13 - w, s[1]], [s[0] - w / 2, s[1] - 18], [s[0] - w / 2, s[1] + 18]];
        for (var k = 0; k < spots.length; k++) {
          var bx = { x: spots[k][0] - 2, y: spots[k][1] - hgt / 2, w: w + 4, h: hgt };
          if (boxes.some(function (o) { return bx.x < o.x + o.w && o.x < bx.x + bx.w && bx.y < o.y + o.h && o.y < bx.y + bx.h; })) continue;
          boxes.push(bx);
          ctx.lineWidth = 4; ctx.strokeStyle = C.sheet; ctx.strokeText(txt, spots[k][0], spots[k][1]);
          ctx.fillStyle = C.ink; ctx.fillText(txt, spots[k][0], spots[k][1]);
          break;
        }
      });
    }
    // labels when few nodes are in view
    var inView = N.nodeList.filter(function (n) { var s = toScreen(n.x, n.y); return s[0] > -20 && s[0] < sz.w + 20 && s[1] > -20 && s[1] < sz.h + 20; });
    if (inView.length <= 45 && !labelled.length) {
      ctx.font = "12px " + css("--mono"); ctx.fillStyle = C.ink2; ctx.textBaseline = "bottom";
      inView.forEach(function (n) { var s = toScreen(n.x, n.y); ctx.fillText(n.id, s[0] + r0 + 3, s[1] - r0 - 1); });
    }
  }

  // ── hit testing, pan and zoom ──────────────────────────────────────────────
  function hit(px, py) {
    var best = null, bd = 10 * 10;
    N.nodeList.forEach(function (n) { var s = toScreen(n.x, n.y), d = (s[0] - px) * (s[0] - px) + (s[1] - py) * (s[1] - py); if (d < bd) { bd = d; best = { kind: "nodes", id: n.id }; } });
    if (best) return best;
    bd = 7 * 7;
    N.linkList.forEach(function (l) {
      var pts = linkPath(l); if (!pts) return;
      for (var i = 1; i < pts.length; i++) {
        var a = toScreen(pts[i - 1][0], pts[i - 1][1]), b = toScreen(pts[i][0], pts[i][1]);
        var vx = b[0] - a[0], vy = b[1] - a[1], L = vx * vx + vy * vy, t = L ? ((px - a[0]) * vx + (py - a[1]) * vy) / L : 0;
        t = Math.max(0, Math.min(1, t));
        var dx = a[0] + t * vx - px, dy = a[1] + t * vy - py, d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = { kind: "links", id: l.id }; }
      }
    });
    return best;
  }
  function zoomAt(px, py, f) {
    var w = toWorld(px, py);
    view.s = Math.max(view.s0 * 0.3, Math.min(view.s0 * 400, view.s * f));
    var w2 = toWorld(px, py);
    view.cx += w[0] - w2[0]; view.cy += w[1] - w2[1];
    draw();
  }
  var pointers = {}, drag = null, moved = false, pinch = null;
  canvas.addEventListener("pointerdown", function (e) {
    canvas.setPointerCapture(e.pointerId);
    pointers[e.pointerId] = [e.offsetX, e.offsetY];
    var ids = Object.keys(pointers);
    if (ids.length === 1) { drag = { x: e.offsetX, y: e.offsetY, cx: view.cx, cy: view.cy }; moved = false; }
    if (ids.length === 2) {
      var a = pointers[ids[0]], b = pointers[ids[1]];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), s: view.s }; drag = null;
    }
  });
  canvas.addEventListener("pointermove", function (e) {
    if (!N || !view) return;
    if (pointers[e.pointerId]) pointers[e.pointerId] = [e.offsetX, e.offsetY];
    var ids = Object.keys(pointers);
    if (pinch && ids.length === 2) {
      var a = pointers[ids[0]], b = pointers[ids[1]], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      var mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, w = toWorld(mx, my);
      view.s = Math.max(view.s0 * 0.3, Math.min(view.s0 * 400, pinch.s * d / Math.max(pinch.d, 1)));
      var w2 = toWorld(mx, my); view.cx += w[0] - w2[0]; view.cy += w[1] - w2[1];
      moved = true; draw(); return;
    }
    if (drag) {
      var dx = e.offsetX - drag.x, dy = e.offsetY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      if (moved) { view.cx = drag.cx - dx / view.s; view.cy = drag.cy + dy / view.s; draw(); }
      return;
    }
    var h = hit(e.offsetX, e.offsetY);
    canvas.style.cursor = h ? "pointer" : "grab";
    if (h) {
      var v = cur ? (cur[h.kind][h.id] || [])[ti] : null;
      var vv = D.vars[h.kind === "nodes" ? "node" : "link"];
      var el = h.kind === "nodes" ? N.nodes[h.id] : N.links[h.id];
      tip.innerHTML = "<b>" + esc(h.id) + "</b> · " + esc(TYPE[D.kind][el.sec] || el.sec) +
        (cur && vv && v !== undefined && v !== null ? "<br>" + esc(vv.label) + " " + fmt(v) + " " + esc(vv.unit) : "");
      tip.hidden = false;
      var bw = canvas.clientWidth;
      tip.style.left = Math.min(e.offsetX + 14, bw - 220) + "px"; tip.style.top = (e.offsetY + 14) + "px";
    } else tip.hidden = true;
  });
  function endPointer(e) {
    var wasDrag = drag && !moved && Object.keys(pointers).length === 1;
    delete pointers[e.pointerId];
    if (Object.keys(pointers).length < 2) pinch = null;
    if (wasDrag && e.type === "pointerup") { var h = hit(e.offsetX, e.offsetY); select(h, e.pointerType === "mouse" ? "click" : "tap"); }
    if (!Object.keys(pointers).length) drag = null;
  }
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);
  canvas.addEventListener("pointerleave", function () { tip.hidden = true; });
  canvas.addEventListener("wheel", function (e) { if (!view) return; e.preventDefault(); zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  $("nv-zin").addEventListener("click", function () { var sz = size(); zoomAt(sz.w / 2, sz.h / 2, 1.5); });
  $("nv-zout").addEventListener("click", function () { var sz = size(); zoomAt(sz.w / 2, sz.h / 2, 1 / 1.5); });
  $("nv-fit").addEventListener("click", function () { fit(); draw(); });
  var lastW = 0;
  window.addEventListener("resize", function () {  // refit only when the width changes (a phone's address bar changes the height)
    if (!N) return;
    if (Math.abs(canvas.clientWidth - lastW) > 2) { lastW = canvas.clientWidth; fit(); }
    draw();
  });
  if (window.matchMedia) matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { draw(); });

  // ── legend and side panel ──────────────────────────────────────────────────
  function bar(colorFn, n) {
    var stops = [];
    for (var i = 0; i <= n; i++) stops.push(rgb(colorFn(i / n)) + " " + (100 * i / n).toFixed(0) + "%");
    return '<div class="vw-bar" style="background:linear-gradient(90deg,' + stops.join(",") + ')"></div>';
  }
  function symbolsHtml() {
    return '<span class="nv-sym"><span><i class="s-j"></i>junction</span>' +
      (D.kind === "swmm" ? '<span><i class="s-o"></i>outfall</span><span><i class="s-s"></i>storage</span>' : '<span><i class="s-s"></i>tank or reservoir</span>') +
      '<span><i class="s-p"></i>pump</span><span><i class="s-w"></i>' + (D.kind === "swmm" ? "weir, orifice or outlet" : "valve") + "</span></span>";
  }
  function renderLegend() {
    var parts = [];
    if (cur && scales) {
      var nv = D.vars.node, lv = D.vars.link;
      var refName = ref ? (ref.role === "exact" ? "exact" : ref.role === "measured" ? "measured" : ref.label.replace(/ \(reference\)$/, "")) : "";
      var hasN = Object.keys(cur.nodes).length, hasL = lv && Object.keys(cur.links).length;
      if (mode === "diff") {
        if (hasN) parts.push('<div class="nv-leg"><span class="nv-leg-t">' + esc(nv.label) + " − " + esc(refName) + " (" + esc(nv.unit) + ")</span>" +
          bar(function (t) { return divColor(2 * t - 1); }, 12) + '<div class="vw-ticks"><span>−' + fmt(scales.node.lim) + "</span><span>0</span><span>+" + fmt(scales.node.lim) + "</span></div></div>");
        if (hasL) parts.push('<div class="nv-leg"><span class="nv-leg-t">' + esc(lv.label) + " − " + esc(refName) + " (" + esc(lv.unit) + ")</span>" +
          bar(function (t) { return divColor(2 * t - 1); }, 12) + '<div class="vw-ticks"><span>−' + fmt(scales.link.lim) + "</span><span>0</span><span>+" + fmt(scales.link.lim) + "</span></div></div>");
      } else {
        if (hasN) parts.push('<div class="nv-leg"><span class="nv-leg-t">' + esc(nv.label) + " (" + esc(nv.unit) + ")" + (sparse ? " · at the " + hasN + " reported points" : "") + "</span>" + bar(seqColor, 12) +
          '<div class="vw-ticks"><span>' + fmt(scales.node.lo) + "</span><span>" + fmt(scales.node.hi) + "</span></div></div>");
        if (hasL) parts.push('<div class="nv-leg"><span class="nv-leg-t">' + esc(lv.label) + " (" + esc(lv.unit) + ")" + (flowOn() ? " · dashes run downstream" : "") + "</span>" +
          bar(function (t) { return seqColor(0.3 + 0.7 * t); }, 12) + '<div class="vw-ticks"><span>0</span><span>' + fmt(scales.link.hi) + "</span></div></div>");
      }
    }
    legend.innerHTML = parts.join("");
    legend.hidden = !parts.length;
  }

  function propsTable(sec, row) {
    var f = fieldsFor(sec);
    return row.tok.map(function (v, i) { return "<tr><th>" + esc(f[i] || "field " + (i + 1)) + "</th><td class=\"mono\">" + esc(v) + "</td></tr>"; }).join("");
  }
  function miniChart(kind, id) {
    var series = D.results.filter(function (r) { return r[kind][id]; });
    if (!series.length) return '<p class="small muted">No engine reports this element.</p>';
    var W = 340, H = 170, L = 46, R = 8, T = 10, B = 26, x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    series.forEach(function (r) { r.t.forEach(function (t, i) { var v = r[kind][id][i]; if (v === null) return; x0 = Math.min(x0, t); x1 = Math.max(x1, t); y0 = Math.min(y0, v); y1 = Math.max(y1, v); }); });
    if (!isFinite(x0)) return "";
    if (x1 - x0 < 1e-9) { x0 -= 1; x1 += 1; }
    if (y1 - y0 < 1e-12) { y0 -= Math.abs(y0) * 0.05 + 1e-3; y1 += Math.abs(y1) * 0.05 + 1e-3; }
    var pad = (y1 - y0) * 0.08; y0 -= pad; y1 += pad;
    function X(t) { return L + (t - x0) / (x1 - x0) * (W - L - R); }
    function Y(v) { return T + (y1 - v) / (y1 - y0) * (H - T - B); }
    var tsc = x1 > 7200 ? 3600 : x1 > 120 ? 60 : 1, tun = (tsc === 3600 ? "h" : tsc === 60 ? "min" : "s") + (D.t0 ? " from " + D.t0.slice(0, 10) : "");
    var g = '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + (H - B) + '" y2="' + (H - B) + '" class="nv-ax"/>';
    [y0 + pad, (y0 + y1) / 2, y1 - pad].forEach(function (v) { g += '<text x="' + (L - 5) + '" y="' + (Y(v) + 4) + '" text-anchor="end">' + fmt(v) + '</text><line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" class="nv-grid"/>'; });
    var single = series.every(function (r) { return r.t.length === 1; });
    if (single) g += '<text x="' + ((L + W - R) / 2) + '" y="' + (H - 8) + '" text-anchor="middle" class="nv-unit">at the end of the run</text>';
    else {
      [[x0, "start"], [(x0 + x1) / 2, "middle"]].forEach(function (a) { var v = a[0] / tsc; g += '<text x="' + X(a[0]) + '" y="' + (H - 8) + '" text-anchor="' + a[1] + '">' + (Math.abs(v) >= 10 ? Math.round(v) : Math.round(v * 10) / 10) + "</text>"; });
      g += '<text x="' + (W - R) + '" y="' + (H - 8) + '" text-anchor="end" class="nv-unit">' + (Math.abs(x1 / tsc) >= 10 ? Math.round(x1 / tsc) : Math.round(x1 / tsc * 10) / 10) + " " + tun + "</text>";
    }
    series.forEach(function (r) {
      var s = r[kind][id], d = "", pen = false, dots = "";
      r.t.forEach(function (t, i) {
        var v = s[i]; if (v === null) { pen = false; return; }
        d += (pen ? "L" : "M") + X(t).toFixed(1) + "," + Y(v).toFixed(1); pen = true;
        if (r.t.length <= 3) dots += '<circle cx="' + X(t).toFixed(1) + '" cy="' + Y(v).toFixed(1) + '" r="4" fill="' + r.color + '"/>';
      });
      var dash = r.role === "model" ? "" : ' stroke-dasharray="5 3"';
      g += '<path d="' + d + '" fill="none" stroke="' + r.color + '" stroke-width="' + (r === cur ? 2.6 : 1.6) + '"' + dash + "/>" + dots;
    });
    if (cur && cur.t.length > 1) g += '<line x1="' + X(cur.t[ti]) + '" x2="' + X(cur.t[ti]) + '" y1="' + T + '" y2="' + (H - B) + '" class="nv-cursor"/>';
    var seek = cur && cur.t.length > 1 ? ' data-x0="' + x0 + '" data-x1="' + x1 + '" data-l="' + L + '" data-r="' + (W - R) + '" data-w="' + W + '"' : "";
    return '<svg class="nv-mini' + (seek ? " nv-seek" : "") + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Result over time at ' + esc(id) + '"' + seek + ">" + g + "</svg>" +
      (seek ? '<p class="small muted nv-mini-note">Click the chart to jump to that time.</p>' : "");
  }
  function renderSide() {
    if (!selected) { side.innerHTML = '<p class="muted small">Click a ' + (D.kind === "swmm" ? "manhole, junction or pipe" : "junction or pipe") + " on the map to see what the input file says about it and every engine's result there.</p>"; return; }
    var kind = selected.kind, id = selected.id, el = kind === "nodes" ? N.nodes[id] : N.links[id];
    if (!el) { side.innerHTML = ""; return; }
    var vv = D.vars[kind === "nodes" ? "node" : "link"];
    var h = '<div class="nv-side-head"><h3>' + esc(id) + '</h3><span class="tag">' + esc(TYPE[D.kind][el.sec] || el.sec) + '</span><button type="button" class="linkish nv-back-map" id="nv-back-map">↑ Map</button></div>';
    if (kind === "links") {
      h += '<p class="small">From <button type="button" class="linkish" data-node="' + esc(el.from) + '">' + esc(el.from) + '</button> to <button type="button" class="linkish" data-node="' + esc(el.to) + '">' + esc(el.to) + "</button></p>";
    }
    if (vv && D.results.length) {
      var t = cur ? cur.t[ti] : null;
      var rows = D.results.map(function (r) {
        var s = r[kind][id]; if (!s) return "";
        var j = t === null ? r.t.length - 1 : nearestIndex(r.t, t);
        var near = t === null || r.t.length === 1 ? (r.t.length === 1 ? Math.abs(r.t[0] - (t === null ? r.t[0] : t)) < 1e-6 || !cur || cur.t.length === 1 : true) : true;
        var v = near ? s[j] : null;
        var rv = r !== ref && ref ? refAt(kind, id, t === null ? r.t[j] : t) : null;
        var diff = v !== null && rv !== null && rv !== undefined ? v - rv : null;
        return "<tr" + (r === cur ? ' class="nv-cur"' : "") + '><td><span class="sw" style="background:' + r.color + '"></span>' + esc(r.label) + '</td><td class="num mono">' + fmt(v) + '</td><td class="num mono">' + (diff === null ? "" : (diff > 0 ? "+" : "") + fmt(diff)) + "</td></tr>";
      }).join("");
      if (rows) {
        h += '<p class="small nv-at">' + esc(vv.label) + " (" + esc(vv.unit) + ")" + (cur && cur.t.length > 1 ? ", " + esc(clock(cur.t[ti])) : "") + "</p>";
        h += '<table class="data nv-vals"><thead><tr><th>Engine</th><th class="num">Value</th><th class="num">' + (ref ? "− " + esc(ref.role === "exact" ? "exact" : ref.role === "measured" ? "measured" : "reference") : "") + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
        h += miniChart(kind, id);
      } else h += '<p class="small muted">No engine reports a result here' + (D.sid === "A1F-100" ? " (results are kept at the seven level meters only)" : "") + ".</p>";
    }
    h += '<h4 class="nv-h4">In the input file</h4><table class="data nv-props"><tbody>' + propsTable(el.sec, el.row);
    if (el.xs) h += '<tr><td colspan="2" class="nv-sub">[XSECTIONS]</td></tr>' + propsTable("XSECTIONS", el.xs);
    if (kind === "nodes" && !N.laidOut) h += '<tr><td colspan="2" class="nv-sub">[COORDINATES]</td></tr><tr><th>X, Y</th><td class="mono">' + fmt(el.x) + ", " + fmt(el.y) + "</td></tr>";
    h += "</tbody></table>";
    h += '<p class="small"><button type="button" class="linkish" id="nv-in-file">Every line about ' + esc(id) + ' in the file →</button> <span class="muted">(line ' + (el.row.line + 1) + ")</span></p>";
    side.innerHTML = h;
    var bm = $("nv-back-map");
    if (bm) bm.addEventListener("click", function () { canvas.scrollIntoView({ behavior: "smooth", block: "center" }); });
    var mc = side.querySelector(".nv-seek");
    if (mc) mc.addEventListener("click", function (e) {
      var r = mc.getBoundingClientRect(), sx = (e.clientX - r.left) / r.width * +mc.getAttribute("data-w");
      var l = +mc.getAttribute("data-l"), rr = +mc.getAttribute("data-r"), x0 = +mc.getAttribute("data-x0"), x1 = +mc.getAttribute("data-x1");
      var t = x0 + Math.max(0, Math.min(1, (sx - l) / (rr - l))) * (x1 - x0);
      stop(); setTime(nearestIndex(cur.t, t));
    });
    side.querySelectorAll("[data-node]").forEach(function (b) { b.addEventListener("click", function () { select({ kind: "nodes", id: b.getAttribute("data-node") }); }); });
    var f = $("nv-in-file");
    if (f) f.addEventListener("click", function () { showTab("file"); find.value = id; runFind(true); });
  }
  function select(h, how) {
    selected = h;
    renderSide(); draw();
    // on a phone the details sit below the map: bring them into view after a tap
    if (h && how === "tap" && window.innerWidth <= 960) side.scrollIntoView({ behavior: "smooth", block: "start" });
    if (h && how !== "auto") try { history.replaceState(null, "", "#" + D.sid + ":" + (h.kind === "nodes" ? "node" : "link") + ":" + h.id); } catch (e) { /* ignore */ }
  }

  // ── time ───────────────────────────────────────────────────────────────────
  function setTime(i) {
    ti = Math.max(0, Math.min(i, cur ? cur.t.length - 1 : 0));
    scrub.value = ti;
    tlabel.textContent = cur ? clock(cur.t[ti]) : "";
    draw();
    if (selected) renderSide();
  }
  var ICON_PLAY = '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 L16 9 L4 16 Z"/></svg>';
  var ICON_PAUSE = '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2 H8 V16 H4 Z M10 2 H14 V16 H10 Z"/></svg>';
  function stop() { if (timer) { clearInterval(timer); timer = null; } play.innerHTML = ICON_PLAY; play.setAttribute("aria-label", "Play"); }
  function start() {
    if (!cur || cur.t.length < 2) return;
    if (ti >= cur.t.length - 1) setTime(0);
    play.innerHTML = ICON_PAUSE; play.setAttribute("aria-label", "Pause");
    timer = setInterval(function () { if (ti >= cur.t.length - 1) { stop(); return; } setTime(ti + 1); }, Math.max(30, 9000 / cur.t.length) / speed);
  }
  play.addEventListener("click", function () { if (timer) stop(); else start(); });
  $("nv-back").addEventListener("click", function () { stop(); setTime(ti - 1); });
  $("nv-fwd").addEventListener("click", function () { stop(); setTime(ti + 1); });
  scrub.addEventListener("input", function () { stop(); setTime(+scrub.value); });
  document.querySelectorAll("[data-nvspeed]").forEach(function (b) {
    b.addEventListener("click", function () {
      speed = +b.getAttribute("data-nvspeed");
      document.querySelectorAll("[data-nvspeed]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      if (timer) { stop(); start(); }
    });
  });
  document.addEventListener("keydown", function (e) {
    if (!cur || cur.t.length < 2 || paneMap.hidden || e.altKey || e.ctrlKey || e.metaKey) return;
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "select" || tag === "textarea" || (tag === "button" && e.key === " ")) return;
    if (e.key === " ") { e.preventDefault(); if (timer) stop(); else start(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); stop(); setTime(ti + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); stop(); setTime(ti - 1); }
  });

  // ── flow animation ─────────────────────────────────────────────────────────
  function flowOn() { return flowBox.checked && !paneMap.hidden; }
  function hasFlow() { return !!(cur && D.vars.link && Object.keys(cur.links).length); }
  function tick(now) {
    raf = null;
    if (!flowOn() || !hasFlow()) return;
    if (now - lastFrame > 33) { phase += (now - lastFrame) * 0.03; lastFrame = now; draw(); }
    raf = requestAnimationFrame(tick);
  }
  function animate() {
    if (raf) cancelAnimationFrame(raf);
    raf = null; lastFrame = performance.now();
    if (flowOn() && hasFlow()) raf = requestAnimationFrame(tick); else draw();
  }
  flowBox.addEventListener("change", function () { renderLegend(); animate(); });
  if ("IntersectionObserver" in window) new IntersectionObserver(function (es) {  // pause off screen
    es.forEach(function (en) { if (!en.isIntersecting && raf) { cancelAnimationFrame(raf); raf = null; } else if (en.isIntersecting) animate(); });
  }).observe(canvas);

  // ── engines and colouring ──────────────────────────────────────────────────
  function roleTag(r) { return r.role === "exact" ? "exact answer" : r.role === "measured" ? "measured" : r.role === "model" ? "" : "reference"; }
  function renderEngines() {
    var h = '<span class="nv-eng-lbl small">Show</span><button type="button" class="vw-chip" data-res="" aria-pressed="' + (!cur) + '">Network only</button>';
    D.results.forEach(function (r) {
      var tag = roleTag(r), parts = r.label.split(" · ");
      h += '<button type="button" class="vw-chip' + (tag ? " nv-ref" : "") + '" data-res="' + esc(r.key) + '" aria-pressed="' + (cur === r) + '"><span class="sw" style="background:' + esc(r.color) + '"></span>' +
        esc(tag ? (r.role === "reference" ? parts[0].replace(/ \(reference\)$/, "") : tag.charAt(0).toUpperCase() + tag.slice(1)) : parts[0]) +
        (!tag && parts.length > 1 ? ' <span class="vw-chip-sub">' + esc(parts.slice(1).join(" · ")) + "</span>" : "") +
        (tag && r.role === "reference" ? ' <span class="vw-chip-sub">reference</span>' : "") +
        (r.verdict ? '<span class="vw-chip-v ' + (r.verdict === "pass" ? "pass" : "fail") + '" title="' + (r.verdict === "pass" ? "passes the test" : "fails the test") + '">' + (r.verdict === "pass" ? "✓" : "✗") + "</span>" : "") + "</button>";
    });
    engines.innerHTML = h;
    engines.querySelectorAll("[data-res]").forEach(function (b) { b.addEventListener("click", function () { setResult(b.getAttribute("data-res")); }); });
  }
  function setMode(m) {
    mode = m;
    modeBox.querySelectorAll("[data-nvmode]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-nvmode") === m ? "true" : "false"); });
  }
  modeBox.querySelectorAll("[data-nvmode]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.disabled) return;
      setMode(b.getAttribute("data-nvmode")); computeScales(); renderLegend(); draw(); if (selected) renderSide();
    });
  });
  function setResult(key) {
    stop();
    cur = D.results.filter(function (r) { return r.key === key; })[0] || null;
    engines.querySelectorAll("[data-res]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-res") === (cur ? cur.key : "") ? "true" : "false"); });
    var canDiff = !!ref && cur && cur !== ref, db = modeBox.querySelector('[data-nvmode="diff"]');
    db.disabled = !canDiff;
    db.title = canDiff ? "" : (ref ? "Pick an engine to compare with the " + roleTag(ref) : "This test has no reference to compare with");
    if (!canDiff) setMode("value");
    sparse = !!(cur && N.nodeList.length > 40 && Object.keys(cur.nodes).length < 0.1 * N.nodeList.length);
    timeBox.hidden = !cur || cur.t.length < 2;
    $("nv-flow").parentNode.hidden = !hasFlow();
    if (cur) { scrub.max = cur.t.length - 1; ti = Math.min(ti, cur.t.length - 1); }
    computeScales(); renderLegend(); setTime(ti);
    if (selected) renderSide();
    animate();
  }

  // the element worth looking at first: the biggest gap from the reference, else the first reported one
  function pickDefault() {
    var R = cur || D.results[0];
    if (!R) return null;
    var best = null, bv = -1;
    ["nodes", "links"].forEach(function (kind) {
      Object.keys(R[kind]).forEach(function (id) {
        if (kind === "nodes" ? !N.nodes[id] : !N.links[id]) return;
        var s = R[kind][id], r = ref && ref !== R ? ref[kind][id] : null, v = 0;
        if (ref && ref !== R && Object.keys(ref[kind]).length && !r) return;  // compare where there is something to compare with
        if (r) { for (var i = 0; i < s.length; i++) { var j = nearestIndex(ref.t, R.t[i]); if (s[i] !== null && r[j] !== null && r[j] !== undefined) v = Math.max(v, Math.abs(s[i] - r[j])); } }
        else s.forEach(function (x) { if (x !== null) v = Math.max(v, Math.abs(x)); });
        if (kind === "links") v *= 1e-9;  // prefer a node: its chart reads more plainly
        if (v > bv) { bv = v; best = { kind: kind, id: id }; }
      });
    });
    return best;
  }

  // ── input file tab ─────────────────────────────────────────────────────────
  function lineHtml(i) {
    var s = P.lines[i], cls = "";
    var t = s.trim();
    if (t.charAt(0) === "[") cls = "nv-l-sec"; else if (t.charAt(0) === ";") cls = "nv-l-com";
    var body = esc(s);
    if (!cls && s.indexOf(";") >= 0) { var k = s.indexOf(";"); body = esc(s.slice(0, k)) + '<span class="nv-l-com">' + esc(s.slice(k)) + "</span>"; }
    return '<span class="nv-line' + (cls ? " " + cls : "") + '"><span class="ln">' + (i + 1) + "</span>" + (body || " ") + "</span>";
  }
  function showSection(name) {
    fileSec = name;
    var o = P.order.filter(function (x) { return x.name === name; })[0];
    secNav.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-sec") === name ? "true" : "false"); });
    if (!o) return;
    var end = Math.min(o.end, o.line + 3000), out = [];
    for (var i = o.line; i < end; i++) out.push(lineHtml(i));
    if (o.end > end) out.push('<span class="nv-line nv-l-com"><span class="ln"></span>… ' + (o.end - end) + " more lines in this section: download the file to see them all.</span>");
    src.innerHTML = out.join("");
    src.scrollTop = 0;
    findN.textContent = "";
  }
  var WHOLE = 5000;  // files up to this many lines are shown whole; longer ones a section at a time
  function showWhole() {
    fileSec = "*";
    var out = [];
    for (var i = 0; i < P.lines.length; i++) out.push(lineHtml(i).replace('<span class="nv-line', '<span id="nv-ln-' + i + '" class="nv-line'));
    src.innerHTML = out.join(""); src.scrollTop = 0; findN.textContent = "";
    secNav.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-sec") === "*" ? "true" : "false"); });
  }
  function renderFileNav() {
    var whole = P.lines.length <= WHOLE;
    secNav.innerHTML = (whole ? '<button type="button" data-sec="*" aria-pressed="true">Whole file <span class="muted">' + P.lines.length + "</span></button>" : "") +
      P.order.map(function (o) { return '<button type="button" data-sec="' + esc(o.name) + '" aria-pressed="false">' + esc(o.name) + ' <span class="muted">' + o.rows + "</span></button>"; }).join("");
    secNav.querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        var name = b.getAttribute("data-sec");
        find.value = "";
        if (name === "*") { showWhole(); return; }
        if (whole) {  // jump within the whole file
          if (fileSec !== "*") showWhole();
          var o = P.order.filter(function (x) { return x.name === name; })[0], el = o && $("nv-ln-" + o.line);
          if (el) src.scrollTop = el.offsetTop - src.offsetTop;
          secNav.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
          return;
        }
        showSection(name);
      });
    });
    if (whole) showWhole(); else showSection(P.order.length ? P.order[0].name : null);
  }
  function runFind(exactId) {
    var q = find.value.trim();
    if (!q) { if (P.lines.length <= WHOLE) showWhole(); else showSection(fileSec && fileSec !== "*" ? fileSec : (P.order[0] && P.order[0].name)); return; }
    var ql = q.toLowerCase(), hits = [], secOf = function (i) { var n = null; P.order.forEach(function (o) { if (o.line <= i) n = o.name; }); return n; };
    for (var i = 0; i < P.lines.length && hits.length < 400; i++) {
      var s = P.lines[i];
      if (exactId ? s.split(";")[0].trim().split(/\s+/).indexOf(q) >= 0 : s.toLowerCase().indexOf(ql) >= 0) hits.push(i);
    }
    var last = null, out = [];
    hits.forEach(function (i) {
      var sc = secOf(i);
      if (sc !== last) { out.push('<span class="nv-line nv-l-sec"><span class="ln"></span>[' + esc(sc) + "]</span>"); last = sc; }
      out.push(lineHtml(i));
    });
    src.innerHTML = out.join("") || '<span class="nv-line nv-l-com"><span class="ln"></span>No line matches.</span>';
    findN.textContent = hits.length + (hits.length >= 400 ? "+" : "") + " line" + (hits.length === 1 ? "" : "s");
    secNav.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
  }
  var findT = null;
  find.addEventListener("input", function () { clearTimeout(findT); findT = setTimeout(function () { runFind(false); }, 180); });

  function showTab(which) {
    var map = which === "map";
    tabMap.setAttribute("aria-selected", map ? "true" : "false"); tabFile.setAttribute("aria-selected", map ? "false" : "true");
    paneMap.hidden = !map; paneFile.hidden = map;
    if (map) animate(); else if (raf) { cancelAnimationFrame(raf); raf = null; }
  }
  tabMap.addEventListener("click", function () { showTab("map"); });
  tabFile.addEventListener("click", function () { showTab("file"); });

  // ── loading a test ─────────────────────────────────────────────────────────
  function renderDownloads() {
    var h = '<a class="btn primary" href="' + esc(D.inp.url) + '" download>Download ' + esc(D.inp.name) + ' <span class="nv-kb">' + kb(D.inp.bytes) + "</span></a>";
    h += '<a class="btn" href="' + esc(D.case_zip) + '" download>Whole test (.zip)</a>';
    h += '<a class="btn ghost" href="tests/' + esc(D.sid) + '.html">Test page →</a>';
    dl.innerHTML = h;
    var f = "Drawn from " + esc(D.inp.name) + ", " + esc(D.inp.source) + (N && N.laidOut ? ". The file has no map coordinates, so the network is laid out by distance along the pipes" : "") + ".";
    if (D.zips.length) f += " The files each engine ran: " + D.zips.map(function (z) { return '<a href="' + esc(z.url) + '" download>' + esc(z.label) + "</a>"; }).join(" · ") + ".";
    foot.innerHTML = symbolsHtml() + '<span class="nv-src-note">' + f + "</span>";
  }
  function renderSummary() {
    var o = N.options, bits = [D.kind === "swmm" ? "SWMM" : "EPANET"];
    N.counts.forEach(function (c) { bits.push(c[0] + " " + c[1].toLowerCase().replace(/ \(manhole\)/, "") + (c[0] === 1 || /s$/.test(c[1]) ? "" : "s")); });
    if (o.FLOW_UNITS) bits.push(o.FLOW_UNITS); else if (o.UNITS) bits.push(o.UNITS);
    if (o.FLOW_ROUTING) bits.push(o.FLOW_ROUTING.toLowerCase().replace("dynwave", "dynamic wave").replace("kinwave", "kinematic wave"));
    summary.textContent = bits.join(" · ");
  }
  function load(sid, focus) {
    stop();
    selected = null; side.innerHTML = '<p class="muted small">Loading…</p>';
    fetch("data/network/" + encodeURIComponent(sid) + ".json").then(function (r) { return r.json(); }).then(function (d) {
      D = d;
      return fetch(d.inp.url).then(function (r) { return r.text(); });
    }).then(function (text) {
      P = parseInp(text); N = buildNet(D.kind);
      ref = D.results.filter(function (r) { return r.role !== "model"; })[0] || null;
      var first = D.results.filter(function (r) { return r.role === "model"; })[0] || D.results[0];
      cur = first || null;
      var refLabel = ref ? (ref.role === "exact" ? "exact answer" : ref.role === "measured" ? "measurements" : ref.label.replace(/ \(reference\)$/, "")) : "";
      modeBox.querySelector('[data-nvmode="diff"]').textContent = ref ? "Difference from " + refLabel : "Difference";
      ti = 0;
      renderEngines(); renderDownloads(); renderSummary(); renderFileNav();
      setResult(first ? first.key : "");
      fit(); lastW = canvas.clientWidth;
      if (cur && cur.t.length > 1) setTime(Math.floor(cur.t.length / 2));
      if (focus) { var p = focus.split(":"); select({ kind: p[0] === "link" ? "links" : "nodes", id: p.slice(1).join(":") }); }
      else { var d0 = pickDefault(); if (d0) select(d0, "auto"); else renderSide(); }
    }).catch(function (e) { side.innerHTML = '<p class="small">Could not load this test: ' + esc(e.message || e) + "</p>"; });
  }
  testSel.addEventListener("change", function () { try { history.replaceState(null, "", "#" + testSel.value); } catch (e) { /* ignore */ } load(testSel.value); });

  var hash = decodeURIComponent((location.hash || "").slice(1)), start = IDX.first, focus = null;
  if (hash) {
    var parts = hash.split(":");
    if (IDX.tests.some(function (t) { return t.sid === parts[0]; })) { start = parts[0]; if (parts.length > 2) focus = parts.slice(1).join(":"); }
  }
  testSel.value = start;
  if (start) load(start, focus);
})();
