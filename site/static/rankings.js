// Leaderboard: the OpenHydro rating (Bradley–Terry over head-to-head results, 95 % bootstrap interval),
// the full table, accuracy against run time and every result, recomputed in the browser for the chosen
// board and model kinds. The arithmetic repeats site/ranking.py exactly (same random numbers, same order).
// Data: #rk-data (site/rankpage.py).
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("rk-data").textContent);
  function $(id) { return document.getElementById(id); }
  var R = D.rules, group = "", kinds = {}, query = "", sortKey = "rank", sortDir = 1;
  document.querySelectorAll(".rk-kinds input").forEach(function (c) { kinds[c.value] = c.checked; });
  var GNAME = {}; D.groups.forEach(function (g) { GNAME[g[0]] = g[1]; });
  var TORDER = {}; D.tests.forEach(function (t, i) { TORDER[t.sid] = i; });

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function num(s) { return s < 1 ? String(Number(s.toPrecision(2))) : s < 10 ? s.toFixed(1) : s < 1e4 ? String(Math.round(s)) : s.toExponential(0).replace("e+", "e"); }
  function short(s) {
    if (s === null || s === undefined) return "–";
    if (!isFinite(s) || s >= 1e12) return "∞";
    return s < 0.01 ? "<0.01 %" : num(s) + " %";
  }
  function klass(s) {
    if (s === null || s === undefined) return "sn";
    for (var i = 0; i < R.bands.length; i++) if (s < R.bands[i][0]) return R.bands[i][1];
    return "s5";
  }
  function time(s) {
    if (s === null || s === undefined) return "–";
    return s < 1 ? s.toFixed(2) + " s" : s < 60 ? s.toFixed(1) + " s" : s < 3600 ? (s / 60).toFixed(1) + " min" : (s / 3600).toFixed(1) + " h";
  }
  function tied(a, b) {
    if (!isFinite(a) || !isFinite(b)) return a === b;
    if (a < R.tie_floor && b < R.tie_floor) return true;
    var hi = Math.max(a, b);
    return hi === 0 || Math.abs(a - b) <= R.tie_rel * hi;
  }
  function median(v) { var s = v.slice().sort(function (a, b) { return a - b; }), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; }

  // ── the rating (site/ranking.py: _mulberry32, _fit, rating_board) ───────────
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function tiedOn(sid, a, b) { var f = R.noise[sid]; return tied(a, b) || (f !== undefined && a <= f && b <= f); }
  function fit(keys, tests, pick) {  // each test's matches share one unit of weight (site/ranking.py: _fit)
    var n = keys.length, idx = {}, wins = [], games = {}, i, j;
    keys.forEach(function (k, q) { idx[k] = q; wins.push(R.prior); });
    pick.forEach(function (ti) {
      var sid = tests[ti][0], rows = tests[ti][1], w = 2 / (rows.length * (rows.length - 1));
      for (var a = 0; a < rows.length; a++) for (var b = a + 1; b < rows.length; b++) {
        i = idx[rows[a][0]]; j = idx[rows[b][0]];
        var sa = rows[a][1], sb = rows[b][1];
        if (tiedOn(sid, sa, sb)) { wins[i] += 0.5 * w; wins[j] += 0.5 * w; } else if (sa < sb) wins[i] += w; else wins[j] += w;
        var key = i < j ? i * 100000 + j : j * 100000 + i;
        games[key] = (games[key] || 0) + w;
      }
    });
    var pairs = Object.keys(games).map(Number).sort(function (x, y) { return x - y; })
      .map(function (k) { return [Math.floor(k / 100000), k % 100000, games[k]]; });
    var p = []; for (i = 0; i < n; i++) p.push(1);
    for (var it = 0; it < 200; it++) {
      var den = p.map(function (pi) { return 2 * R.prior / (pi + 1); });
      pairs.forEach(function (q) { var s = q[2] / (p[q[0]] + p[q[1]]); den[q[0]] += s; den[q[1]] += s; });
      var nw = [], lg = 0;
      for (i = 0; i < n; i++) nw.push(wins[i] / den[i]);
      for (i = 0; i < n; i++) lg += Math.log(nw[i]);
      var g = Math.exp(lg / n), dmax = 0;
      for (i = 0; i < n; i++) { nw[i] = nw[i] / g; dmax = Math.max(dmax, Math.abs(Math.log(nw[i] / p[i]))); }
      p = nw;
      if (dmax < 1e-9) break;
    }
    return p.map(function (x) { return 1000 + 400 * Math.log10(x); });
  }
  function component(keys, tests) {  // the largest set of models linked by shared tests (site/ranking.py: _component)
    var parent = {};
    keys.forEach(function (k) { parent[k] = k; });
    function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
    tests.forEach(function (t) {
      var rows = t[1];
      for (var q = 1; q < rows.length; q++) {
        var a = find(rows[0][0]), b = find(rows[q][0]);
        if (a !== b) { if (a < b) parent[b] = a; else parent[a] = b; }
      }
    });
    var comps = {};
    keys.forEach(function (k) { var r = find(k); (comps[r] = comps[r] || []).push(k); });
    var best = null, bs = null;
    Object.keys(comps).forEach(function (r) {
      var c = comps[r].slice().sort(), nt = tests.filter(function (t) { return t[1].some(function (x) { return c.indexOf(x[0]) >= 0; }); }).length;
      var sc = [c.length, nt, c.join("")];
      if (!bs || sc[0] > bs[0] || (sc[0] === bs[0] && (sc[1] > bs[1] || (sc[1] === bs[1] && sc[2] > bs[2])))) { best = c; bs = sc; }
    });
    return best || [];
  }
  function shown(k) { var m = D.models[k]; return !!(m && kinds[m.kind]); }
  function board() {
    var bt = {}, keysSet = {}, times = {}, byG = {};
    D.results.forEach(function (r) {
      var t = D.tests[TORDER[r[0]]];
      if (!t || r[2] === null || r[5] || !shown(r[1])) return;  // r[5]: the engine flags the run
      if (group ? t.group !== group : R.rated_groups.indexOf(t.group) < 0) return;  // overall: physics groups only
      (bt[r[0]] = bt[r[0]] || []).push([r[1], r[2]]);
      keysSet[r[1]] = 1;
      var gg = (byG[r[1]] = byG[r[1]] || {});
      (gg[t.group] = gg[t.group] || []).push(r[2]);
      if (r[3] !== null && r[3] !== undefined) (times[r[1]] = times[r[1]] || []).push(r[3]);
    });
    var tests = Object.keys(bt).sort(function (a, b) { return TORDER[a] - TORDER[b]; })
      .map(function (sid) { return [sid, bt[sid].sort(function (x, y) { return x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0; })]; })
      .filter(function (t) { return t[1].length >= 2; });
    var keysAll = Object.keys(keysSet).sort();
    if (!keysAll.length) return [];
    var keys = component(keysAll, tests), inMain = {};
    keys.forEach(function (k) { inMain[k] = 1; });
    var mtests = tests.filter(function (t) { return inMain[t[1][0][0]]; });
    var all = []; for (var q = 0; q < mtests.length; q++) all.push(q);
    var point = keys.length ? fit(keys, mtests, all) : [], rnd = mulberry32(R.seed), draws = [];
    for (var b = 0; b < (keys.length ? R.boot : 0); b++) {
      var pick = []; for (var z = 0; z < mtests.length; z++) pick.push(Math.floor(rnd() * mtests.length));
      draws.push(fit(keys, mtests, pick));
    }
    var out = keysAll.map(function (k) {
      var g = byG[k] || {}, allS = [], gm = {};
      Object.keys(g).forEach(function (x) { gm[x] = median(g[x]); allS = allS.concat(g[x]); });
      var r = { key: k, tests: tests.filter(function (t) { return t[1].some(function (x) { return x[0] === k; }); }).length,
                groups: gm, med: median(allS), time: median(times[k] || []), timed: (times[k] || []).length,
                connected: !!inMain[k], rating: null, lo: null, hi: null };
      if (inMain[k]) {
        var i = keys.indexOf(k), col = draws.map(function (d) { return d[i]; }).sort(function (x, y) { return x - y; });
        r.rating = point[i]; r.lo = col[Math.floor(0.025 * (R.boot - 1))]; r.hi = col[Math.ceil(0.975 * (R.boot - 1))];
      }
      return r;
    });
    out.forEach(function (r) { r.ranked = r.connected && r.tests >= R.min_tests; });
    var ranked = out.filter(function (r) { return r.ranked; });
    out.forEach(function (r) { r.rank = r.ranked ? 1 + ranked.filter(function (o) { return o.lo > r.hi; }).length : null; });
    ranked.forEach(function (r) { r.tie = ranked.filter(function (o) { return o.rank === r.rank; }).length > 1; });
    out.sort(function (a, b) {  // ranked first, by rank, then rating; unranked by tests (site/ranking.py)
      if (a.ranked !== b.ranked) return a.ranked ? -1 : 1;
      if (a.ranked) return (a.rank - b.rank) || (b.rating - a.rating);
      return b.tests - a.tests;
    });
    return out;
  }

  function match(k) { if (!query) return true; var m = D.models[k]; return (m.name + " " + m.sub + " " + (m.org || "")).toLowerCase().indexOf(query) >= 0; }

  // ── rating chart ────────────────────────────────────────────────────────────
  function chart(rows) {
    var box = $("rc"); if (!box) return;
    var rr = rows.filter(function (r) { return r.ranked && match(r.key); });
    if (!rr.length) { box.innerHTML = '<li class="rc-empty">No ranked models in this view: a model needs ' + R.min_tests + " tests in the board.</li>"; return; }
    var lo = Math.min.apply(null, rr.map(function (r) { return r.lo; })), hi = Math.max.apply(null, rr.map(function (r) { return r.hi; }));
    var base = (Math.floor(lo / 50) - 1) * 50, span = Math.max(hi - base, 1);
    box.innerHTML = rr.map(function (r) {
      var m = D.models[r.key], w = 100 * (r.rating - base) / span, a = 100 * (r.lo - base) / span, b = 100 * (r.hi - base) / span;
      return '<li><a class="rc-name" href="solvers/' + esc(r.key) + '.html"><span class="rc-rank">' + r.rank + (r.tie ? "=" : "") + '</span><span class="sw" style="background:' + esc(m.color) + '"></span><b>' + esc(m.name) + '</b> <span class="lb-sub">' + esc(m.sub) + "</span></a>" +
        '<span class="rc-track" title="' + Math.round(r.rating) + " (95 % interval " + Math.round(r.lo) + " to " + Math.round(r.hi) + ')">' +
        '<i class="rc-ci" style="left:' + a.toFixed(2) + "%;width:" + Math.max(b - a, 0.6).toFixed(2) + '%"></i><i class="rc-dot" style="left:' + w.toFixed(2) + '%"></i></span><span class="rc-val">' + Math.round(r.rating) + "</span></li>";
    }).join("");
  }

  // ── full table ──────────────────────────────────────────────────────────────
  function groupsShown() { return D.groups.filter(function (g) { return D.tests.some(function (t) { return t.group === g[0] && (!group || t.group === group); }); }); }
  function sorted(rows) {
    var v = function (r) {
      if (sortKey === "rating") return r.ranked ? r.rating : -Infinity;
      if (sortKey === "rank") return r.ranked ? r.rank : 1e9 - r.tests;
      if (sortKey === "tests") return r.tests;
      if (sortKey === "time") return r.time === null ? Infinity : r.time;
      if (sortKey === "name") return D.models[r.key].name + " " + D.models[r.key].sub;
      if (sortKey.indexOf("g:") === 0) { var x = r.groups[sortKey.slice(2)]; return x === undefined ? Infinity : x; }
      return 0;
    };
    return rows.slice().sort(function (a, b) {
      var x = v(a), y = v(b);
      if (typeof x === "string") return sortDir * (x < y ? -1 : x > y ? 1 : 0);
      if (x === y) return current.indexOf(a) - current.indexOf(b);
      if (!isFinite(x)) return 1;
      if (!isFinite(y)) return -1;
      return sortDir * (x - y);
    });
  }
  function table(rows) {
    var gs = groupsShown(), t = $("lb-table");
    var th = function (key, label, cls) {
      var on = sortKey === key;
      return '<th scope="col"' + (cls ? ' class="' + cls + '"' : "") + (on ? ' aria-sort="' + (sortDir < 0 ? "descending" : "ascending") + '"' : "") +
        '><button type="button" data-sort="' + key + '">' + esc(label) + (on ? (sortDir < 0 ? " ↓" : " ↑") : "") + "</button></th>";
    };
    var h = "<thead><tr>" + th("rank", "Rank", "num") + th("name", "Model") + th("rating", "Rating", "num") + '<th scope="col" class="num">95 % interval</th>' + th("tests", "Tests", "num") +
      gs.map(function (g) { return th("g:" + g[0], g[1], "num lb-g"); }).join("") + th("time", "Median run time", "num") + '<th scope="col">Licence</th></tr></thead><tbody>';
    var shownRows = sorted(rows).filter(function (r) { return match(r.key); });
    shownRows.forEach(function (r) {
      var m = D.models[r.key];
      var why = r.ranked ? "" : !r.connected ? "no test shared with the rated models" : "fewer than " + R.min_tests + " tests";
      h += "<tr" + (r.ranked ? "" : ' class="lb-unranked"') + '><td class="num lb-rank">' + (r.ranked ? r.rank + (r.tie ? "=" : "") : "–") + "</td>" +
        '<td class="lb-model"><a href="solvers/' + esc(r.key) + '.html"><span class="sw" style="background:' + esc(m.color) + '"></span><b>' + esc(m.name) + '</b> <span class="lb-sub">' + esc(m.sub) + "</span></a>" +
        '<div class="lb-org">' + esc(m.org || "") + "</div></td>" +
        '<td class="num lb-rating">' + (r.ranked ? Math.round(r.rating) : "–") + '</td><td class="num lb-ci">' + (r.ranked ? Math.round(r.lo) + "–" + Math.round(r.hi) : '<span class="lb-why">' + esc(why) + "</span>") + "</td>" +
        '<td class="num">' + r.tests + "</td>" +
        gs.map(function (g) { var x = r.groups[g[0]]; return x === undefined ? '<td class="num lb-none">–</td>' : '<td class="num"><span class="lb-cell ' + klass(x) + '">' + short(x) + "</span></td>"; }).join("") +
        '<td class="num">' + time(r.time) + (r.timed && r.timed < r.tests ? '<div class="lb-org">' + r.timed + " of " + r.tests + " timed</div>" : "") + "</td>" +
        '<td class="lb-lic">' + esc(m.licence || "") + "</td></tr>";
    });
    if (!shownRows.length) h += '<tr><td colspan="' + (7 + gs.length) + '">No model matches this view.</td></tr>';
    t.innerHTML = h + "</tbody>";
    t.querySelectorAll("[data-sort]").forEach(function (b) {
      b.addEventListener("click", function () {
        var k = b.getAttribute("data-sort");
        if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = (k === "rating" || k === "tests") ? -1 : 1; }
        table(current);
        var nb = t.querySelector('[data-sort="' + k + '"]'); if (nb) nb.focus();
      });
    });
    var nr = rows.filter(function (r) { return r.ranked; }).length, nt = D.tests.filter(function (x) { return !group || x.group === group; }).length;
    $("lb-note").textContent = nr + " model" + (nr === 1 ? "" : "s") + " ranked on " + nt + " test" + (nt === 1 ? "" : "s") +
      (group ? " in " + GNAME[group] : " in the physics groups (" + R.rated_groups.map(function (g) { return GNAME[g]; }).join(", ") + ")") +
      ", each test weighted equally. Rank is 1 + the number of models whose whole 95 % interval lies above the model's own, so a model can rank behind one it out-rates when its interval is wider; = marks a shared rank. Select a column heading to sort.";
  }

  // ── accuracy against run time ─────────────────────────────────────────────
  function speed(rows) {
    var box = $("rk-speed");
    var pts = rows.filter(function (r) { return r.ranked && r.time !== null && match(r.key); });
    if (pts.length < 2) { box.innerHTML = '<p class="muted small">Not enough timed models in this view.</p>'; return; }
    var W = Math.max(320, box.clientWidth || 560), H = 340, L = 52, Rr = 18, T = 14, B = 40;
    var xs = pts.map(function (p) { return Math.log10(Math.max(p.time, 1e-3)); }), ys = pts.map(function (p) { return p.rating; });
    var x0 = Math.floor(Math.min.apply(null, xs) - 0.2), x1 = Math.ceil(Math.max.apply(null, xs) + 0.2);
    var y0 = Math.floor((Math.min.apply(null, pts.map(function (p) { return p.lo; })) - 20) / 100) * 100;
    var y1 = Math.ceil((Math.max.apply(null, pts.map(function (p) { return p.hi; })) + 20) / 100) * 100;
    function X(v) { return L + (v - x0) / (x1 - x0) * (W - L - Rr); }
    function Y(v) { return T + (y1 - v) / (y1 - y0) * (H - T - B); }
    var mx = median(xs), my = median(ys);
    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" class="rk-scatter" role="img" aria-label="Rating against median run time">';
    svg += '<rect x="' + L + '" y="' + T + '" width="' + Math.max(0, X(mx) - L) + '" height="' + Math.max(0, Y(my) - T) + '" class="best"/><text x="' + (L + 8) + '" y="' + (T + 16) + '" class="best-t">more accurate and faster</text>';
    for (var d = y0; d <= y1; d += 100) svg += '<line x1="' + L + '" x2="' + (W - Rr) + '" y1="' + Y(d) + '" y2="' + Y(d) + '" class="g"/><text x="' + (L - 6) + '" y="' + (Y(d) + 4) + '" text-anchor="end">' + d + "</text>";
    for (var e = x0; e <= x1; e++) svg += '<line y1="' + T + '" y2="' + (H - B) + '" x1="' + X(e) + '" x2="' + X(e) + '" class="g"/><text x="' + X(e) + '" y="' + (H - B + 16) + '" text-anchor="middle">' + time(Math.pow(10, e)) + "</text>";
    svg += '<text x="' + ((L + W - Rr) / 2) + '" y="' + (H - 4) + '" text-anchor="middle">median run time, finest grid (log)</text>';
    // labels: the model's name (with its variant when two shown models share a name), placed clear of the others
    var names = {}; pts.forEach(function (p) { var n = D.models[p.key].name; names[n] = (names[n] || 0) + 1; });
    var boxes = pts.map(function (p, i) { return { x0: X(xs[i]) - 7, x1: X(xs[i]) + 7, y0: Y(ys[i]) - 7, y1: Y(ys[i]) + 7 }; });
    function hits(bx) { return boxes.some(function (o) { return bx.x0 < o.x1 && bx.x1 > o.x0 && bx.y0 < o.y1 && bx.y1 > o.y0; }) || bx.x1 > W - 2 || bx.y0 < T || bx.y1 > H - B; }
    var order = pts.map(function (p, i) { return i; }).sort(function (a, b) { return pts[b].rating - pts[a].rating; });
    var labels = {};
    order.forEach(function (i) {
      var m = D.models[pts[i].key], txt = names[m.name] > 1 ? m.name + " " + m.sub.split(" · ").pop() : m.name;
      var w = txt.length * 6.6 + 4, cx = X(xs[i]), cy = Y(ys[i]);
      var tries = [[9, 4], [9, -10], [9, 18], [-9 - w, 4], [-9 - w, -10], [-9 - w, 18], [9, -24], [9, 32]];
      for (var k = 0; k < tries.length; k++) {
        var lx = cx + tries[k][0], ly = cy + tries[k][1], bx = { x0: lx, x1: lx + w, y0: ly - 11, y1: ly + 3 };
        if (!hits(bx)) { boxes.push(bx); labels[i] = '<text x="' + lx + '" y="' + ly + '" class="pl">' + esc(txt) + "</text>"; break; }
      }
    });
    pts.forEach(function (p, i) {
      var m = D.models[p.key], cx = X(xs[i]), cy = Y(ys[i]);
      svg += '<g><line x1="' + cx + '" x2="' + cx + '" y1="' + Y(p.lo) + '" y2="' + Y(p.hi) + '" class="ci"/><circle cx="' + cx + '" cy="' + cy + '" r="6" fill="' + esc(m.color) + '" stroke="var(--sheet)" stroke-width="2"><title>' +
        esc(m.name + " " + m.sub + ": rating " + Math.round(p.rating) + ", median run time " + time(p.time)) + "</title></circle>" + (labels[i] || "") + "</g>";
    });
    box.innerHTML = svg + "</svg>";
  }

  // ── every result ────────────────────────────────────────────────────────────
  function portrait(rows) {
    var t = $("rk-portrait");
    var cols = D.tests.filter(function (x) { return (!group || x.group === group) && D.results.some(function (r) { return r[0] === x.sid && shown(r[1]); }); });
    var h = '<thead><tr><th scope="col" class="rk-corner">Model</th>';
    cols.forEach(function (x) { h += '<th scope="col" title="' + esc(x.name + " · " + GNAME[x.group]) + '"><a href="tests/' + esc(x.sid) + '.html"><span>' + esc(x.sid) + "</span></a></th>"; });
    h += "</tr></thead><tbody>";
    var res = {}; D.results.forEach(function (r) { res[r[0] + "|" + r[1]] = r; });
    rows.filter(function (r) { return match(r.key); }).forEach(function (r) {
      var m = D.models[r.key];
      h += '<tr><th scope="row"><span class="sw" style="background:' + esc(m.color) + '"></span>' + esc(m.name) + ' <span class="muted">' + esc(m.sub) + "</span></th>";
      cols.forEach(function (x) {
        var q = res[x.sid + "|" + r.key];
        if (!q || q[2] === null) { h += '<td class="rk-none"></td>'; return; }
        if (q[5]) { h += '<td class="rk-flag"><a href="tests/' + esc(x.sid) + ".html#m-" + esc(r.key) + '" title="' + esc(x.name + " · " + m.name + " " + m.sub + ": not ranked, the engine flags this run (" + q[5] + ")") + '">⚑</a></td>'; return; }
        h += '<td class="' + klass(q[2]) + '"><a href="tests/' + esc(x.sid) + ".html#m-" + esc(r.key) + '" title="' + esc(x.name + " · " + m.name + " " + m.sub + ": " + short(q[2]) + " off") + '">' + short(q[2]) + "</a></td>";
      });
      h += "</tr>";
    });
    t.innerHTML = h + "</tbody>";
  }

  var current = [];
  function redraw() { chart(current); table(current); speed(current); portrait(current); }
  function render() {
    current = board();
    redraw();
    try { history.replaceState(null, "", group ? "#" + group : location.pathname); } catch (e) { /* file:// */ }
  }
  document.querySelectorAll(".lb-gcard").forEach(function (c) {
    c.addEventListener("click", function () {
      var t = document.querySelector('.lb-tab[data-g="' + c.getAttribute("data-g") + '"]');
      if (t) { t.click(); t.scrollIntoView({ block: "start", behavior: "smooth" }); }
    });
  });
  document.querySelectorAll(".lb-tab").forEach(function (b) {
    b.addEventListener("click", function () {
      group = b.getAttribute("data-g");
      document.querySelectorAll(".lb-tab").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      render();
    });
  });
  document.querySelectorAll(".rk-kinds input").forEach(function (c) { c.addEventListener("change", function () { kinds[c.value] = c.checked; render(); }); });
  $("lb-q").addEventListener("input", function () { query = this.value.trim().toLowerCase(); redraw(); });
  window.addEventListener("resize", function () { speed(current); });
  var h0 = decodeURIComponent((location.hash || "").slice(1));
  if (h0 && D.groups.some(function (g) { return g[0] === h0; })) {
    group = h0;
    document.querySelectorAll(".lb-tab").forEach(function (o) { o.setAttribute("aria-pressed", o.getAttribute("data-g") === h0 ? "true" : "false"); });
  }
  $("rk-legend").innerHTML = R.bands.map(function (b) { return '<span><i class="' + b[1] + '"></i>' + esc(b[2]) + "</span>"; }).join("") + '<span><i class="rk-none"></i>not run</span>';
  render();
})();
