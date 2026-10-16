// In-browser results check. Mirrors benchmark1d2d's scorer for the checks it
// supports: on grids (L1/L2/Linf norms, mass, flood front, observed order), on
// networks (node and link values against the exact answer) and on exact states
// (a probe's depth, an exchange flow or a volume account at a time, and the
// water balance). Files are read locally and never leave the browser.
(function () {
  var sel = document.getElementById("case"), input = document.getElementById("files"),
      drop = document.getElementById("drop"), report = document.getElementById("report");
  if (!sel || !input) return;
  var cache = {};
  var IDX = JSON.parse((document.getElementById("sc-index") || { textContent: '{"tests":[]}' }).textContent);
  var BY = {}; IDX.tests.forEach(function (t) { BY[t.sid] = t; });
  var last = null;  // the files last checked: [{name, text, level}] and the test
  function kb(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB"; }
  function showTest() {
    var t = BY[sel.value]; if (!t) return;
    var dl = document.getElementById("sc-dl"), pg = document.getElementById("sc-page"), q = document.getElementById("sc-q"), st = document.getElementById("sc-setup");
    if (dl) { dl.href = t.zip; dl.innerHTML = "Download the test <span class=\"nv-kb\">.zip · " + kb(t.bytes) + "</span>"; }
    if (pg) pg.href = "tests/" + t.sid + ".html";
    if (q) q.textContent = t.question + (t.check ? "" : " (Scored by the bot when you publish: the in-browser check does not cover this test yet.)");
    if (st) st.innerHTML = t.setup || "<p>See START_HERE.md in the download.</p>";
    report.innerHTML = ""; last = null;
    var pub = document.getElementById("sc-publish"); if (pub) pub.hidden = true;
    try { history.replaceState(null, "", "#" + t.sid); } catch (e) { /* ignore */ }
  }
  sel.addEventListener("change", showTest);
  window.addEventListener("hashchange", function () {
    var h = location.hash.replace("#", "");
    if (h && h !== sel.value && sel.querySelector('option[value="' + h + '"]')) { sel.value = h; showTest(); }
  });
  function getJSON(url) {
    if (!cache[url]) cache[url] = fetch(url).then(function (r) { if (!r.ok) throw new Error(url + ": " + r.status); return r.json(); });
    return cache[url];
  }
  var hash = location.hash.replace("#", "");
  if (hash && sel.querySelector('option[value="' + hash + '"]')) sel.value = hash;
  showTest();

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function nice(v, sig) {
    sig = sig || 2; if (v === null || !isFinite(v)) return "n/a";
    var a = Math.abs(v); if (a === 0) return "0"; if (a < 1e-4) return "< 0.0001"; if (a >= 100) return Math.round(v).toLocaleString();
    var d = Math.max(sig - 1 - Math.floor(Math.log10(a)), 0); return String(+v.toFixed(d));
  }
  function units(v, u) {
    u = (u || "").trim();
    if (u === "m") { var a = Math.abs(v); return a < 0.01 ? nice(v * 1000) + " mm" : a < 1 ? nice(v * 100) + " cm" : nice(v, 3) + " m"; }
    if (u === "%") return nice(v) + " %";
    return nice(v, 3) + (u && u !== "1" ? " " + u : "");
  }

  // Column names as people write them, mapped to the results contract (mirrors io/results.py ALIASES).
  var ALIAS = { time: "t", time_s: "t", depth: "h", water_depth: "h", velocity: "u", u_velocity: "u", x_velocity: "u", v_velocity: "v",
    y_velocity: "v", pressure: "p", flow: "Q", discharge: "Q", q: "Q", concentration: "c", bed: "z", bed_level: "z", bed_elevation: "z",
    invert: "z", volume: "V", id: "element_id", element: "element_id", name: "element_id", node: "element_id", type: "element_type" };
  var KNOWN = { t: 1, x: 1, y: 1, h: 1, u: 1, v: 1, p: 1, Q: 1, c: 1, z: 1, V: 1, element_id: 1, element_type: 1 };
  function colName(h) {
    h = h.trim().replace(/^"|"$/g, "");
    if (KNOWN[h]) return h;
    var k = h.replace(/\s*[\(\[].*?[\)\]]\s*/g, "").trim().toLowerCase().replace(/\s+/g, "_");
    if (KNOWN[k]) return k;
    return ALIAS[k] || null;
  }
  function parseCSV(text) {
    var lines = text.replace(/\r/g, "").split("\n").filter(function (l) { return l.trim().length; });
    if (!lines.length) throw new Error("the file is empty");
    var first = lines[0], sep = first.indexOf("\t") >= 0 ? "\t" : (first.indexOf(";") >= 0 && first.indexOf(",") < 0 ? ";" : ",");
    var raw = first.split(sep), head = raw.map(colName);
    var cols = {}, STR = { element_id: 1, element_type: 1 }, used = {};
    head.forEach(function (h, i) { if (h && !used[h]) { used[h] = 1; cols[h] = []; } else head[i] = null; });
    for (var r = 1; r < lines.length; r++) {
      var f = lines[r].split(sep);
      head.forEach(function (h, i) {
        if (!h) return;
        var v = f[i] === undefined ? "" : f[i].trim().replace(/^"|"$/g, "");
        if (!STR[h] && sep === ";" && /^-?\d+,\d+$/.test(v)) v = v.replace(",", ".");  // decimal commas
        cols[h].push(STR[h] ? v : (v === "" ? NaN : parseFloat(v)));
      });
    }
    if (!cols.x && !cols.element_id) throw new Error("no x column (or element ids): keep the positions from the results sheet");
    cols._ignored = raw.filter(function (h, i) { return !head[i]; }).map(function (h) { return h.trim(); }).filter(Boolean);
    return cols;
  }

  // Final time slice, as the scorer does.
  function finalSlice(c) {
    if (!c.t) return c;
    var tmax = -Infinity; c.t.forEach(function (v) { if (isFinite(v) && v > tmax) tmax = v; });
    if (!isFinite(tmax)) return c;
    var keep = [];
    c.t.forEach(function (v, i) { if (Math.abs(v - tmax) <= 1e-8 * Math.max(1, Math.abs(tmax))) keep.push(i); });
    var out = {}; Object.keys(c).forEach(function (k) { out[k] = keep.map(function (i) { return c[k][i]; }); });
    out._t = tmax; return out;
  }

  function pickLevel(meta, cols) {
    var n = cols.x.length, best = null;
    meta.levels.forEach(function (lv) { if (lv.n === n) best = lv; });
    if (best) return best;
    var xs = cols.x.slice().filter(isFinite).sort(function (a, b) { return a - b; }), d = [];
    for (var i = 1; i < xs.length; i++) if (xs[i] - xs[i - 1] > 1e-9) d.push(xs[i] - xs[i - 1]);
    d.sort(function (a, b) { return a - b; });
    var dx = d.length ? d[Math.floor(d.length / 2)] : 0;
    meta.levels.forEach(function (lv) { if (Math.abs(lv.dx - dx) < 0.01 * lv.dx) best = lv; });
    return best;
  }

  function align(meta, lvData, cols) {
    var dx = lvData._dx, key = function (x, y) { return Math.round(x / dx * 1000) + "," + (y === null || y === undefined || !isFinite(y) ? "" : Math.round(y / dx * 1000)); };
    var idx = {};
    for (var i = 0; i < cols.x.length; i++) idx[key(cols.x[i], meta.is2d && cols.y ? cols.y[i] : null)] = i;
    var order = [], missing = 0;
    for (var j = 0; j < lvData.x.length; j++) {
      var k = key(lvData.x[j], lvData.y ? lvData.y[j] : null);
      if (idx[k] === undefined) missing++; else order.push([j, idx[k]]);
    }
    if (missing) throw new Error(missing + " of " + lvData.x.length + " report points are missing; use the template for this grid size");
    return order;
  }

  function norm(name, err) {
    var s = 0, m = 0;
    if (name === "Linf") { err.forEach(function (e) { m = Math.max(m, Math.abs(e)); }); return m; }
    if (name === "L2") { err.forEach(function (e) { s += e * e; }); return Math.sqrt(s / err.length); }
    err.forEach(function (e) { s += Math.abs(e); }); return s / err.length;
  }
  function pass(v, thr) {
    var x = +thr.value;
    if (thr.op === "abs<=") return Math.abs(v) <= x;
    if (thr.op === "<=") return v <= x;
    if (thr.op === ">=") return v >= x;
    return v === x;
  }

  function evaluate(meta, lvData, cols, order) {
    var get = function (v) { return order.map(function (p) { return cols[v] ? cols[v][p[1]] : NaN; }); };
    var ref = function (v) { return order.map(function (p) { return lvData.ref[v] ? lvData.ref[v][p[0]] : null; }); };
    var out = [];
    meta.criteria.forEach(function (c) {
      var r = { label: c.label, threshold: c.threshold, gating: c.gating, supported: c.supported };
      if (!c.supported) { out.push(r); return; }
      try {
        if (c.metric === "L1" || c.metric === "L2" || c.metric === "Linf") {
          var s = get(c.variable), f = ref(c.variable), e = [], z = [];
          for (var i = 0; i < s.length; i++) { if (f[i] === null) continue; if (!isFinite(s[i])) throw new Error("missing " + c.variable + " values"); e.push(s[i] - f[i]); z.push(f[i]); }
          var v = norm(c.metric, e);
          if ((c.threshold.units || "").trim() === "%") v = 100 * v / Math.max(norm(c.metric, z), 1e-300);
          r.value = v;
        } else if (c.metric === "global_mass_error") {
          var q = (c.variable !== "volume" && c.variable !== "h" && cols[c.variable]) ? c.variable : "h";
          var ss = 0, rr = 0, sv = get(q), rv = ref(q);
          for (var k = 0; k < sv.length; k++) { if (!isFinite(sv[k])) throw new Error("missing " + q + " values"); ss += sv[k]; rr += (rv[k] === null ? sv[k] : rv[k]); }
          r.value = 100 * (ss - rr) / rr;
        } else if (c.metric === "front_position_error") {
          var hx = get("h"), xx = order.map(function (p) { return lvData.x[p[0]]; }), det = -Infinity;
          for (var m = 0; m < hx.length; m++) if (hx[m] >= meta.front.thresh) det = Math.max(det, xx[m]);
          if (!isFinite(det)) throw new Error("no wet cells");
          r.value = Math.abs(det - meta.front.exact);
        } else if (c.metric === "volume_front_error") {
          r.value = volumeFront(order.map(function (p) { return lvData.x[p[0]]; }), get("h"), meta.vfront.fraction, meta.vfront.x0) - meta.vfront.exact;
        }
        r.ok = pass(r.value, c.threshold);
      } catch (err) { r.error = err.message; r.ok = false; }
      out.push(r);
    });
    return out;
  }

  // Mirrors benchmark1d2d.metrics.volume_front_position: the abscissa beyond
  // which lies `frac` of the water downstream of x0 (rows at one x averaged).
  function volumeFront(xs, hs, frac, x0) {
    var acc = {};
    for (var i = 0; i < xs.length; i++) {
      if (!isFinite(xs[i])) continue;
      var hv = isFinite(hs[i]) ? Math.max(hs[i], 0) : 0, a = acc[xs[i]] || (acc[xs[i]] = [0, 0]);
      a[0] += hv; a[1] += 1;
    }
    var x = Object.keys(acc).map(Number).sort(function (a, b) { return a - b; });
    var h = x.map(function (v) { return acc[v][0] / acc[v][1]; }), n = x.length;
    if (n < 2) throw new Error("need at least two report points");
    var lo = [], w = [], vol = [];
    for (var k = 0; k < n; k++) {
      var l = k === 0 ? x[0] - (0.5 * (x[1] + x[0]) - x[0]) : 0.5 * (x[k] + x[k - 1]);
      var r = k === n - 1 ? x[n - 1] + (x[n - 1] - 0.5 * (x[n - 1] + x[n - 2])) : 0.5 * (x[k] + x[k + 1]);
      l = Math.max(l, x0); lo.push(l); w.push(Math.max(r - l, 0)); vol.push(h[k] * w[k]);
    }
    var tail = new Array(n), sum = 0;
    for (var j = n - 1; j >= 0; j--) { sum += vol[j]; tail[j] = sum; }
    if (!(tail[0] > 0)) return x0;  // no water has crossed: the front is still at the dam
    var target = frac * tail[0], q = 0;
    while (q < n && tail[q] > target) q++;
    if (q === 0) return lo[0];
    var hiT = tail[q - 1], loT = q < n ? tail[q] : 0;
    return lo[q - 1] + w[q - 1] * (hiT - target) / Math.max(hiT - loT, 1e-300);
  }

  function convError(meta, lvData, cols, order) {
    var v = meta.conv.variable, e = [];
    order.forEach(function (p) { var f = lvData.ref[v] ? lvData.ref[v][p[0]] : null; if (f !== null) e.push(cols[v][p[1]] - f); });
    return norm(meta.conv.norm, e);
  }
  function observedOrder(sp, er) {
    var o = [];
    for (var i = 0; i < er.length - 1; i++) o.push(Math.log(Math.abs(er[i + 1]) / Math.abs(er[i])) / Math.log(sp[i + 1] / sp[i]));
    if (er.length >= 3) {
      var r12 = sp[1] / sp[0], r23 = sp[2] / sp[1];
      if (Math.abs(r12 - r23) / Math.max(r12, r23) < 1e-9) return (o[0] + o[1]) / 2;
    }
    return o.reduce(function (a, b) { return a + b; }, 0) / o.length;
  }

  // Scoring method 2 (docs/methodology/scoring_v2.md): the order fitted through every grid, with its 90 % range.
  var T90 = { 1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895, 8: 1.860, 9: 1.833, 10: 1.812 };
  function fitOrder(sp, er) {
    var pts = [];
    for (var i = 0; i < er.length; i++) if (er[i] && sp[i] > 0) pts.push([Math.log(sp[i]), Math.log(Math.abs(er[i]))]);
    var n = pts.length;
    if (n < 2) return { p: null, ci: null, n: n };
    var mx = 0, my = 0; pts.forEach(function (q) { mx += q[0] / n; my += q[1] / n; });
    var sxx = 0, sxy = 0; pts.forEach(function (q) { sxx += (q[0] - mx) * (q[0] - mx); sxy += (q[0] - mx) * (q[1] - my); });
    if (!sxx) return { p: null, ci: null, n: n };
    var b = sxy / sxx;
    if (n === 2) return { p: b, ci: null, n: n };
    var ss = 0; pts.forEach(function (q) { var r = q[1] - (my + b * (q[0] - mx)); ss += r * r; });
    var se = Math.sqrt(ss / (n - 2) / sxx), t = T90[n - 2] || 1.645;
    return { p: b, ci: [b - t * se, b + t * se], n: n };
  }
  function judgeOrder(f, pmin) {
    if (f.p === null || !f.ci) return "inconclusive";
    if (f.ci[0] >= pmin) return "pass";
    if (f.ci[1] < pmin) return "fail";
    return "inconclusive";
  }

  function render(meta, results, conv) {
    var h = "";
    var finest = results[results.length - 1];
    var all = finest.checks.filter(function (c) { return c.supported && c.gating; });
    var acc = all.every(function (c) { return c.ok; });
    // scoring method 2.1: the result passes when every check is within its limit; how it converges is a separate verdict
    var v = acc ? "pass" : "fail";
    var sub = meta.mode === "grid" || !meta.mode ? "Finest file: grid " + esc(finest.level) + " · " + esc(finest.file) : "File: " + esc(finest.file);
    h += '<div class="card"><div class="head-row" style="margin-bottom:12px"><div><h2 style="margin:0">' + esc(meta.name) + '</h2><div class="muted">' + sub + "</div></div>" +
      ({ pass: '<span class="badge pass">✓ Passes these checks</span>', fail: '<span class="badge fail">✗ Fails at least one check</span>',
         inconclusive: '<span class="badge unsure">? Inconclusive</span>' })[v] + "</div>";
    h += '<div class="checks-grid">';
    finest.checks.forEach(function (c) {
      if (!c.supported) { h += '<div class="check"><div class="k">' + esc(c.label) + '</div><div class="v muted" style="font-size:15px">Checked by the command-line scorer</div></div>'; return; }
      var lim = (c.threshold.op === ">=" ? "needed: at least " : "allowed: ") + units(+c.threshold.value, c.threshold.units);
      var val = c.error ? esc(c.error) : units(Math.abs(c.value), c.threshold.units);
      h += '<div class="check' + (c.ok ? "" : " bad") + '"><div class="k">' + esc(c.label) + '</div><div class="v">' + (c.ok ? "✓ " : "✗ ") + val + '</div><div class="lim">' + lim + "</div></div>";
    });
    if (conv) {
      var cls = { pass: "", fail: " bad", inconclusive: " unsure" }[conv.v], sym = { pass: "✓ ", fail: "✗ ", inconclusive: "? " }[conv.v];
      var txt = conv.p === null ? "needs 3+ grids" : ("rate " + conv.p.toFixed(2) + (conv.ci ? " (90 % range " + conv.ci[0].toFixed(2) + " to " + conv.ci[1].toFixed(2) + ")" : "")).replace(/-/g, "−");
      h += '<div class="check' + cls + '"><div class="k">Improves with finer grids</div><div class="v">' + sym + txt +
        '</div><div class="lim">needed: ' + nice(meta.conv.min_observed_order, 2) + " or better across the whole range</div></div>";
    }
    h += "</div>";
    if (meta.mode === "elements" || meta.mode === "states") {
      // one file per test: no grids
    } else if (results.length > 1) {
      h += '<div class="table-scroll" style="margin-top:16px"><table class="data"><thead><tr><th>Grid</th><th>File</th><th class="num">' + esc(meta.conv ? meta.conv.norm + " error in " + meta.conv.variable : "") + "</th></tr></thead><tbody>";
      results.forEach(function (r) { h += "<tr><td>" + esc(r.level) + "</td><td>" + esc(r.file) + '</td><td class="num">' + (r.convErr === undefined ? "–" : r.convErr.toPrecision(4)) + "</td></tr>"; });
      h += "</tbody></table></div>";
    } else if (meta.conv) {
      h += '<p class="small" style="margin-top:14px">Drop one file for each of the ' + meta.levels.length + " grid sizes (" + meta.levels.map(function (l) { return l.name; }).join(", ") + ") to measure how fast your error shrinks.</p>";
    }
    h += '<p class="small" style="margin:14px 0 0">A check in your browser with the same formulas as the scorer. Publish it below to get the official, signed score on the site.</p></div>';
    report.innerHTML = h;
  }

  // ── networks: node and link values against the exact answer ──────────────
  function checkElements(meta, name, cols) {
    if (!cols.element_id) throw new Error("no element_id column: list every node and link, as in the template");
    var row = {};
    for (var i = 0; i < cols.element_id.length; i++) row[(cols.element_type ? cols.element_type[i] : "") + "|" + cols.element_id[i]] = i;
    var checks = meta.criteria.map(function (c) {
      var r = { label: c.label, threshold: c.threshold, gating: c.gating, supported: c.supported };
      if (!c.supported) return r;
      try {
        var refv = meta.ref[c.variable] || [], e = [], z = [], missing = [];
        meta.elements.forEach(function (el, k) {
          var f = refv[k]; if (f === null || f === undefined) return;
          var j = row[el[0] + "|" + el[1]];
          if (j === undefined || !isFinite(cols[c.variable] ? cols[c.variable][j] : NaN)) { missing.push(el[0] + " " + el[1]); return; }
          e.push(cols[c.variable][j] - f); z.push(f);
        });
        if (missing.length) throw new Error("no " + c.variable + " for " + missing.length + " element(s), e.g. " + missing[0]);
        var v = norm(c.metric, e);
        if ((c.threshold.units || "").trim() === "%") v = 100 * v / Math.max(norm(c.metric, z), 1e-300);
        r.value = v; r.ok = pass(v, c.threshold);
      } catch (err) { r.error = err.message; r.ok = false; }
      return r;
    });
    return [{ level: "network", dx: 0, file: name, checks: checks }];
  }

  // ── exact states and the water balance (coupled tests) ───────────────────
  function rowsWhere(cols, pred) { var out = []; for (var i = 0; i < cols.t.length; i++) if (pred(i)) out.push(i); return out; }
  function seriesOf(cols, idx, v) {
    var pts = idx.map(function (i) { return [cols.t[i], cols[v] ? cols[v][i] : NaN]; }).filter(function (p) { return isFinite(p[0]); });
    pts.sort(function (a, b) { return a[0] - b[0]; });
    return pts;
  }
  function interpAt(pts, t) {
    if (!pts.length) throw new Error("no rows");
    if (t <= pts[0][0]) return pts[0][1];
    for (var i = 1; i < pts.length; i++) if (t <= pts[i][0]) { var f = (t - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0] || 1); return pts[i - 1][1] + f * (pts[i][1] - pts[i - 1][1]); }
    return pts[pts.length - 1][1];
  }
  function stateValue(meta, st, cols) {
    var hasT = st.time !== undefined && st.time !== null;
    if (st.element) {
      var idx = rowsWhere(cols, function (i) {
        var typ = cols.element_type ? cols.element_type[i] : "";
        return cols.element_id && cols.element_id[i] === st.element && (st.variable === "V" ? typ === "account" : typ !== "account");
      });
      if (!idx.length) throw new Error("no rows for " + st.element);
      var pts = seriesOf(cols, idx, st.variable);
      return hasT ? interpAt(pts, st.time) : pts[pts.length - 1][1];
    }
    var worst = null;
    String(st.where || "").split(",").forEach(function (pid) {
      var pr = meta.probes.filter(function (p) { return p.id === pid.trim(); })[0];
      if (!pr) throw new Error("probe " + pid + " not in the test");
      var best = Infinity, bx = null, by = null;
      for (var i = 0; i < cols.t.length; i++) {
        if (!isFinite(cols.x[i]) || !cols.y || !isFinite(cols.y[i])) continue;
        var d = Math.pow(cols.x[i] - pr.x, 2) + Math.pow(cols.y[i] - (pr.y || 0), 2);
        if (d < best) { best = d; bx = cols.x[i]; by = cols.y[i]; }
      }
      if (bx === null) throw new Error("no rows with x and y for probe " + pid);
      var pts = seriesOf(cols, rowsWhere(cols, function (i) { return cols.x[i] === bx && cols.y[i] === by; }), "h");
      var v = hasT ? interpAt(pts, st.time) : Math.max.apply(null, pts.map(function (p) { return p[1]; }));
      if (worst === null || Math.abs(v - st.value) > Math.abs(worst - st.value)) worst = v;
    });
    return worst;
  }
  function balance(cols) {
    if (!cols.V || !cols.element_type) throw new Error("no volume accounts: add element_type 'account' rows with column V");
    var acc = {};
    ["surface", "network", "inflow", "outflow"].forEach(function (a) {
      acc[a] = seriesOf(cols, rowsWhere(cols, function (i) { return cols.element_type[i] === "account" && cols.element_id[i] === a; }), "V");
    });
    if (!acc.surface.length || !acc.network.length) throw new Error("the surface and network accounts are needed");
    var t = acc.surface.map(function (p) { return p[0]; });
    var at = function (a, tt) { return acc[a].length ? interpAt(acc[a], tt) : 0; };
    var s0 = at("surface", t[0]) + at("network", t[0]), i0 = at("inflow", t[0]), o0 = at("outflow", t[0]), tn = t[t.length - 1];
    var imb = at("surface", tn) + at("network", tn) - s0 - (at("inflow", tn) - i0) + (at("outflow", tn) - o0);
    var scale = Math.max(at("inflow", tn) - i0, s0, 1e-12);
    return 100 * imb / scale;
  }
  function checkStates(meta, name, cols) {
    if (!cols.t) throw new Error("no t column");
    var states = {}; meta.states.forEach(function (s) { states[s.id] = s; });
    var checks = meta.criteria.map(function (c) {
      var r = { label: c.label, threshold: c.threshold, gating: c.gating, supported: c.supported };
      if (!c.supported) return r;
      try {
        if (c.metric === "continuity_error") r.value = balance(cols);
        else {
          var st = states[c.against], got = stateValue(meta, st, cols);
          r.value = (c.threshold.units || "").trim() === "%" ? 100 * (got - st.value) / st.value : got - st.value;
        }
        r.ok = pass(r.value, c.threshold);
      } catch (err) { r.error = err.message; r.ok = false; }
      return r;
    });
    return [{ level: "states", dx: 0, file: name, checks: checks }];
  }

  function run(files) {
    var sid = sel.value;
    report.innerHTML = '<div class="card">Checking…</div>';
    files = Array.prototype.slice.call(files);
    Promise.all(files.map(function (f) { return f.text().then(function (t) { return { name: f.name, text: t }; }); })).then(function (read) {
      last = { sid: sid, files: read, levels: {} };
      var pub = document.getElementById("sc-publish"); if (pub) pub.hidden = false;
      var sent = document.getElementById("sc-sent"); if (sent) sent.hidden = true;
      var mem = read.map(function (r) { return { name: r.name, text: function () { return Promise.resolve(r.text); } }; });
      if (!BY[sid] || !BY[sid].check) uncheckedSummary(sid, mem); else score(sid, mem);
    });
  }
  function score(sid, files) {
    getJSON("data/check/" + sid + ".json").then(function (meta) {
      if (meta.mode === "elements" || meta.mode === "states") {
        var f = files[0];
        return f.text().then(function (t) {
          var cols = parseCSV(t);
          var res = meta.mode === "elements" ? checkElements(meta, f.name, finalSlice(cols)) : checkStates(meta, f.name, cols);
          render(meta, res, null);
        });
      }
      return Promise.all(files.map(function (f) { return f.text().then(function (t) { return { name: f.name, cols: finalSlice(parseCSV(t)) }; }); }))
        .then(function (parsed) {
          return Promise.all(parsed.map(function (p) {
            var lv = pickLevel(meta, p.cols);
            if (!lv) throw new Error(p.name + ": " + p.cols.x.length + " rows does not match any grid size of this test (" + meta.levels.map(function (l) { return l.name + ": " + l.n + " points"; }).join(", ") + ")");
            if (Math.abs(p.cols._t - meta.t_end) > 1e-6 * Math.max(1, meta.t_end)) throw new Error(p.name + ": results are at t = " + p.cols._t + " s; this test is compared at t = " + meta.t_end + " s");
            if (last) last.levels[p.name] = lv.name;
            return getJSON("data/check/" + sid + "_dx" + lv.name + ".json").then(function (d) {
              d._dx = lv.dx; var order = align(meta, d, p.cols);
              var res = { level: lv.name, dx: lv.dx, file: p.name, checks: evaluate(meta, d, p.cols, order) };
              if (meta.conv) res.convErr = convError(meta, d, p.cols, order);
              return res;
            });
          }));
        })
        .then(function (results) {
          results.sort(function (a, b) { return b.dx - a.dx; });
          var conv = null;
          if (meta.conv) {
            var uniq = {}; results.forEach(function (r) { uniq[r.dx] = r; });
            var lv = Object.keys(uniq).map(Number).sort(function (a, b) { return a - b; });
            if (lv.length >= 2) {
              var er = lv.map(function (d) { return uniq[d].convErr; });
              if (er.every(function (e) { return Math.abs(e) < 1e-12; })) conv = { p: null, ci: null, v: "fail" };
              else { var f = fitOrder(lv, er); conv = { p: f.p, ci: f.ci, v: judgeOrder(f, meta.conv.min_observed_order) }; }
            }
          }
          render(meta, results, conv);
        });
    }).catch(function (err) {
      report.innerHTML = '<div class="callout warn"><b>Could not check this file.</b> ' + esc(err.message) + "</div>";
    });
  }
  // Tests the browser cannot check yet: read the files, say what was found, and let them be published.
  function uncheckedSummary(sid, files) {
    Promise.all(files.map(function (f) { return f.text().then(function (t) { var c = parseCSV(t); return { name: f.name, rows: (c.x || c.element_id).length, cols: Object.keys(c).filter(function (k) { return k[0] !== "_"; }) }; }); }))
      .then(function (got) {
        var h = '<div class="card"><h2 style="margin:0 0 6px">' + esc(BY[sid].name) + '</h2><p>Your files read cleanly. This test is scored by the full scorer, which runs when you publish: you get the scores as a reply within minutes, before anything goes on the site.</p><ul class="small">';
        got.forEach(function (g) { h += "<li><b>" + esc(g.name) + "</b>: " + g.rows + " rows; columns " + esc(g.cols.join(", ")) + "</li>"; });
        report.innerHTML = h + "</ul></div>";
      }).catch(function (err) { report.innerHTML = '<div class="callout warn"><b>Could not read this file.</b> ' + esc(err.message) + "</div>"; });
  }

  // ── publishing: one zip and a pre-filled GitHub form ─────────────────────
  var form = document.getElementById("sc-form");
  if (form) form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!last || !window.JSZip) return;
    var t = BY[last.sid], f = new FormData(form), get = function (k) { return String(f.get(k) || "").trim(); };
    var z = new JSZip(), names = [];
    var ordered = last.files.slice().sort(function (a, b) { return (parseFloat(last.levels[b.name]) || 0) - (parseFloat(last.levels[a.name]) || 0); });
    ordered.forEach(function (file) {
      var lv = last.levels[file.name], ext = (file.name.match(/\.[A-Za-z]+$/) || [".csv"])[0].toLowerCase();
      var name = lv ? t.sid + "_dx" + lv + ext : (ordered.length === 1 ? t.sid + ext : file.name.replace(/[^\w.\-]/g, "_"));
      names.push(name); z.file(name, file.text);
    });
    var sub = { schema_version: "1.0.0", solver: { name: get("software"), version: get("version"), options: get("settings") }, submitted_by: get("org"),
      date: new Date().toISOString().slice(0, 10), results_licence: get("licence"), cases: [{ test_id: t.sid, case_version: t.version, results: names }] };
    z.file("submission.json", JSON.stringify(sub, null, 2));
    var slug = (get("software") + "-" + t.sid).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    z.generateAsync({ type: "blob" }).then(function (blob) {
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = slug + ".zip"; document.body.appendChild(a); a.click(); a.remove();
      var q = new URLSearchParams({ template: "submit-results.yml", title: "Results: " + get("software") + " " + get("version") + " on " + t.sid,
        software: get("software"), version: get("version"), organisation: get("org"), tests: t.sid, settings: get("settings"),
        licence: get("licence") === "CC0-1.0" ? "CC0 (no conditions)" : "CC BY 4.0 (credit to you)" });
      var url = IDX.repo + "/issues/new?" + q.toString();
      var sent = document.getElementById("sc-sent");
      sent.innerHTML = "<b>Almost done.</b> <b>" + esc(slug) + ".zip</b> has downloaded. <a href=\"" + esc(url) + "\" target=\"_blank\" rel=\"noopener\">Open the GitHub form</a> (it opens filled in), drag the zip into its <b>Files</b> box and press <b>Submit</b>. A free GitHub account is needed; the bot replies with your scores within minutes.";
      sent.hidden = false;
      window.open(url, "_blank", "noopener");
    });
  });

  input.addEventListener("change", function () { if (input.files.length) run(input.files); });
  if (drop) {
    ["dragenter", "dragover"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("over"); }); });
    ["dragleave", "drop"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("over"); }); });
    drop.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) run(e.dataTransfer.files); });
  }
  window.__benchCheck = { parseCSV: parseCSV, finalSlice: finalSlice, pickLevel: pickLevel, align: align, evaluate: evaluate, convError: convError, observedOrder: observedOrder, fitOrder: fitOrder, judgeOrder: judgeOrder };
})();
