from datasette import hookimpl

ALWAYS_KEEP = {"id"}  # colonne che non vanno mai nascoste (puoi aggiungere: "inizio","fine",...)

def _quote_ident(name: str) -> str:
    # Quote per identificatori SQLite
    return '"' + name.replace('"', '""') + '"'

def _get_filters_for_table(request, column_names_lower):
    """
    Estrae filtri equality dalla querystring, limitati alle colonne della tabella.
    Supporta valori ripetuti -> IN (...).
    Ignora parametri che iniziano con '_' (es. _sort, _columns, ecc.).
    """
    filters = []   # lista di (col_name_originale, valori[])
    if not request:
        return filters

    # alcuni ambienti hanno request.args, altri request.query_params
    qp = getattr(request, "args", None) or getattr(request, "query_params", None)
    if not qp:
        return filters

    # getlist compatibile
    getlist = getattr(qp, "getlist", None)
    get = getattr(qp, "get", None)

    # mappa lower->originale (per tenere il case corretto)
    lower_to_original = {c.lower(): c for c in column_names_lower.values()}

    # Scorri tutte le chiavi della querystring
    keys = []
    if hasattr(qp, "keys"):
        keys = list(qp.keys())
    else:
        # fallback: tenta di leggere tramite to_dict flat
        try:
            keys = list(dict(qp).keys())
        except Exception:
            keys = []

    for k in keys:
        if not k or k.startswith("_"):
            continue
        lk = k.lower()
        if lk not in column_names_lower:
            continue
        vals = []
        if callable(getlist):
            vals = list(getlist(k))
        if not vals and callable(get):
            v = get(k)
            if v is not None:
                vals = [v]
        # pulizia valori vuoti
        vals = [v for v in vals if v is not None and str(v) != ""]
        if not vals:
            continue
        filters.append((lower_to_original[lk], vals))
    return filters

def _non_empty_sql(expr_quoted: str) -> str:
    """
    Ritorna un'espressione SQL che vale 1 se la cella è 'non vuota', 0 altrimenti.
    Definizione 'vuoto':
      - NULL
      - testo che, dopo trim, è stringa vuota
      - numeri == 0
      - per altri tipi: usiamo lunghezza > 0 come non-vuoto
    """
    # Nota: typeof() è specifico SQLite (ok per Datasette su SQLite)
    return f"""
      CASE
        WHEN {expr_quoted} IS NULL THEN 0
        WHEN typeof({expr_quoted}) = 'text' AND length(trim({expr_quoted})) = 0 THEN 0
        WHEN typeof({expr_quoted}) IN ('integer','real') AND {expr_quoted} = 0 THEN 0
        WHEN typeof({expr_quoted}) = 'blob' AND length({expr_quoted}) = 0 THEN 0
        ELSE 1
      END
    """

@hookimpl
def table_visible_columns(columns, table, database, request, datasette):
    """
    Nasconde automaticamente le colonne che risultano interamente vuote/false
    nel dataset filtrato corrente della tabella/view.
    Rispetta _columns/_hide: se presenti, lascia fare a quelli (o applica _hide sopra).
    Permette di disattivare con ?_auto_hide_empty=off
    """
    # Normalizza input 'columns' e prepara mapping nome->oggetto
    input_names = []
    col_by_name = {}
    for c in columns:
        name = c.get("name") if isinstance(c, dict) else str(c)
        input_names.append(name)
        col_by_name[name] = c

    # Contesto DB
    db = datasette.databases.get(database)
    if not db or not table:
        return columns  # nessuna azione se manca contesto

    # Parametri di controllo da querystring
    qp = getattr(request, "args", None) or getattr(request, "query_params", None)
    auto_on = True
    if qp is not None:
        try:
            # _auto_hide_empty=off per disattivare
            val = (qp.get("_auto_hide_empty") or "").lower()
            if val in ("0", "off", "false", "no"):
                auto_on = False
        except Exception:
            pass

    # Se l'utente specifica _columns o _hide, NON attiviamo auto-hide (rispettiamo la scelta esplicita)
    def _getlist(key):
        gl = getattr(qp, "getlist", None)
        if callable(gl):
            return list(gl(key))
        g = getattr(qp, "get", None)
        if callable(g):
            v = g(key)
            return [v] if v is not None else []
        return []

    has_columns_param = bool(_getlist("_columns"))
    has_hide_param = bool(_getlist("_hide"))

    if not auto_on:
        # ma applichiamo comunque _hide se presente: teniamo comportamento coerente
        if has_hide_param:
            hide_set = {h.strip().lower() for v in _getlist("_hide") for h in v.split(",")}
            visible = [n for n in input_names if n.lower() not in hide_set]
            return [col_by_name[n] for n in visible]
        return columns

    if has_columns_param:
        # Se l'utente ha chiesto colonne esplicite, lasciamo Apache/altro plugin gestire (o Datasette).
        # Eventualmente applichiamo _hide sopra, se presente.
        visible = []
        requested = [p.strip() for v in _getlist("_columns") for p in v.split(",") if p.strip()]
        requested_lower = [r.lower() for r in requested]
        lower_to_original = {n.lower(): n for n in input_names}
        for r in requested_lower:
            orig = lower_to_original.get(r)
            if orig:
                visible.append(orig)
        if not visible:
            visible = input_names[:]
        if has_hide_param:
            hide_set = {h.strip().lower() for v in _getlist("_hide") for h in v.split(",")}
            visible = [n for n in visible if n.lower() not in hide_set]
        return [col_by_name[n] for n in visible]

    # Auto-hide: costruisci i filtri equality dalla querystring
    column_names_lower = {n.lower(): n for n in input_names}
    eq_filters = _get_filters_for_table(request, column_names_lower)

    # Costruisci WHERE e parametri
    where_clauses = []
    params = []
    for col_name, values in eq_filters:
        qcol = _quote_ident(col_name)
        if len(values) == 1:
            where_clauses.append(f"{qcol} = ?")
            params.append(values[0])
        else:
            where_clauses.append(f"{qcol} IN ({','.join('?' for _ in values)})")
            params.extend(values)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Determina quali colonne sono NON completamente vuote
    keep = set()
    for name in input_names:
        if name in ALWAYS_KEEP:
            keep.add(name)
            continue
        expr = _quote_ident(name)
        non_empty = _non_empty_sql(expr)
        # Query: c'è almeno UNA riga (rispetto ai filtri) con valore non-vuoto per questa colonna?
        sql = f"SELECT 1 FROM {_quote_ident(table)} {where_sql} AND {non_empty} = 1 LIMIT 1" if where_sql else \
              f"SELECT 1 FROM {_quote_ident(table)} WHERE {non_empty} = 1 LIMIT 1"
        try:
            res = db.execute(sql, params)
            if res.first() is not None:
                keep.add(name)
        except Exception:
            # Se la colonna non esiste davvero (view/alias strani), tienila per sicurezza
            keep.add(name)

    # Se keep è vuoto (tutte vuote), non fare nulla per evitare pagina "bianca"
    if not keep:
        return columns

    visible = [n for n in input_names if n in keep]
    # Applica eventuale _hide (se presente)
    if has_hide_param:
        hide_set = {h.strip().lower() for v in _getlist("_hide") for h in v.split(",")}
        visible = [n for n in visible if n.lower() not in hide_set]

    return [col_by_name[n] for n in visible]
