# plugins/fk_pretty_where.py
# ------------------------------------------------------------
# Mostra nella riga "X row(s) where ..." le LABEL delle FK
# invece degli ID, senza hard-coding per tabella/colonna.
#
# Come funziona (server-side):
# - Legge tutte le FK dallo schema SQLite (PRAGMA foreign_key_list)
# - Integra eventuali FK e label_column presenti in metadata.json
# - Per ogni parametro di query (es. ?indirizzo_id=4&partner_id=7)
#   risolve gli ID nelle etichette reali eseguendo SELECT mirate
# - Inietta il testo "umano" nel DOM con extra_body_script
#
# Limiti intenzionali:
# - Gestisce i filtri standard (= e IN) della UI tabellare.
# - Se mancano label_column nei metadata, usa la PK o 'id' come fallback.
# ------------------------------------------------------------

from __future__ import annotations

from datasette import hookimpl
from datasette.utils import await_me_maybe
from markupsafe import Markup
from typing import Dict, Tuple, List, Any, Optional
import json

# Cache in memoria per evitare di ricostruire la mappa ad ogni richiesta
_FK_CACHE: Dict[str, Dict[Tuple[str, str], Tuple[str, str, str]]] = {}
_PK_CACHE: Dict[Tuple[str, str], str] = {}  # (db, table) -> pk column name


def _qident(name: str) -> str:
    """Quoting sicuro per identificatori SQLite con doppi apici."""
    return '"' + name.replace('"', '""') + '"'


async def _get_pk(datasette, dbname: str, table: str) -> str:
    """Determina la primary key di 'table' (fallback: 'id')."""
    key = (dbname, table)
    if key in _PK_CACHE:
        return _PK_CACHE[key]

    db = datasette.databases[dbname]
    safe_table = table.replace("'", "''")
    sql = f"PRAGMA table_info('{safe_table}')"
    res = await db.execute(sql)
    pk = None
    for row in res.rows:
        if row["pk"] == 1:
            pk = row["name"]
            break
    if not pk:
        pk = "id"
    _PK_CACHE[key] = pk
    return pk


def _label_col_from_metadata(datasette, dbname: str, table: str) -> Optional[str]:
    """Ritorna label_column per una tabella dai metadata, se definito."""
    md = datasette.metadata() or {}
    db_md = (md.get("databases") or {}).get(dbname, {})
    t_md = (db_md.get("tables") or {}).get(table, {})
    return t_md.get("label_column")


async def _build_fk_map(datasette, dbname: str) -> Dict[Tuple[str, str], Tuple[str, str, str]]:
    """
    Costruisce la mappa:
      (child_table, child_col) -> (parent_table, parent_pk_col, parent_label_col)
    combinando PRAGMA + metadata.json
    """
    if dbname in _FK_CACHE:
        return _FK_CACHE[dbname]

    db = datasette.databases[dbname]
    fkmap: Dict[Tuple[str, str], Tuple[str, str, str]] = {}

    # 1) Elenco tabelle "reali"
    tables_res = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = [r["name"] for r in tables_res.rows]

    # 2) PRAGMA foreign_key_list per ciascuna tabella figlia
    for child_table in tables:
        safe_child = child_table.replace("'", "''")
        pragma_sql = f"PRAGMA foreign_key_list('{safe_child}')"
        fks = await db.execute(pragma_sql)
        for fk in fks.rows:
            child_col = fk["from"]
            parent_table = fk["table"]
            parent_pk = await _get_pk(datasette, dbname, parent_table)
            label_col = _label_col_from_metadata(datasette, dbname, parent_table) or parent_pk
            fkmap[(child_table, child_col)] = (parent_table, parent_pk, label_col)

    # 3) Integra FK dichiarate nei metadata.json (se presenti)
    md = datasette.metadata() or {}
    db_md = (md.get("databases") or {}).get(dbname, {})
    t_md = (db_md.get("tables") or {})  # dict: table -> config
    for child_table, conf in t_md.items():
        for fk in (conf.get("foreign_keys") or []):
            child_col = fk.get("column")
            parent_table = fk.get("other_table")
            parent_pk = fk.get("other_column") or await _get_pk(datasette, dbname, parent_table)
            label_col = (
                (t_md.get(parent_table, {}) or {}).get("label_column")
                or _label_col_from_metadata(datasette, dbname, parent_table)
                or parent_pk
            )
            if child_col and parent_table:
                fkmap[(child_table, child_col)] = (parent_table, parent_pk, label_col)

    _FK_CACHE[dbname] = fkmap
    return fkmap


def _alias_name(col: str) -> str:
    """Rende più umano il nome colonna a sinistra dell'uguale."""
    if col.endswith("_id"):
        col = col[:-3]
    return col.replace("_", " ")


async def _resolve_labels_for_param(
    datasette, dbname: str, table: str, col: str, values: List[str], fkmap
) -> str:
    """
    Se 'col' è FK nota, risolve ciascun ID in label tramite SELECT;
    altrimenti restituisce i valori grezzi.
    """
    key = (table, col)
    if key not in fkmap:
        return ", ".join(map(str, values))

    parent_table, parent_pk, parent_label = fkmap[key]
    db = datasette.databases[dbname]

    labels: List[str] = []
    for v in values:
        try:
            sql = (
                f"SELECT {_qident(parent_label)} AS label "
                f"FROM {_qident(parent_table)} WHERE {_qident(parent_pk)} = ? LIMIT 1"
            )
            row = (await db.execute(sql, [v])).first()
            labels.append(str(row["label"]) if row and row["label"] is not None else str(v))
        except Exception:
            labels.append(str(v))

    return ", ".join(labels)


async def _pretty_where_for_request(datasette, dbname: str, table: str, request) -> str:
    """Costruisce la riga 'N rows where col = Label, ...' risolvendo tutte le FK note."""
    qp = getattr(request, "args", None) or getattr(request, "query_params", None)
    if not qp:
        return ""

    fkmap = await _build_fk_map(datasette, dbname)

    # Raccogli i parametri 'user-facing' (esclusi quelli di servizio che iniziano con _)
    parts: List[str] = []
    keys = list(qp.keys()) if hasattr(qp, "keys") else []
    user_keys = [k for k in keys if k and not k.startswith("_")]

    # Conta righe (opzionale)
    n_rows: Optional[int] = None
    try:
        db = datasette.databases[dbname]
        where_clauses: List[str] = []
        params: List[Any] = []
        for k in user_keys:
            # supporta parametri ripetuti => IN (...)
            if hasattr(qp, "getlist"):
                vals = [v for v in qp.getlist(k) if v is not None and str(v) != ""]
            else:
                v = qp.get(k)
                vals = [v] if v is not None and str(v) != "" else []
            if not vals:
                continue
            if len(vals) == 1:
                where_clauses.append(f"{_qident(k)} = ?")
                params.append(vals[0])
            else:
                ph = ",".join("?" for _ in vals)
                where_clauses.append(f"{_qident(k)} IN ({ph})")
                params.extend(vals)

        cnt_sql = f"SELECT count(*) AS n FROM {_qident(table)}"
        if where_clauses:
            cnt_sql += " WHERE " + " AND ".join(where_clauses)
        row = (await db.execute(cnt_sql, params)).first()
        if row:
            n_rows = int(row["n"])
    except Exception:
        n_rows = None  # non è critico

    # Costruisci "col = label" per ciascun parametro
    for k in user_keys:
        if hasattr(qp, "getlist"):
            vals = [v for v in qp.getlist(k) if v is not None and str(v) != ""]
        else:
            v = qp.get(k)
            vals = [v] if v is not None and str(v) != "" else []
        if not vals:
            continue

        pretty_val = await _resolve_labels_for_param(datasette, dbname, table, k, vals, fkmap)
        parts.append(f"{_alias_name(k)} = {pretty_val}")

    if not parts:
        return ""

    prefix = f"{n_rows} row{'s' if n_rows != 1 else ''} where " if n_rows is not None else ""
    return prefix + " and ".join(parts)


@hookimpl
def extra_body_script(datasette, database, table, view_name, request, **kwargs):
    """
    Inietta uno script minimo che rimpiazza la riga standard "X row(s) where ..."
    con la versione 'umana' calcolata server-side.
    """
    if not (database and table and request):
        return []

    async def build():
        pretty = await _pretty_where_for_request(datasette, database, table, request)
        if not pretty:
            return ""
        # Script piccolissimo che trova il nodo del riepilogo e lo sostituisce.
        js = f"""
        <script>
        (function(){{
          function findNode(){{
            var root = document.querySelector('.content') || document;
            var nodes = root.querySelectorAll('p, h2, h3, div, strong, span');
            for (var i=0; i<nodes.length; i++) {{
              var t = (nodes[i].textContent||'').trim().toLowerCase();
              if (/^\\d+\\s+rows?\\s+where\\s+/.test(t)) {{
                return nodes[i].closest('p,h2,h3,div') || nodes[i];
              }}
            }}
            return null;
          }}
          var n = findNode();
          if (n) n.textContent = {json.dumps(pretty)};
        }})();
        </script>
        """
        return Markup(js)

    return [await_me_maybe(build())]
