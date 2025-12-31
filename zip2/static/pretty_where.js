// Riscrive "X row(s) where ..." usando SEMPRE le label delle FK.
// Funziona anche se la colonna *_id è nascosta o non ci sono righe visibili.
(function () {
  // Mappa esplicita: quale tabella/label corrisponde a ciascun *_id.
  // Aggiungi qui le tue altre FK se vuoi lo stesso comportamento.
  const FK_MAP = {
    "indirizzo_id": { db: "output", table: "luogo", labelCol: "indirizzo" },
    "luogo_id":     { db: "output", table: "luogo", labelCol: "indirizzo" },
    // "partner_id": { db: "output", table: "partner", labelCol: "nome" },
  };

  // Alias più umani per il nome colonna (sinistra dell'uguale)
  const ALIAS = {
    "indirizzo_id": "luogo",
    "luogo_id": "luogo",
  };

  const q  = (s, r=document) => r.querySelector(s);
  const qa = (s, r=document) => Array.from(r.querySelectorAll(s));
  const clean = t => (t||"").replace(/\u00a0/g, " ").trim();

  function findSummaryNode() {
    const nodes = qa(".content p, .content h2, .content h3, .content div, .content strong, .content span");
    for (const el of nodes) {
      const txt = clean(el.textContent).toLowerCase();
      if (/^\d+\s+rows?\s+where\s+/.test(txt)) {
        return el.closest("p, h2, h3, div") || el;
      }
    }
    return null;
  }

  async function fkLabel(colKey, idVal) {
    const m = FK_MAP[colKey];
    if (!m || !idVal) return null;
    const url = `/${encodeURIComponent(m.db)}/${encodeURIComponent(m.table)}/${encodeURIComponent(idVal)}.json?_shape=objects`;
    try {
      const r = await fetch(url, { credentials: "same-origin" });
      if (!r.ok) return null;
      const obj = await r.json();                 // oggetto singolo
      const label = obj && obj[m.labelCol];
      return label ? String(label) : null;
    } catch { return null; }
  }

  async function rewrite() {
    const node = findSummaryNode();
    if (!node) return;

    const original = clean(node.textContent);
    const mRows = original.match(/^(\d+)\s+rows?/i);
    const n = mRows ? mRows[1] : null;

    const params = new URLSearchParams(location.search);
    const parts = [];

    for (const [kRaw, vRaw] of params.entries()) {
      const k = kRaw.toLowerCase();
      if (!/_id$/.test(k)) continue;             // solo chiavi esterne classiche

      const alias = ALIAS[k] || k.replace(/_id$/, "").replace(/_/g, " ");
      let val = vRaw;

      // Prova a risolvere la label via API
      const label = await fkLabel(k, vRaw);
      if (label) val = label;

      parts.push(`${alias} = ${val}`);
    }

    if (!parts.length) return;
    node.textContent = `${n || ""} row${n==="1" ? "" : "s"} where ${parts.join(" and ")}`;
  }

  document.addEventListener("DOMContentLoaded", rewrite);
  // Piccolo observer per quando cambi i filtri senza ricaricare
  const obsTarget = document.querySelector(".content") || document.body;
  const obs = new MutationObserver(() => {
    clearTimeout(obs._t);
    obs._t = setTimeout(rewrite, 60);
  });
  obs.observe(obsTarget, { childList: true, subtree: true, characterData: true });

  // flag di debug rapido: digita in console __prettyWhereLoaded
  window.__prettyWhereLoaded = true;
})();
