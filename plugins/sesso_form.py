# Version: 1.14
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from datasette import hookimpl
from datasette.utils.asgi import Response
from datasette.database import Database


DB_FILE_BASENAME = "cassaforte"
TABLE = "sesso"
PORT_HINT = 8015


def _safe_json_loads(s: Optional[str]) -> Dict[str, Any]:
    if not s:
        return {}
    s = s.strip()
    # tolerate the common missing closing brace seen in this DB
    if s and (s.startswith("{") and not s.endswith("}")):
        s = s + "}"
    try:
        return json.loads(s)
    except Exception:
        return {}


def _format_dt_for_storage(value: str) -> str:
    """
    Convert HTML datetime-local 'YYYY-MM-DDTHH:MM' to 'YYYY-MM-DD HH:MM'.
    If it's already in a reasonable format, return it unchanged.
    """
    if not value:
        return value
    v = value.strip()
    if "T" in v and len(v) >= 16:
        try:
            dt = datetime.strptime(v[:16], "%Y-%m-%dT%H:%M")
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return v.replace("T", " ")
    return v


async def _get_db(datasette) -> Database:
    return datasette.get_database(DB_FILE_BASENAME)


async def _fetchall(db: Database, sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
    results = await db.execute(sql, params)
    return list(results.rows)


async def _get_sesso_field_defs(datasette) -> List[Dict[str, Any]]:
    """
    Returns a list of field definitions for the 'sesso' form.
    The DB meta_* tables are the only source of truth.
    """
    db = await _get_db(datasette)

    # Map table name -> table_id
    table_id_rows = await _fetchall(
        db,
        "select id from meta_registry_tables where name = ?",
        (TABLE,),
    )
    if not table_id_rows:
        raise RuntimeError(f"meta_registry_tables has no entry for table '{TABLE}'")
    table_id = table_id_rows[0]["id"]

    # Registry columns for the table
    reg_cols = await _fetchall(
        db,
        "select id, name from meta_registry_columns where table_id = ? order by id",
        (table_id,),
    )

    # Column_id -> (type_key, nullable, notes)
    col_type_rows = await _fetchall(
        db,
        "select column_id, type_key, nullable, notes from meta_column_type",
    )
    col_type = {r["column_id"]: dict(r) for r in col_type_rows}

    # Type_key -> meta (widget, display_format, defaults, options_json)
    type_rows = await _fetchall(
        db,
        """select type_key, ui_widget, display_format, default_mode, default_value, default_expr, options_json
           from meta_type_registry""",
    )
    type_meta = {r["type_key"]: dict(r) for r in type_rows}

    # FK map for sesso (from_col -> ref_table)
    fk_rows = await _fetchall(db, "pragma foreign_key_list(sesso)")
    fk_map = {r["from"]: r["table"] for r in fk_rows}

    # pragma table_info for real column ordering + to skip id
    tinfo = await _fetchall(db, "pragma table_info(sesso)")
    ordered_cols = [r["name"] for r in tinfo if r["name"] != "id"]

    reg_by_name = {r["name"]: r for r in reg_cols}

    fields: List[Dict[str, Any]] = []
    for col_name in ordered_cols:
        reg = reg_by_name.get(col_name)
        # If a column exists in the table but is not registered, we still include it
        # (unless it's id) but mark as "fallback".
        reg_id = reg["id"] if reg else None

        meta = col_type.get(reg_id, {}) if reg_id is not None else {}
        type_key = meta.get("type_key") or ("int" if col_name.endswith("_id") else "text")
        nullable = bool(meta.get("nullable", 1))
        notes = meta.get("notes")

        tmeta = type_meta.get(type_key, {})
        ui_widget = tmeta.get("ui_widget") or "input_text"
        display_format = tmeta.get("display_format") or "plain"
        default_mode = tmeta.get("default_mode") or "none"
        default_value = tmeta.get("default_value")
        default_expr = tmeta.get("default_expr")
        options = _safe_json_loads(tmeta.get("options_json"))

        field: Dict[str, Any] = {
            "name": col_name,
            "type_key": type_key,
            "ui_widget": ui_widget,
            "display_format": display_format,
            "nullable": nullable,
            "notes": notes,
            "default_mode": default_mode,
            "default_value": default_value,
            "default_expr": default_expr,
            "options": options,
            "ref_table": fk_map.get(col_name),
            "choices": [],
        }

        # Build choices for selects (fk or single_choice)
        if ui_widget in ("select", "multi_select") or type_key in ("fk", "single_choice", "multiple_choice"):
            ref_table = field["ref_table"]
            if ref_table:
                # Determine a label expression: prefer columns named like nome/title/label; else first TEXT column; else id.
                ref_cols = await _fetchall(db, f"pragma table_info({ref_table})")
                ref_col_names = [c["name"] for c in ref_cols]
                label_col = None
                for candidate in ("nome", "name", "titolo", "title", "label", "indirizzo", "nick", "cognome"):
                    if candidate in ref_col_names:
                        label_col = candidate
                        break
                if not label_col:
                    # pick first non-id TEXT column
                    for c in ref_cols:
                        if c["name"] == "id":
                            continue
                        if (c["type"] or "").upper() in ("TEXT", "VARCHAR", "CHAR"):
                            label_col = c["name"]
                            break
                if not label_col and ref_table == "persona":
                    # Construct a more helpful label if possible
                    if "nome" in ref_col_names and "cognome" in ref_col_names:
                        label_expr = "trim(coalesce(nome,'') || ' ' || coalesce(cognome,''))"
                    elif "nick" in ref_col_names:
                        label_expr = "coalesce(nick, cast(id as text))"
                    else:
                        label_expr = "cast(id as text)"
                elif not label_col and ref_table == "luogo":
                    if "nome" in ref_col_names and "indirizzo" in ref_col_names:
                        label_expr = "coalesce(nome, indirizzo, cast(id as text))"
                    elif "nome" in ref_col_names:
                        label_expr = "coalesce(nome, cast(id as text))"
                    else:
                        label_expr = "cast(id as text)"
                else:
                    label_expr = f"coalesce({label_col}, cast(id as text))" if label_col else "cast(id as text)"

                # Fetch up to 500 options
                rows = await _fetchall(
                    db,
                    f"select id as value, {label_expr} as label from {ref_table} order by id limit 500"
                )
                field["choices"] = [{"value": r["value"], "label": r["label"]} for r in rows]
            else:
                field["choices"] = []

        fields.append(field)

    return fields


@hookimpl
def register_routes():
    return [
        (r"^/sesso$", sesso_page),
        (r"^/-/sesso/insert$", sesso_insert),
    ]


async def sesso_page(request, datasette):
    try:
        fields = await _get_sesso_field_defs(datasette)
    except Exception as e:
        return Response.text(f"Error building form: {e}", status=500)

    # Render using templates/sesso.html
    html = await datasette.render_template(
        "sesso.html",
        {
            "db_name": DB_FILE_BASENAME,
            "table": TABLE,
            "fields": fields,
        },
        request=request,
    )
    return Response.html(html)


async def sesso_insert(request, datasette):
    if request.method != "POST":
        return Response.json({"ok": False, "error": "POST required"}, status=405)

    form = await request.post_vars()

    # CSRF protection: Datasette's internal API differs across versions.
    # We validate the token generated by {{ csrftoken() }} against the CSRF cookie set by Datasette.
    form_token = str(form.get("csrftoken") or "").strip()

    # Datasette sets a CSRF cookie; name has varied across setups. We accept common names.
    cookies = getattr(request, "cookies", {}) or {}
    cookie_token = (
        cookies.get("ds_csrftoken")
        or cookies.get("csrftoken")
        or cookies.get("csrftoken_d")
        or ""
    )
    cookie_token = str(cookie_token).strip()

    # If either side is missing, we allow (tailnet/private deployment). If both exist, they must match.
    if form_token and cookie_token and form_token != cookie_token:
        return Response.json({"ok": False, "error": "csrf: invalid token"}, status=403)

    try:
        fields = await _get_sesso_field_defs(datasette)
    except Exception as e:
        return Response.json({"ok": False, "error": f"form meta error: {e}"}, status=500)

    # Build insert dict
    values: Dict[str, Any] = {}
    for f in fields:
        name = f["name"]
        t = f["type_key"]
        widget = f["ui_widget"]

        if t == "boolean" or widget == "checkbox":
            # unchecked checkboxes won't be present in form
            values[name] = 1 if str(form.get(name, "")).lower() in ("1", "true", "on", "yes") else 0
            continue

        v = form.get(name)
        if v is None or str(v).strip() == "":
            # If nullable, store NULL; otherwise store empty string/0 depending on type
            if f["nullable"]:
                values[name] = None
            else:
                if t in ("int", "real", "fk", "single_choice", "multiple_choice"):
                    values[name] = 0
                else:
                    values[name] = ""
            continue

        v_str = str(v).strip()

        if t == "date_time" or widget == "datetime_picker":
            values[name] = _format_dt_for_storage(v_str)
        elif t == "date" or widget == "date_picker":
            values[name] = v_str  # store as-is (YYYY-MM-DD)
        elif t in ("int", "fk", "single_choice"):
            try:
                values[name] = int(v_str)
            except Exception:
                values[name] = None
        elif t == "real":
            try:
                values[name] = float(v_str)
            except Exception:
                values[name] = None
        else:
            values[name] = v_str

    cols = list(values.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"insert into {TABLE} ({', '.join(cols)}) values ({placeholders})"

    db = await _get_db(datasette)
    try:
        await db.execute_write(sql, tuple(values[c] for c in cols))
        # fetch last row id
        row = await db.execute("select last_insert_rowid() as id")
        new_id = row.first()["id"] if row else None

        # If this was a normal browser form POST, redirect to the table (as requested).
        accept = (request.headers.get("accept") or "").lower()
        if "text/html" in accept and "application/json" not in accept:
            return Response.redirect(f"/{DB_FILE_BASENAME}/{TABLE}?_sort_desc=id")

        return Response.json({"ok": True, "id": new_id, "db_name": DB_FILE_BASENAME, "table": TABLE})
    except Exception as e:
        return Response.json({"ok": False, "error": str(e)}, status=500)