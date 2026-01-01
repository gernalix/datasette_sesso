# neo-datasette version: 1.4
# Improve /sesso form: dynamically list columns from table schema, remove static CSS dependency,
# and keep INSERT safe (only known columns, ignore csrftoken).

from datasette import hookimpl
from datasette.utils.asgi import Response


def _infer_input(col_name: str, col_type: str):
    t = (col_type or "").upper()
    # Heuristic: treat "note" as textarea
    if col_name.lower() in ("note", "notes", "commento", "commenti", "descrizione", "descr"):
        return ("textarea", {})
    if "INT" in t:
        return ("number", {"inputmode": "numeric"})
    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return ("number", {"step": "any"})
    # default
    return ("text", {})


async def _get_sesso_columns(datasette):
    db = datasette.get_database()
    rows = await db.execute("PRAGMA table_info(sesso)")
    cols = []
    for r in rows.rows:
        name = r["name"]
        if name.lower() == "id":
            continue
        col_type = r["type"] or ""
        kind, attrs = _infer_input(name, col_type)
        cols.append(
            {
                "name": name,
                "type": col_type,
                "kind": kind,  # text / number / textarea
                "attrs": attrs,
            }
        )
    return cols


@hookimpl
def register_routes():
    async def sesso_form(request, datasette):
        cols = await _get_sesso_columns(datasette)
        html = await datasette.render_template(
            "sesso_form.html",
            {"cols": cols},
            request=request,
        )
        return Response.html(html)

    async def sesso_insert(request, datasette):
        if request.method != "POST":
            return Response.json({"ok": False, "error": "POST required"}, status=405)

        form = await request.post_vars()

        # Build allowed column set from schema (prevents inserting unexpected fields)
        cols = await _get_sesso_columns(datasette)
        allowed = {c["name"] for c in cols}

        # Drop csrftoken and empty values
        items = []
        for k, v in (form or {}).items():
            if k == "csrftoken":
                continue
            if k not in allowed:
                continue
            if v in (None, "", []):
                continue
            items.append((k, v))

        if not items:
            return Response.json({"ok": False, "error": "No data submitted"}, status=400)

        db = datasette.get_database()
        columns = ", ".join([k for k, _ in items])
        placeholders = ", ".join(["?"] * len(items))
        values = [v for _, v in items]

        await db.execute_write(
            f"INSERT INTO sesso ({columns}) VALUES ({placeholders})",
            values,
        )

        return Response.json({"ok": True})

    return [
        (r"^/sesso$", sesso_form),
        (r"^/sesso/insert$", sesso_insert),
    ]
