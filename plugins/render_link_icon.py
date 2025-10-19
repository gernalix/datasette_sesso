from datasette import hookimpl
from markupsafe import Markup

@hookimpl
def render_cell(value, column, table, database, datasette):
    # Se la colonna è 'url' o 'link', mostra l'icona
    if column in ("url", "link") and isinstance(value, str) and value:
        return Markup(f'<a href="{value}" target="_blank" rel="noopener">➡️</a>')
    return None
