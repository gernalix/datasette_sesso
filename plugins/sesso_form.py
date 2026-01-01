# neo-datasette version: 1.12
# Fixes:
# - meta_registry_tables uses column "name" (not "table_name")
# - meta_registry_columns uses column "name" (not "column_name")
# - meta_type_registry does NOT store fk_table/fk_label_column in this project:
#   FK options are derived from PRAGMA foreign_key_list(<table>)
# - Always redirects to /{db}/sesso after successful insert (303) unless client asks for JSON
#
# Notes:
# - This plugin chooses the database that contains table "sesso" (skipping Datasette "_internal").

import json
from datasette import hookimpl
from datasette.utils.asgi import Response


async def _db_has_table(db, table_name: str) -> bool:
    row = await db.execute(
        "select 1 from sqlite_master where type='table' and name = ? limit 1",
        [table_name],
    )
    return bool(row.rows)


async def _choose_db(datasette, request):
    # If URL specifies a DB, use it
    db_name = (getattr(request, "url_vars", {}) or {}).get("database")
    if db_name and db_name in datasette.databases:
        return datasette.get_database(db_name), db_name

    # Prefer DB containing sesso
    for name, db in datasette.databases.items():
        if name == "_internal":
            continue
        if await _db_has_table(db, "sesso"):
            return db, name

    # Fallback first non-internal DB
    for name, db in datasette.databases.items():
        if name != "_internal":
            return db, name

    db = datasette.get_database()
    return db, getattr(db, "name", "db")


async def _pragma_foreign_keys(db, table: str):
    # Returns list of dicts from PRAGMA foreign_key_list(table)
    try:
        res = await db.execute(f"pragma foreign_key_list({table})")
        # Datasette returns rows as sqlite3.Row-ish
        out = []
        for r in res.rows:
            # columns: id, seq, table, from, to, on_update, on_delete, match
            out.append({
                "table": r["table"] if "table" in r.keys() else r[2],
                "from": r["from"] if "from" in r.keys() else r[3],
                "to": r["to"] if "to" in r.keys() else r[4],
            })
        return out
    except Exception:
        return []


async def _table_columns(db, table: str):
    # PRAGMA table_info
    res = await db.execute(f"pragma table_info({table})")
    cols = []
    for r in res.rows:
        # cid, name, type, notnull, dflt_value, pk
        name = r["name"] if "name" in r.keys() else r[1]
        ctype = r["type"] if "type" in r.keys() else r[2]
        cols.append((name, ctype))
    return cols


async def _pick_label_column(db, table: str, options_json: str | None):
    # 1) explicit options_json {"label_column": "..."}
    if options_json:
        try:
            obj = json.loads(options_json)
            if isinstance(obj, dict):
                lc = obj.get("label_column") or obj.get("label") or obj.get("display")
                if lc:
                    return lc
        except Exception:
            pass

    cols = await _table_columns(db, table)
    names = [c[0] for c in cols]

    # 2) common names
    for candidate in ("nome", "name", "titolo", "title", "label"):
        if candidate in names:
            return candidate

    # 3) first TEXT-like column (not id)
    for n, t in cols:
        if n.lower() == "id":
            continue
        if (t or "").upper().startswith("TEXT"):
            return n

    # 4) fallback
    return "id"


async def _meta_fields(db):
    # Find table_id in meta_registry_tables where name='sesso'
    t = await db.execute("select id from meta_registry_tables where name = 'sesso' limit 1")
    if not t.rows:
        return []

    table_id = t.rows[0][0] if not isinstance(t.rows[0], dict) else t.rows[0]["id"]

    cols = await db.execute(
        "select id, name from meta_registry_columns where table_id = ? order by id",
        [table_id],
    )
    col_ids = [r[0] for r in cols.rows]
    col_names = {r[0]: r[1] for r in cols.rows}
    if not col_ids:
        return []

    q = ",".join(["?"] * len(col_ids))
    ct = await db.execute(
        f"select column_id, type_key, options_json from meta_column_type left join meta_type_registry on meta_column_type.type_key = meta_type_registry.type_key where column_id in ({q})",
        col_ids,
    )
    # Build map by column_id
    by_col = {}
    for r in ct.rows:
        # r: column_id, type_key, options_json
        col_id = r[0]
        by_col[col_id] = {"type_key": r[1], "options_json": r[2]}

    fields = []
    for col_id in col_ids:
        name = col_names.get(col_id)
        if not name or name.lower() == "id":
            continue

        tk = by_col.get(col_id, {}).get("type_key")
        # ui_widget from meta_type_registry
        ui = "text"
        opt_json = by_col.get(col_id, {}).get("options_json")
        if tk:
            tr = await db.execute("select ui_widget from meta_type_registry where type_key = ? limit 1", [tk])
            if tr.rows and tr.rows[0][0]:
                ui = tr.rows[0][0]

        fields.append({
            "name": name,
            "type_key": tk,
            "ui_widget": ui,
            "options_json": opt_json
        })
    return fields


async def _fk_options_for_column(db, base_table: str, col_name: str, options_json: str | None):
    fks = await _pragma_foreign_keys(db, base_table)
    fk = next((x for x in fks if x["from"] == col_name), None)
    if not fk:
        return None

    ref_table = fk["table"]
    label_col = await _pick_label_column(db, ref_table, options_json)

    try:
        rows = await db.execute(f"select id, {label_col} as label from {ref_table} order by label")
        return [{"id": r["id"], "label": r["label"]} for r in rows.rows]
    except Exception:
        rows = await db.execute(f"select id from {ref_table} order by id")
        return [{"id": r["id"], "label": r["id"]} for r in rows.rows]


def _wants_json(request):
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept


@hookimpl
def register_routes():
    async def sesso_form(request, datasette):
        db, db_name = await _choose_db(datasette, request)
        fields = await _meta_fields(db)

        fk_options = {}
        for f in fields:
            if f["ui_widget"] in ("select", "fk", "lookup"):
                opts = await _fk_options_for_column(db, "sesso", f["name"], f.get("options_json"))
                if opts is not None:
                    fk_options[f["name"]] = opts

        html = await datasette.render_template(
            "sesso.html",
            {
                "fields": fields,
                "fk_options": fk_options,
                "db_name": db_name,
                "version": "1.12",
            },
            request=request,
        )
        return Response.html(html)

    async def sesso_insert(request, datasette):
        db, db_name = await _choose_db(datasette, request)
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
