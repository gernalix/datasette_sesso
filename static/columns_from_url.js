// Applica _hide=... e _columns=... alla tabella HTML di Datasette, lato client.
// Funziona con nomi colonna esatti (case-insensitive). Supporta più param ripetuti.
(function () {
  const q  = (s, r=document) => r.querySelector(s);
  const qa = (s, r=document) => Array.from(r.querySelectorAll(s));
  function norm(s){ return (s||"").trim().toLowerCase(); }

  function apply() {
    const url = new URL(location.href);
    const hideParams = url.searchParams.getAll("_hide");
    const colsParams = url.searchParams.getAll("_columns");

    // niente da fare
    if (!hideParams.length && !colsParams.length) return;

    const table = q("table.rows-and-columns");
    if (!table || !table.tHead || !table.tBodies[0]) return;

    const head = table.tHead.rows[0];
    const body = table.tBodies[0];
    const nCols = head.cells.length;

    // mappa: nome colonna -> indice (1-based per nth-child)
    const idxByName = {};
    qa("th", head).forEach((th, i) => {
      idxByName[norm(th.textContent)] = i + 1;
    });

    // set colonne da mostrare/nascondere
    const showSet = new Set(colsParams.map(norm));
    const hideSet = new Set(hideParams.map(norm));

    // Se _columns è presente, tutto il resto va nascosto
    let toHideIdx = new Set();
    if (showSet.size) {
      qa("th", head).forEach((th, i) => {
        const name = norm(th.textContent);
        if (!showSet.has(name)) toHideIdx.add(i + 1);
      });
    }
    // Inoltre applica gli _hide espliciti
    hideSet.forEach(name => {
      const idx = idxByName[name];
      if (idx) toHideIdx.add(idx);
    });

    if (!toHideIdx.size) return;

    // Inietta una sola regola CSS per nascondere th/td delle colonne scelte
    const sel = [...toHideIdx]
      .map(i => `table.rows-and-columns th:nth-child(${i}), table.rows-and-columns td:nth-child(${i})`)
      .join(", ");
    const style = document.createElement("style");
    style.id = "columns-from-url-style";
    style.textContent = `${sel}{display:none!important}`;
    const old = q("#columns-from-url-style");
    if (old) old.remove();
    document.head.appendChild(style);
  }

  document.addEventListener("DOMContentLoaded", apply);
})();
