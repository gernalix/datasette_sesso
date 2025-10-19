from datasette import hookimpl
from markupsafe import Markup
from datetime import datetime, date

ARROW_HTML = "&#10145;"  # ➡️

# Colonne HTML (già contenenti <a ...>) nella view sex_v
HTML_COLUMNS_BY_TABLE = {
    "sex_v": {"partner", "interrotto", "luogo", "dove_sborra", "come_viene"}
}
HTML_COLUMNS_FALLBACK = set().union(*HTML_COLUMNS_BY_TABLE.values()) if HTML_COLUMNS_BY_TABLE else set()

# Nomi di colonne che nel tuo schema sono booleani (0/1) anche se il tipo DB non è BOOLEAN
BOOLEAN_NAMES_HINT = {
    "droghe_offerte", "overdose", "mia_iniz", "video", "audio",
    "lui_succhia", "io_scopo", "io_succhio", "lui_scopa", "bb",
    "record", "lube", "dom", "dolore", "chiacchiere", "kink",
    "viene_sega", "completo", "fuori", "cruising"
}

_DT_PATTERNS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M%z",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)
_DATE_PATTERNS = ("%Y-%m-%d",)


def _is_anchor_html(val: str) -> bool:
    s = val.lstrip().lower()
    return s.startswith("<a ") and ("href=" in s)


def _parse_dt(value: str):
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(v)
    except Exception:
        pass
    for pat in _DT_PATTERNS:
        try:
            return datetime.strptime(v, pat)
        except Exception:
            continue
    for pat in _DATE_PATTERNS:
        try:
            d = datetime.strptime(v, pat).date()
            return datetime.combine(d, datetime.min.time())
        except Exception:
            continue
    return None


def _format_dt_ddmmyy_hhmm(dt: datetime) -> str:
    return dt.strftime("%d-%m-%y %H:%M")


def _as_boolish(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "t", "yes", "y"):
            return True
        if v in ("0", "false", "f", "no", "n", ""):
            return False
    return None


def _is_bool_column(column: str, table: str | None, database: str, datasette) -> bool:
    if not column:
        return False
    name = column.lower()
    if name.endswith("_id"):
        return False
    try:
        info = datasette.inspect().get(database, {}).get("tables", {}).get(table or "", {})
        col_types = {c["name"]: (c.get("type") or "").upper() for c in info.get("columns", [])}
        t = col_types.get(column, "")
        if "BOOL" in t:
            return True
        if t in ("", "INT", "INTEGER", "TINYINT", "SMALLINT", "BIT"):
            if name in BOOLEAN_NAMES_HINT or name.startswith(("is_", "has_", "can_", "flag_", "bool_", "do_", "did_")):
                return True
    except Exception:
        pass
    return name in BOOLEAN_NAMES_HINT


@hookimpl
def render_cell(value, column, table, database, datasette):
    # 1) Rendi sicuri gli <a ...> per tabelle note (pagina tabellare)
    if table in HTML_COLUMNS_BY_TABLE and column in HTML_COLUMNS_BY_TABLE[table]:
        if isinstance(value, str) and _is_anchor_html(value):
            return Markup(value)

    # 2) <a ...> anche in risultati Custom SQL (table is None)
    if table is None and column in HTML_COLUMNS_FALLBACK:
        if isinstance(value, str) and _is_anchor_html(value):
            return Markup(value)

    # 3) Icona ➡️ su colonna link_icon (URL assoluto/relativo)
    if (table == "sex_v" or table is None) and column == "link_icon":
        if isinstance(value, str) and value:
            return Markup(f'<a href="{value}" target="_blank" rel="noopener">{ARROW_HTML}</a>')

    # 4) Booleani → ✅ / ""  (supporta int, bool, stringhe; evita *_id e numeri reali)
    if _is_bool_column(column or "", table, database, datasette):
        b = _as_boolish(value)
        if b is not None:
            return "✅" if b else ""

    # 5) Date/Datetime → dd-mm-yy hh:mm  (solo rendering, sorting intatto)
    if isinstance(value, (datetime, date)):
        dt = value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time())
        return _format_dt_ddmmyy_hhmm(dt)
    if isinstance(value, str):
        dt = _parse_dt(value)
        if dt is not None:
            return _format_dt_ddmmyy_hhmm(dt)

    return None
