// Rankings: leaderboard, models × tests portrait and accuracy against run time, re-ranked in the browser for the
// chosen test group and model kinds with the rules of site/ranking.py. Data: #rk-data (site/rankpage.py).
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("rk-data").textContent);
  function $(id) { return document.getElementById(id); }
  var NS = "http://www.w3.org/2000/svg";
  var R = D.rules, group = "", kinds = {};
  document.querySelectorAll(".rk-kinds input").forEach(function (c) { kinds[c.value] = c.checked; });

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function short(s) {
    if (s === null || s === undefined) return "–";
    if (!isFinite(s) || s >= 1e12) return "∞";
    if (s < 0.01) return "<1 %";
    if (s < 1) return Math.round(s * 100) + " %";
    if (s < 10) return s.toFixed(1) + "×";
    if (s < 1e4) return Math.round(s) + "×";
    return s.toExponential(0).replace("e+", "e") + "×";
  }
  function klass(s) {
    if (s === null || s === undefined) return "sn";
    return s < 0.1 ? "s0" : s < 0.5 ? "s1" : s < 1 ? "s2" : s < 2 ? "s3" : s < 10 ? "s4" : "s5";
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
  function name(k) { var m = D.models[k]; return m.name + (m.sub ? " · " + m.sub : ""); }

  function shown(k) { var m = D.models[k]; return m && kinds[m.kind]; }
  function testsShown() { return D.tests.filter(function (t) { return !group || t.group === group; }); }
  function byTest() {  // sid -> [{key, score, time, machine}]
    var out = {};
    D.results.forEach(function (r) {
      if (!shown(r[1])) return;
      (out[r[0]] = out[r[0]] || []).push({ key: r[1], score: r[2], time: r[3], machine: r[4] });
    });
    return out;
  }
  function overall(bt, tests) {
    var per = {};
    tests.forEach(function (t) {
      var rows = (bt[t.sid] || []).filter(function (r) { return r.score !== null; });
      if (!rows.length) return;
      var med = median(rows.map(function (r) { return r.score; }).filter(isFinite)) || 1;
      rows.forEach(function (r) {
        var p = per[r.key] = per[r.key] || { key: r.key, tests: 0, wins: 0, comps: 0, rel: [], scores: [], times: [] };
        p.tests++; p.scores.push(r.score);
        p.rel.push(Math.max(r.score, R.tie_floor) / Math.max(med, R.tie_floor));
        if (r.time !== null && r.time !== undefined) p.times.push(r.time);
        rows.forEach(function (o) {
          if (o === r) return;
          p.comps++;
          if (tied(r.score, o.score)) p.wins += 0.5; else if (r.score < o.score) p.wins += 1;
        });
      });
    });
    var out = Object.keys(per).map(function (k) {
      var p = per[k];
      return { key: k, tests: p.tests, comps: p.comps, win: p.comps ? p.wins / p.comps : null,
               field: p.rel.length ? Math.exp(p.rel.reduce(function (a, v) { return a + Math.log(v); }, 0) / p.rel.length) : null,
               med: median(p.scores), time: median(p.times), timed: p.times.length };
    });
    var ranked = out.filter(function (r) { return r.tests >= R.min_tests && r.win !== null; })
      .sort(function (a, b) { return b.win - a.win || (a.field || 1e9) - (b.field || 1e9); });
    ranked.forEach(function (r) { r.rank = 1 + ranked.filter(function (o) { return o.win > r.win + 0.02; }).length; });
    var rest = out.filter(function (r) { return ranked.indexOf(r) < 0; }).sort(function (a, b) { return (b.win || 0) - (a.win || 0) || b.tests - a.tests; });
    rest.forEach(function (r) { r.rank = null; });
    return ranked.concat(rest);
  }

  function board(rows, nTests) {
    var tb = document.querySelector("#rk-board tbody"), h = "";
    rows.forEach(function (r) {
      var m = D.models[r.key];
      h += "<tr" + (r.rank ? "" : ' class="rk-unranked"') + '><td class="num"><b>' + (r.rank ? r.rank : "–") + "</b></td>" +
        '<td><a href="solvers/' + esc(r.key) + '.html"><span class="sw" style="background:' + esc(m.color) + '"></span><b>' + esc(m.name) + '</b> <span class="muted">' + esc(m.sub) + "</span></a></td>" +
        '<td><div class="rk-bar"><i style="width:' + (r.win === null ? 0 : (100 * r.win).toFixed(1)) + '%"></i><span>' + (r.win === null ? "–" : Math.round(100 * r.win) + " %") + '</span></div><span class="muted small">' + r.comps + " comparisons</span></td>" +
        '<td class="num">' + (r.field === null ? "–" : r.field < 0.1 ? r.field.toFixed(2) + "×" : r.field.toFixed(1) + "×") + "</td>" +
        '<td class="num">' + r.tests + "</td>" +
        '<td class="num"><span class="score ' + klass(r.med) + '">' + short(r.med) + "</span></td>" +
        '<td class="num">' + time(r.time) + (r.timed && r.timed < r.tests ? '<div class="muted small">' + r.timed + " of " + r.tests + " timed</div>" : "") + "</td></tr>";
    });
    tb.innerHTML = h || '<tr><td colspan="7">No results for this choice.</td></tr>';
    var nr = rows.filter(function (r) { return r.rank; }).length;
    $("rk-board-note").textContent = nr + " model" + (nr === 1 ? "" : "s") + " ranked over " + nTests + " test" + (nTests === 1 ? "" : "s") +
      ". Models with fewer than " + R.min_tests + " tests in this view are listed below the ranked ones, without a rank.";
  }

  function portrait(rows, tests, bt) {
    var t = $("rk-portrait"), h = '<thead><tr><th scope="col" class="rk-corner">Model</th>';
    var cols = tests.filter(function (x) { return (bt[x.sid] || []).length; });
    var gname = {}; D.groups.forEach(function (g) { gname[g[0]] = g[1]; });
    cols.forEach(function (x) { h += '<th scope="col" title="' + esc(x.name + " · " + gname[x.group]) + '"><a href="tests/' + esc(x.sid) + '.html"><span>' + esc(x.sid) + "</span></a></th>"; });
    h += "</tr></thead><tbody>";
    rows.forEach(function (r) {
      var m = D.models[r.key];
      h += '<tr><th scope="row"><span class="sw" style="background:' + esc(m.color) + '"></span>' + esc(m.name) + ' <span class="muted">' + esc(m.sub) + "</span></th>";
      cols.forEach(function (x) {
        var res = (bt[x.sid] || []).filter(function (q) { return q.key === r.key; })[0];
        if (!res) { h += '<td class="rk-none"></td>'; return; }
        h += '<td class="' + klass(res.score) + '"><a href="tests/' + esc(x.sid) + ".html#m-" + esc(r.key) + '" title="' + esc(x.name + " · " + name(r.key) + ": " + short(res.score)) + '">' + short(res.score) + "</a></td>";
      });
      h += "</tr>";
    });
    t.innerHTML = h + "</tbody>";
  }

  function speedPick(tests, bt) {
    var sel = $("rk-test"), keep = sel.value;
    var withTime = tests.filter(function (x) { return (bt[x.sid] || []).some(function (r) { return r.time !== null && r.time !== undefined && r.score !== null; }); });
    sel.innerHTML = withTime.map(function (x) { return '<option value="' + esc(x.sid) + '">' + esc(x.sid + " · " + x.name) + "</option>"; }).join("");
    if (withTime.some(function (x) { return x.sid === keep; })) sel.value = keep;
    sel.disabled = !withTime.length;
    speed(bt);
  }
  function speed(bt) {
    var box = $("rk-speed"), sid = $("rk-test").value;
    var pts = (bt[sid] || []).filter(function (r) { return r.time !== null && r.time !== undefined && r.score !== null && isFinite(r.score); });
    if (!pts.length) { box.innerHTML = '<p class="muted small">No timed results in this view yet: run times are recorded by every run from 17 October 2026 and appear as the solver jobs re-run.</p>'; return; }
    var W = Math.max(320, box.clientWidth || 640), H = 320, L = 64, Rr = 16, T = 14, B = 44;
    var xs = pts.map(function (p) { return Math.log10(Math.max(p.time, 1e-3)); }), ys = pts.map(function (p) { return Math.log10(Math.max(p.score, 1e-3)); });
    var x0 = Math.floor(Math.min.apply(null, xs) - 0.2), x1 = Math.ceil(Math.max.apply(null, xs) + 0.2);
    var y0 = Math.floor(Math.min(Math.min.apply(null, ys), -1) - 0.1), y1 = Math.ceil(Math.max(Math.max.apply(null, ys), 0.3) + 0.1);
    function X(v) { return L + (v - x0) / (x1 - x0) * (W - L - Rr); }
    function Y(v) { return T + (y1 - v) / (y1 - y0) * (H - T - B); }
    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" class="rk-scatter" role="img" aria-label="Allowance used against run time">';
    for (var d = y0; d <= y1; d++) svg += '<line x1="' + L + '" x2="' + (W - Rr) + '" y1="' + Y(d) + '" y2="' + Y(d) + '" class="g"/><text x="' + (L - 6) + '" y="' + (Y(d) + 4) + '" text-anchor="end">' + short(Math.pow(10, d)) + "</text>";
    for (var e = x0; e <= x1; e++) svg += '<line y1="' + T + '" y2="' + (H - B) + '" x1="' + X(e) + '" x2="' + X(e) + '" class="g"/><text x="' + X(e) + '" y="' + (H - B + 16) + '" text-anchor="middle">' + time(Math.pow(10, e)) + "</text>";
    svg += '<line x1="' + L + '" x2="' + (W - Rr) + '" y1="' + Y(0) + '" y2="' + Y(0) + '" class="lim"/><text x="' + (W - Rr) + '" y="' + (Y(0) - 5) + '" text-anchor="end" class="lim-t">the allowance</text>';
    svg += '<text x="' + ((L + W - Rr) / 2) + '" y="' + (H - 6) + '" text-anchor="middle">wall time, finest grid (log)</text><text x="14" y="' + ((T + H - B) / 2) + '" text-anchor="middle" transform="rotate(-90 14 ' + ((T + H - B) / 2) + ')">allowance used (log)</text>';
    pts.forEach(function (p, i) {
      var m = D.models[p.key], cx = X(xs[i]), cy = Y(ys[i]);
      svg += '<g><circle cx="' + cx + '" cy="' + cy + '" r="6" fill="' + esc(m.color) + '" stroke="var(--sheet)" stroke-width="1.5"><title>' + esc(name(p.key) + ": " + short(p.score) + " in " + time(p.time) + (p.machine ? " on " + p.machine : "")) + "</title></circle>" +
        '<text x="' + (cx + 9) + '" y="' + (cy + 4) + '" class="pl">' + esc(m.name) + "</text></g>";
    });
    box.innerHTML = svg + "</svg>";
  }

  function legend() {
    $("rk-legend").innerHTML = [["s0", "under 10 %"], ["s1", "10–50 %"], ["s2", "50–100 %"], ["s3", "1–2×"], ["s4", "2–10×"], ["s5", "over 10×"], ["rk-none", "not run"]]
      .map(function (x) { return '<span><i class="' + x[0] + '"></i>' + x[1] + "</span>"; }).join("");
  }

  function render() {
    var tests = testsShown(), bt = byTest(), rows = overall(bt, tests);
    board(rows, tests.filter(function (x) { return (bt[x.sid] || []).length; }).length);
    portrait(rows, tests, bt);
    speedPick(tests, bt);
    try { history.replaceState(null, "", group ? "#" + group : location.pathname); } catch (e) { /* file:// */ }
  }
  document.querySelectorAll("[data-g]").forEach(function (b) {
    b.addEventListener("click", function () {
      group = b.getAttribute("data-g");
      document.querySelectorAll("[data-g]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      render();
    });
  });
  document.querySelectorAll(".rk-kinds input").forEach(function (c) { c.addEventListener("change", function () { kinds[c.value] = c.checked; render(); }); });
  $("rk-test").addEventListener("change", function () { speed(byTest()); });
  window.addEventListener("resize", function () { speed(byTest()); });
  var h = decodeURIComponent((location.hash || "").slice(1));
  if (h && D.groups.some(function (g) { return g[0] === h; })) {
    group = h;
    document.querySelectorAll("[data-g]").forEach(function (o) { o.setAttribute("aria-pressed", o.getAttribute("data-g") === h ? "true" : "false"); });
  }
  legend();
  render();
})();
