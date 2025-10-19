// Nasconde le colonne completamente vuote/false nella tabella principale di Datasette
// - considera vuote le celle con solo spazi, &nbsp;, <br>, <em> "subtle-id", ecc.
// - ignora colonne con qualunque contenuto visibile (testo, link, emoji, numeri)
// - si ri-esegue su cambi DOM (filtri, navigazioni interne)

(function () {
  const MAX_CELLS = 40000; // safety per tabelle mostruose (righe*colonne)

  const q  = (s, r = document) => r.querySelector(s);
  const qa = (s, r = document) => Array.from(r.querySelectorAll(s));

  function cellIsVisiblyEmpty(td) {
    if (!td) return true;

    // Se contiene elementi "visibili" tipici, NON è vuota
    if (td.querySelector("a, svg, img, input, button, select, textarea")) return false;

    // Testo "ripulito"
    const text = (td.textContent || "")
      .replace(/\u00a0/g, " ")  // NBSP -> spazio
      .replace(/\s+/g, " ")     // collassa spazi/newline
      .trim();

    if (text) return false;

    // Anche l'HTML dev'essere vuoto oppure solo markup "invisibile"
    const html = (td.innerHTML || "")
      .replace(/&nbsp;/gi, "")
      .replace(/<br\s*\/?>/gi, "")
      .replace(/<em[^>]*>.*?<\/em>/gi, "") // rimuovi eventuali <em> numeretti
      .replace(/\s+/g, "")
      .trim();

    return html === "" ;
  }

  function hideEmptyColumns() {
    const table = q("table.rows-and-columns");
    if (!table || !table.tBodies[0]) return;

    const bodyRows = Array.from(table.tBodies[0].rows);
    const headRow  = table.tHead ? table.tHead.rows[0] : null;
    const nCols    = headRow ? headRow.cells.length : (bodyRows[0]?.cells.length || 0);
    if (!nCols || !bodyRows.length) return;

    if (nCols * bodyRows.length > MAX_CELLS) return; // evita lavoro eccessivo

    // Determina quali colonne sono completamente vuote in TUTTE le righe visibili
    const toHideIdx = [];
    outer:
    for (let c = 0; c < nCols; c++) {
      for (let r = 0; r < bodyRows.length; r++) {
        const td = bodyRows[r].cells[c];
        if (!cellIsVisiblyEmpty(td)) continue outer; // non vuota → tieni la colonna
      }
      toHideIdx.push(c + 1); // nth-child è 1-based
    }
    if (!toHideIdx.length) return;

    // Inietta UNA SOLA regola CSS che nasconde th/td delle colonne trovate
    const sel = toHideIdx
      .map(i => `table.rows-and-columns th:nth-child(${i}), table.rows-and-columns td:nth-child(${i})`)
      .join(", ");
    const style = document.createElement("style");
    style.id = "hide-empty-cols-style";
    style.textContent = `${sel} { display: none !important; }`;

    // Rimuovi eventuale regola precedente e aggiungi la nuova
    const old = q("#hide-empty-cols-style");
    if (old) old.remove();
    document.head.appendChild(style);
  }

  function installObserver() {
    const target = q(".content") || document.body;
    const obs = new MutationObserver(() => {
      clearTimeout(installObserver._t);
      installObserver._t = setTimeout(hideEmptyColumns, 50);
    });
    obs.observe(target, { childList: true, subtree: true, characterData: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    hideEmptyColumns();
    installObserver();
  });
})();
