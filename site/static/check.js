// In-browser results check. Mirrors benchmark1d2d's scorer for the checks it
// supports (L1/L2/Linf norms, mass, flood front, observed order). Files are
// read locally and never leave the browser.
(function () {
  var sel = document.getElementById("case"), input = document.getElementById("files"),
      drop = document.getElementById("drop"), report = document.getElementById("report");
  if (!sel || !input) return;
  var cache = {};
  function getJSON(url) {
    if (!cache[url]) cache[url] = fetch(url).then(function (r) { if (!r.ok) throw new Error(url + ": " + r.status); return r.json(); });
    return cache[url];
  }
  var hash = location.hash.replace("#", "");
  if (hash && sel.querySelector('option[value="' + hash + '"]')) sel.value = hash;

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

  function parseCSV(text) {
    var lines = text.replace(/\r/g, "").split("\n").filter(function (l) { return l.trim().length; });
    if (!lines.length) throw new Error("the file is empty");
    var sep = lines[0].indexOf(";") >= 0 && lines[0].indexOf(",") < 0 ? ";" : ",";
    var head = lines[0].split(sep).map(function (h) { return h.trim().replace(/^"|"$/g, ""); });
    var cols = {}; head.forEach(function (h, i) { cols[h] = []; });
    for (var r = 1; r < lines.length; r++) {
      var f = lines[r].split(sep);
      head.forEach(function (h, i) { var v = f[i] === undefined ? "" : f[i].trim(); cols[h].push(v === "" ? NaN : parseFloat(v)); });
    }
    if (!cols.x) throw new Error("no x column");
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

  function render(meta, results, conv) {
    var h = "";
    var finest = results[results.length - 1];
    var all = finest.checks.filter(function (c) { return c.supported && c.gating; });
    var ok = all.every(function (c) { return c.ok; }) && (!conv || conv.ok !== false);
    h += '<div class="card"><div class="head-row" style="margin-bottom:12px"><div><h2 style="margin:0">' + esc(meta.name) + '</h2><div class="muted">Finest file: grid ' + esc(finest.level) + " · " + esc(finest.file) + "</div></div>" +
      (ok ? '<span class="badge pass">✓ Passes these checks</span>' : '<span class="badge fail">✗ Fails at least one check</span>') + "</div>";
    h += '<div class="checks-grid">';
    finest.checks.forEach(function (c) {
      if (!c.supported) { h += '<div class="check"><div class="k">' + esc(c.label) + '</div><div class="v muted" style="font-size:15px">Checked by the command-line scorer</div></div>'; return; }
      var lim = (c.threshold.op === ">=" ? "needed: at least " : "allowed: ") + units(+c.threshold.value, c.threshold.units);
      var val = c.error ? esc(c.error) : units(Math.abs(c.value), c.threshold.units);
      h += '<div class="check' + (c.ok ? "" : " bad") + '"><div class="k">' + esc(c.label) + '</div><div class="v">' + (c.ok ? "✓ " : "✗ ") + val + '</div><div class="lim">' + lim + "</div></div>";
    });
    if (conv) {
      h += '<div class="check' + (conv.ok ? "" : " bad") + '"><div class="k">Improves with finer grids</div><div class="v">' + (conv.ok ? "✓ " : "✗ ") +
        (conv.p === null ? "needs 2+ grids" : "rate " + nice(conv.p, 2)) + '</div><div class="lim">needed: ' + nice(meta.conv.min_observed_order, 2) + " or better</div></div>";
    }
    h += "</div>";
    if (results.length > 1) {
      h += '<div class="table-scroll" style="margin-top:16px"><table class="data"><thead><tr><th>Grid</th><th>File</th><th class="num">' + esc(meta.conv ? meta.conv.norm + " error in " + meta.conv.variable : "") + "</th></tr></thead><tbody>";
      results.forEach(function (r) { h += "<tr><td>" + esc(r.level) + "</td><td>" + esc(r.file) + '</td><td class="num">' + (r.convErr === undefined ? "–" : r.convErr.toPrecision(4)) + "</td></tr>"; });
      h += "</tbody></table></div>";
    } else if (meta.conv) {
      h += '<p class="small" style="margin-top:14px">Drop one file for each of the ' + meta.levels.length + " grid sizes (" + meta.levels.map(function (l) { return l.name; }).join(", ") + ") to measure how fast your error shrinks.</p>";
    }
    h += '<p class="small" style="margin:14px 0 0">A browser check, not a score card. For a signed result use the command-line scorer below.</p></div>';
    report.innerHTML = h;
  }

  function run(files) {
    var sid = sel.value;
    report.innerHTML = '<div class="card">Checking…</div>';
    getJSON("data/check/" + sid + ".json").then(function (meta) {
      return Promise.all(Array.prototype.map.call(files, function (f) { return f.text().then(function (t) { return { name: f.name, cols: finalSlice(parseCSV(t)) }; }); }))
        .then(function (parsed) {
          return Promise.all(parsed.map(function (p) {
            var lv = pickLevel(meta, p.cols);
            if (!lv) throw new Error(p.name + ": " + p.cols.x.length + " rows does not match any grid size of this test (" + meta.levels.map(function (l) { return l.name + ": " + l.n + " points"; }).join(", ") + ")");
            if (Math.abs(p.cols._t - meta.t_end) > 1e-6 * Math.max(1, meta.t_end)) throw new Error(p.name + ": results are at t = " + p.cols._t + " s; this test is compared at t = " + meta.t_end + " s");
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
              if (er.every(function (e) { return Math.abs(e) < 1e-12; })) conv = { p: null, ok: false };
              else { var p = observedOrder(lv, er); conv = { p: p, ok: p >= meta.conv.min_observed_order }; }
            }
          }
          render(meta, results, conv);
        });
    }).catch(function (err) {
      report.innerHTML = '<div class="callout warn"><b>Could not check this file.</b> ' + esc(err.message) + "</div>";
    });
  }
  input.addEventListener("change", function () { if (input.files.length) run(input.files); });
  if (drop) {
    ["dragenter", "dragover"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("over"); }); });
    ["dragleave", "drop"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("over"); }); });
    drop.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) run(e.dataTransfer.files); });
  }
  window.__benchCheck = { parseCSV: parseCSV, finalSlice: finalSlice, pickLevel: pickLevel, align: align, evaluate: evaluate, convError: convError, observedOrder: observedOrder };
})();
