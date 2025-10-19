// Sovrascrive la riga "X row(s) where ..." usando le label delle FK
// - Non crea nuovi elementi: modifica quello già presente
// - Funziona anche dopo cambi dei filtri (MutationObserver)

(function () {
  // opzionale: alias più parlanti per le chiavi
  const ALIAS = {
    // "interrotto_id": "motivo",
    // "partner_id": "partner",
    // "luogo_id": "luogo"
  };

  const SEL_CONTAINER = ".content"; // contenitore principale in Datasette

  const q = (s, r = document) => r.querySelector(s);
  const qa = (s, r = document) => Array.from(r.querySelectorAll(s));
  const clean = t => (t || "").replace(/\u00a0/g, " ").trim();

  // Trova il nodo che mostra "X row where ..." (p/h2/div/strong ecc.)
  function findSummaryNode() {
    const root = q(SEL_CONTAINER) || document;
    // cerca un elemento con quel testo
    const candidates = qa("p, h2, h3, div, strong, span", root);
    for (const el of candidates) {
      const txt = clean(el.textContent).toLowerCase();
      if (!txt) continue;
      if (/^\d+\s+rows?\s+where\s+.*$/i.test(txt)) {
        // preferisci il contenitore più grande (p/div) rispetto a <strong>
        return el.closest("p, h2, h3, div") || el;
      }
    }
    return null;
  }

  function getColumnsIndex(table) {
    const head = table?.tHead?.rows?.[0];
    if (!head) return {};
    const map = {};
    qa("th", head).forEach((th, i) => {
      const name = clean(th.textContent).toLowerCase();
      if (name) map[name] = i;
    });
    return map;
  }

  function getLabelMap(table, idxByCol) {
    const body = table?.tBodies?.[0];
    if (!body || !body.rows.length) return {};
    const firstRow = body.rows[0];
    const res = {};
    Object.keys(idxByCol).forEach(col => {
      if (!/_id$/i.test(col)) return;
      const i = idxByCol[col];
      const cell = firstRow.cells[i];
      if (!cell) return;
      const a = cell.querySelector("a");
      const txt = clean(a ? a.textContent : cell.textContent);
      if (txt) res[col] = txt;
    });
    return res;
  }

  function prettyName(col) {
    return (ALIAS[col] || col.replace(/_id$/i, "")).replace(/_/g, " ");
  }

  function rewriteSummary() {
    const table = q("table.rows-and-columns");
    if (!table) return;

    const summaryNode = findSummaryNode();
    if (!summaryNode) return;

    const original = clean(summaryNode.textContent);
    // estrai il numero righe dalla frase originale, altrimenti conta le righe visibili
    const m = original.match(/^(\d+)\s+rows?/i);
    const n = m ? m[1] : (qa("tbody tr", table).length + "");

    const idxByCol = getColumnsIndex(table);
    const labelByCol = getLabelMap(table, idxByCol);

    // leggi i parametri query attivi
    const params = new URLSearchParams(location.search);
    const parts = [];
    for (const [k, v] of params.entries()) {
      const key = k.toLowerCase();
      if (/_id$/i.test(key) && labelByCol[key]) {
        parts.push(`${prettyName(key)} = ${labelByCol[key]}`);
      }
    }
    if (!parts.length) return; // nessun *_id filtrato → lascia com'è

    summaryNode.textContent = `${n} row${n === "1" ? "" : "s"} where ${parts.join(" and ")}`;
  }

  function observeChanges() {
    const target = q(SEL_CONTAINER) || document.body;
    const obs = new MutationObserver(() => {
      clearTimeout(observeChanges._t);
      observeChanges._t = setTimeout(rewriteSummary, 50);
    });
    obs.observe(target, { childList: true, subtree: true, characterData: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    rewriteSummary();
    observeChanges();
  });
})();
