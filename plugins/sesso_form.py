# neo-datasette version: 1.8
# Restore widgets using DB meta tables:
# - meta_registry_tables / meta_registry_columns / meta_column_type / meta_type_registry
# - FK detection via PRAGMA foreign_key_list()
# Also serve both /sesso and /-/sesso for compatibility.

from datasette import hookimpl
from datasette.utils.asgi import Response

LABEL_CANDIDATES = ("nome", "name", "titolo", "title", "label", "descrizione", "descr", "desc", "note")

async def _table_columns(datasette, table: str):
    db = datasette.get_database()
    res = await db.execute(f"PRAGMA table_info({table})")
    return [r["name"] for r in res.rows]

async def _fk_map(datasette, table: str):
    db = datasette.get_database()
    res = await db.execute(f"PRAGMA foreign_key_list({table})")
    mp = {}
    for r in res.rows:
        # r: id, seq, table, from, to, on_update, on_delete, match
        mp[r["from"]] = {"ref_table": r["table"], "ref_column": r["to"]}
    return mp

async def _choices_for_table(datasette, ref_table: str, ref_column: str = "id", limit: int = 500):
    db = datasette.get_database()
    cols = await _table_columns(datasette, ref_table)

    label_expr = None
    # Special-case persona: nome+cognome
    if "nome" in cols and "cognome" in cols:
        label_expr = "COALESCE(nome,'') || CASE WHEN cognome IS NOT NULL AND cognome!='' THEN ' '||cognome ELSE '' END"
    else:
        for c in LABEL_CANDIDATES:
            if c in cols and c != ref_column:
                label_expr = f"COALESCE({c}, '')"
                break

    if not label_expr:
        label_expr = f"CAST({ref_column} AS TEXT)"

    sql = f"SELECT {ref_column} AS value, {label_expr} AS label FROM {ref_table} ORDER BY {ref_column} LIMIT {limit}"
    res = await db.execute(sql)
    out = []
    for r in res.rows:
        out.append({"value": r["value"], "label": r["label"] if r["label"] not in (None, "") else str(r["value"])})
    return out

async def _meta_fields(datasette, table: str):
    db = datasette.get_database()

    # Find table_id
    trow = await db.execute(
        "SELECT id FROM meta_registry_tables WHERE name = ?",
        [table],
    )
    if not trow.rows:
        return None

    table_id = trow.rows[0]["id"]

    sql = '''
    SELECT
        c.id AS column_id,
        c.name AS name,
        ct.type_key AS type_key,
        COALESCE(ct.nullable, 1) AS nullable,
        tr.ui_widget AS ui_widget,
        tr.default_mode AS default_mode,
        tr.default_expr AS default_expr
    FROM meta_registry_columns c
    LEFT JOIN meta_column_type ct ON ct.column_id = c.id
    LEFT JOIN meta_type_registry tr ON tr.type_key = ct.type_key
    WHERE c.table_id = ?
    ORDER BY c.id
    '''
    res = await db.execute(sql, [table_id])

    # Build FK map and choices for select widgets
    fk = await _fk_map(datasette, table)

    fields = []
    for r in res.rows:
        name = r["name"]
        if name.lower() == "id":
            continue

        type_key = r["type_key"] or "text"
        ui_widget = r["ui_widget"] or ""
        nullable = int(r["nullable"]) if r["nullable"] is not None else 1

        f = {
            "name": name,
            "type_key": type_key,
            "ui_widget": ui_widget,
            "nullable": nullable,
            "default_mode": r["default_mode"],
            "default_expr": r["default_expr"],
            "choices": [],
            "ref_table": None,
            "ref_column": None,
        }

        # Detect FK targets
        if name in fk:
            f["ref_table"] = fk[name]["ref_table"]
            f["ref_column"] = fk[name]["ref_column"]

        # Populate choices for selects
        if ui_widget in ("select", "multi_select") or type_key in ("fk", "single_choice", "multiple_choice"):
            if f["ref_table"]:
                f["choices"] = await _choices_for_table(datasette, f["ref_table"], f["ref_column"] or "id")
            else:
                # If no FK, but still a choice type, fall back to empty choices (or could be in a future meta table)
                f["choices"] = []

        fields.append(f)

    return fields

async def _insert_sesso(request, datasette, table: str = "sesso"):
    if request.method != "POST":
        return Response.json({"ok": False, "error": "POST required"}, status=405)

    form = await request.post_vars()

    fields = await _meta_fields(datasette, table)
    if fields is None:
        return Response.json({"ok": False, "error": "Meta tables not configured for this table"}, status=500)

    allowed = {f["name"]: f for f in fields}

    items = []
    present = set()
    for k, v in (form or {}).items():
        if k == "csrftoken":
            continue
        if k not in allowed:
            continue
        if v in (None, "", []):
            continue
        present.add(k)
        items.append((k, v))

    # Handle non-nullable booleans: checkbox missing means 0
    for name, f in allowed.items():
        if f["type_key"] == "boolean" and f["nullable"] == 0 and name not in present:
            items.append((name, 0))

    if not items:
        return Response.json({"ok": False, "error": "No data submitted"}, status=400)

    db = datasette.get_database()
    columns = ", ".join([k for k, _ in items])
    placeholders = ", ".join(["?"] * len(items))
    values = [v for _, v in items]

    await db.execute_write(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        values,
    )

    return Response.json({"ok": True})

@hookimpl
def register_routes():
    async def sesso_form(request, datasette):
        fields = await _meta_fields(datasette, "sesso")
        if fields is None:
            return Response.html("<h1>Errore</h1><p>Meta tables non trovate o non configurate per 'sesso'.</p>", status=500)

        html = await datasette.render_template(
            "sesso.html",
            {
                "fields": fields,
                "db_name": datasette.get_database().name,
                "table": "sesso",
                "neo_version": "1.8",
            },
            request=request,
        )
        return Response.html(html)

    async def sesso_insert(request, datasette):
        return await _insert_sesso(request, datasette, "sesso")

    return [
        (r"^/sesso$", sesso_form),
        (r"^/sesso/insert$", sesso_insert),
        # compatibility with older template/action
        (r"^/-/sesso$", sesso_form),
        (r"^/-/sesso/insert$", sesso_insert),
    ]
