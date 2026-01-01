# neo-datasette version: 1.11
# Fix:
# - Don't accidentally pick Datasette internal DB ("_internal") when resolving db for meta tables.
# - Choose the DB that actually contains table 'sesso' (or meta_registry_tables) before querying meta tables.
# - Keep server-side 303 redirect to the sesso table after POST.

from datasette import hookimpl
from datasette.utils.asgi import Response


async def _db_has_table(db, table_name: str) -> bool:
    try:
        row = await db.execute(
            "select 1 from sqlite_master where type='table' and name = ? limit 1",
            [table_name],
        )
        return bool(row.rows)
    except Exception:
        return False


async def _choose_db_for_sesso(datasette, request):
    # If URL specifies a DB, use it.
    db_name = (getattr(request, "url_vars", {}) or {}).get("database")
    if db_name and db_name in datasette.databases:
        return datasette.get_database(db_name), db_name

    # Prefer a DB that contains 'sesso' table
    for name, db in datasette.databases.items():
        if name == "_internal":
            continue
        if await _db_has_table(db, "sesso"):
            return db, name

    # Next prefer a DB that contains meta tables
    for name, db in datasette.databases.items():
        if name == "_internal":
            continue
        if await _db_has_table(db, "meta_registry_tables"):
            return db, name

    # Fallback: first non-internal DB
    for name, db in datasette.databases.items():
        if name != "_internal":
            return db, name

    # Last fallback: whatever Datasette returns
    db = datasette.get_database()
    return db, getattr(db, "name", "db")


async def _meta_fields(db):
    # Your project schema:
    #   meta_registry_tables(table_name)
    #   meta_registry_columns(table_id, column_name)
    #   meta_column_type(column_id, type_key)
    #   meta_type_registry(type_key, ui_widget, fk_table, fk_label_column)
    table_id_row = await db.execute(
        "select id from meta_registry_tables where table_name = 'sesso' limit 1"
    )
    if not table_id_row.rows:
        return []

    table_id = table_id_row.rows[0][0]

    cols = await db.execute(
        "select id, column_name from meta_registry_columns where table_id = ? order by id",
        [table_id],
    )
    col_ids = [r[0] for r in cols.rows]
    col_names = {r[0]: r[1] for r in cols.rows}
    if not col_ids:
        return []

    q_marks = ",".join(["?"] * len(col_ids))
    ct = await db.execute(
        f"select column_id, type_key from meta_column_type where column_id in ({q_marks})",
        col_ids,
    )
    type_key_by_col = {r[0]: r[1] for r in ct.rows}

    type_keys = sorted({tk for tk in type_key_by_col.values() if tk})
    tr = {}
    if type_keys:
        q_marks2 = ",".join(["?"] * len(type_keys))
        tr_rows = await db.execute(
            f"select type_key, ui_widget, fk_table, fk_label_column "
            f"from meta_type_registry where type_key in ({q_marks2})",
            type_keys,
        )
        for r in tr_rows.rows:
            tr[r[0]] = {"ui_widget": r[1], "fk_table": r[2], "fk_label_column": r[3]}

    fields = []
    for col_id in col_ids:
        name = col_names.get(col_id)
        if not name or name.lower() == "id":
            continue
        tk = type_key_by_col.get(col_id)
        info = tr.get(tk, {})
        ui = info.get("ui_widget") or "text"
        fields.append(
            {
                "name": name,
                "type_key": tk,
                "ui_widget": ui,
                "fk_table": info.get("fk_table"),
                "fk_label_column": info.get("fk_label_column"),
            }
        )
    return fields


async def _fk_options(db, fk_table, label_col):
    if not fk_table:
        return []
    label = label_col or "id"
    try:
        rows = await db.execute(f"select id, {label} as label from {fk_table} order by label")
        return [{"id": r["id"], "label": r["label"]} for r in rows.rows]
    except Exception:
        rows = await db.execute(f"select id from {fk_table} order by id")
        return [{"id": r["id"], "label": r["id"]} for r in rows.rows]


def _wants_json(request):
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept


@hookimpl
def register_routes():
    async def sesso_form(request, datasette):
        db, db_name = await _choose_db_for_sesso(datasette, request)
        fields = await _meta_fields(db)

        fk_options = {}
        for f in fields:
            if f.get("ui_widget") in ("select", "fk", "lookup") and f.get("fk_table"):
                fk_options[f["name"]] = await _fk_options(db, f["fk_table"], f.get("fk_label_column"))

        html = await datasette.render_template(
            "sesso.html",
            {
                "fields": fields,
                "fk_options": fk_options,
                "db_name": db_name,
                "version": "1.11",
            },
            request=request,
        )
        return Response.html(html)

    async def sesso_insert(request, datasette):
        db, db_name = await _choose_db_for_sesso(datasette, request)
        if request.method != "POST":
            return Response.json({"ok": False, "error": "POST required"}, status=405)

        form = await request.post_vars()

        fields = await _meta_fields(db)
        allowed = {f["name"] for f in fields}

        items = []
        for k, v in (form or {}).items():
            if k == "csrftoken":
                continue
            if k not in allowed:
                continue
            if v in (None, "", []):
                continue
            if v == "on":
                v = 1
            items.append((k, v))

        if not items:
            if _wants_json(request):
                return Response.json({"ok": False, "error": "No data submitted"}, status=400)
            return Response.redirect("/sesso?err=1", status=303)

        columns = ", ".join([k for k, _ in items])
        placeholders = ", ".join(["?"] * len(items))
        values = [v for _, v in items]

        await db.execute_write(
            f"insert into sesso ({columns}) values ({placeholders})",
            values,
        )

        table_url = f"/{db_name}/sesso?_sort_desc=id"
        if _wants_json(request):
            return Response.json({"ok": True, "redirect": table_url})
        return Response.redirect(table_url, status=303)

    return [
        (r"^/sesso$", sesso_form),
        (r"^/sesso/insert$", sesso_insert),
    ]
