// Mobile menu.
(function () {
  var btn = document.querySelector(".nav-toggle"), nav = document.getElementById("site-nav");
  if (!btn || !nav) return;
  btn.addEventListener("click", function () {
    var open = nav.classList.toggle("open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });
})();

// Copy buttons on code blocks and on [data-copy] elements (hashes, commands).
(function () {
  function copy(text, el) {
    function done() { var t = el.textContent; el.textContent = "Copied"; setTimeout(function () { el.textContent = t; }, 1200); }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {});
    }
  }
  document.querySelectorAll("pre").forEach(function (pre) {
    var text = pre.textContent;  // read before the button is added
    var b = document.createElement("button");
    b.type = "button"; b.className = "copy"; b.textContent = "Copy";
    b.addEventListener("click", function () { copy(text.replace(/\s+$/, ""), b); });
    pre.appendChild(b);
  });
  document.querySelectorAll("[data-copy]").forEach(function (el) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "copy inline"; b.textContent = "Copy";
    b.setAttribute("aria-label", "Copy " + (el.getAttribute("data-label") || "value"));
    b.addEventListener("click", function () { copy(el.getAttribute("data-copy"), b); });
    el.after(b);
  });
})();

// Filter for any table with data-filter="<input id>" rows carrying data-text.
(function () {
  document.querySelectorAll("table[data-filter]").forEach(function (table) {
    var q = document.getElementById(table.getAttribute("data-filter"));
    var sel = document.getElementById(table.getAttribute("data-filter") + "-result");
    var out = document.getElementById(table.getAttribute("data-filter") + "-count");
    var rows = Array.prototype.slice.call(table.tBodies[0].rows);
    function apply() {
      var text = q.value.trim().toLowerCase(), want = sel ? sel.value : "", n = 0;
      rows.forEach(function (r) {
        var ok = (!text || r.dataset.text.indexOf(text) !== -1) && (!want || r.dataset.result === want);
        r.hidden = !ok; if (ok) n++;
      });
      if (out) out.textContent = n === rows.length ? n + " rows" : n + " of " + rows.length + " rows";
    }
    q.addEventListener("input", apply); if (sel) sel.addEventListener("input", apply);
    apply();
  });
})();

// Catalog filters: progressive enhancement; the table works without script.
(function () {
  var table = document.getElementById("catalog");
  if (!table) return;
  var q = document.getElementById("q"), tr = document.getElementById("f-track"),
      comp = document.getElementById("f-comp"), st = document.getElementById("f-status"),
      out = document.getElementById("count");
  var rows = Array.prototype.slice.call(table.tBodies[0].rows);
  var hash = location.hash.replace("#", "");
  if (hash && comp.querySelector('option[value="' + hash + '"]')) comp.value = hash;
  function apply() {
    var text = q.value.trim().toLowerCase(), n = 0;
    rows.forEach(function (r) {
      var ok = (!text || r.dataset.text.indexOf(text) !== -1) &&
               (!tr.value || r.dataset.track === tr.value) &&
               (!comp.value || r.dataset.comp === comp.value) &&
               (!st.value || r.dataset.status === st.value);
      r.hidden = !ok; if (ok) n++;
    });
    out.textContent = n === rows.length ? n + " cases" : n + " of " + rows.length + " cases";
  }
  [q, tr, comp, st].forEach(function (el) { el.addEventListener("input", apply); });
  apply();
})();

// Render TeX written as \( … \) or $$ … $$ in case READMEs (KaTeX loads deferred).
window.addEventListener("load", function () {
  if (typeof renderMathInElement !== "function") return;
  renderMathInElement(document.querySelector("main") || document.body, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\(", right: "\\)", display: false }
    ],
    throwOnError: false
  });
});
