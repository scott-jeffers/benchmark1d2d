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
