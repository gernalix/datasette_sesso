from datasette import hookimpl

# Colonne sempre visibili (aggiungi/togli come preferisci)
ALWAYS_KEEP = {"id", "inizio", "fine"}

def _qid(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'

def _getlist(qp, key: str):
    if qp is None:
        return []
    getlist = getattr(qp, "getlist", None)
    if callable(getlist):
        try:
            return list(getlist(key))
        except Exception:
            pass
    get = getattr(qp, "get", None)
    if callable(get):
        v = get(key)
        return [v] if v is not None else []
    return []

def _split_csv(vals):
    out = []
    for v in vals:
        if v is None:
            continue
        for p in str(v).split(","):
            p = p.strip()
            if p:
                out.append(p)
    return out

def _non_empty_sql(expr: str) -> str:
    """
    1 se NON vuoto, 0 altrimenti.
    Vuoto se:
      - NULL
      - testo: solo spazi / NBSP / '&nbsp;'
      - testo: '0','false','f','no','n' (case-insensitive)
      - numerico: 0
      - blob: len=0
    """
    # NBSP = char(160)
    trimmed = f"trim(replace(replace({expr}, char(160), ''), '&nbsp;', ''))"
    lowered = f"lower({trimmed})"
    return f"""
    CASE
      WHEN {expr} IS NULL THEN 0
      WHEN typeof({expr}) = 'text' AND (
        length({trimmed}) = 0 OR {lowered} IN ('0','false','f','no','n')
      ) THEN 0
      WHEN typeof({expr}) IN ('integer','real') AND {expr} = 0 THEN 0
      WHEN typeof({expr}) = 'blob' AND length({expr}) = 0 THEN 0
      ELSE 1
    END
    """

def _build_where(qp, name_map):
    """
    WHERE dai parametri equality (col=val / col=val1&col=val2).
    Se presente _where, lo include (pass-through: usalo solo se ti fidi della tua UI).
    """
    if qp is None:
        return "", []
    clauses, params = [], []
    keys = list(qp.keys()) if hasattr(qp, "keys") else []
    for k in keys:
        if not k or k.startswith("_"):
            continue
        lk = k.lower()
        if lk not in name_map:
            continue
        vals = [v for v in _getlist(qp, k) if v is not None and str(v) != ""]
        if not vals:
            continue
        col = _qid(name_map[lk])
        if len(vals) == 1:
            clauses.append(f"{col} = ?")
            params.append(vals[0])
        else:
            ph = ",".join("?" for _ in vals)
            clauses.append(f"{col} IN ({ph})")
            params.extend(vals)
    w = qp.get("_where") if hasattr(qp, "get") else None
    if w:
        clauses.append(f"({w})")
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params

@hookimpl
async def table_visible_columns(columns, table, database, request, datasette=None, **kwargs):
    """
    Nasconde automaticamente (server-side) le colonne completamente vuote/false
    nel risultato filtrato corrente. Rispetta _columns/_hide e supporta disattivazione
    con _auto_hide_empty=off.
    """
    # Normalizza lista colonne
    names, by_name = [], {}
    for c in columns:
        n = c.get("name") if isinstance(c, dict) else str(c)
        names.append(n)
        by_name[n] = c

    # Datasette DB handle
    ds = datasette  # può arrivare come kw in versioni recenti
    if ds is None:
        # fallback: in alcune versioni non passa datasette → non possiamo interrogare
        return columns
    if database not in ds.databases or not table:
        return columns
    db = ds.databases[database]

    qp = getattr(request, "args", None) or getattr(request, "query_params", None)

    # Disattiva auto-hide?
    try:
        val = (qp.get("_auto_hide_empty") or "").lower() if qp else ""
        if val in ("0", "off", "false", "no"):
            # ma applica eventuale _hide
            hides = _split_csv(_getlist(qp, "_hide"))
            if hides:
                hset = {h.lower() for h in hides}
                vis = [n for n in names if n.lower() not in hset]
                return [by_name[n] for n in vis]
            return columns
    except Exception:
        pass

    # _columns esplicite?
    cols = _split_csv(_getlist(qp, "_columns"))
    if cols:
        l2o = {n.lower(): n for n in names}
        sel = [l2o.get(c.lower()) for c in cols if l2o.get(c.lower())]
        if not sel:
            sel = names[:]
        hides = _split_csv(_getlist(qp, "_hide"))
        if hides:
            hset = {h.lower() for h in hides}
            sel = [n for n in sel if n.lower() not in hset]
        return [by_name[n] for n in sel]

    # —— AUTO-HIDE —— (query unica)
    name_map = {n.lower(): n for n in names}
    where_sql, params = _build_where(qp, name_map)

    select_fields = []
    for n in names:
        if n in ALWAYS_KEEP:
            select_fields.append(f"1 AS {_qid('__keep__' + n)}")
        else:
            select_fields.append(f"MAX({_non_empty_sql(_qid(n))}) AS {_qid('__keep__' + n)}")
    sql = f"SELECT {', '.join(select_fields)} FROM {_qid(table)} {where_sql}"

    try:
        res = await db.execute(sql, params)
        row = res.first()
        if row is None:
            return columns  # niente righe → non cambiare nulla
        keep = set()
        for n in names:
            try:
                flag = int(row['__keep__' + n])
            except Exception:
                flag = 0
            if flag == 1:
                keep.add(n)
        if not keep:
            return columns  # safety
        visible = [n for n in names if n in keep]
    except Exception as e:
        print("[auto_hide] ERROR:", e)
        return columns

    # Applica eventuale _hide sopra
    hides = _split_csv(_getlist(qp, "_hide"))
    if hides:
        hset = {h.lower() for h in hides}
        visible = [n for n in visible if n.lower() not in hset]

    print("[auto_hide] table:", table, "keep:", visible)  # LOG di diagnosi
    return [by_name[n] for n in visible]
