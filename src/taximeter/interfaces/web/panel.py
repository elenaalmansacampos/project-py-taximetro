from __future__ import annotations

from datetime import datetime
from html import escape

from taximeter.application.ports import HistoryEntry


PAGE_TITLE = "Historial de carreras"
PANEL_HEADING = "Historial de carreras"
EMPTY_MESSAGE = "Todavia no hay carreras registradas."
ERROR_HEADING = "No se pudo consultar el historial"
ERROR_MESSAGE = (
    "No se pudo obtener el historial de carreras. "
    "Comprueba que el servicio sigue en marcha y vuelve a recargar la pagina."
)
TABLE_CAPTION = "Carreras registradas, de la mas reciente a la mas antigua."

STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2rem 1.5rem;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  line-height: 1.5;
  background: #f4f5f7;
  color: #1b1f24;
}
main { max-width: 60rem; margin: 0 auto; }
h1 { font-size: 1.75rem; margin: 0 0 1.5rem; }
table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
  border-radius: 0.5rem;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}
caption {
  caption-side: top;
  text-align: left;
  padding: 0 0 0.5rem;
  color: #4a5260;
  font-size: 0.95rem;
}
th, td { padding: 0.85rem 1rem; text-align: left; }
thead th {
  background: #1f2a37;
  color: #ffffff;
  font-size: 1rem;
  letter-spacing: 0.02em;
}
tbody tr:nth-child(even) { background: #f8f9fa; }
tbody tr + tr td { border-top: 1px solid #e3e6ea; }
td.amount { text-align: right; font-variant-numeric: tabular-nums; }
td.duration { font-variant-numeric: tabular-nums; }
.notice {
  background: #ffffff;
  border: 1px solid #d7dbe0;
  border-left: 0.35rem solid #6b7280;
  border-radius: 0.5rem;
  padding: 1.25rem 1.5rem;
}
.notice p { margin: 0.35rem 0 0; color: #4a5260; }
.notice.error { border-left-color: #b42318; }
footer { margin-top: 1.5rem; color: #6b7280; font-size: 0.9rem; }
@media (prefers-color-scheme: dark) {
  body { background: #14181d; color: #e8eaed; }
  table { background: #1c2128; box-shadow: none; }
  thead th { background: #2b3644; }
  tbody tr:nth-child(even) { background: #21272f; }
  tbody tr + tr td { border-top-color: #2f3742; }
  .notice { background: #1c2128; border-color: #2f3742; }
  .notice p, footer, caption { color: #a9b1bd; }
}
"""


def format_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def format_duration(seconds: float) -> str:
    total = int(round(float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {secs} s"
    return f"{secs} s"


def format_amount(amount: float) -> str:
    return f"{float(amount):.2f} EUR"


def render_panel(entries: list[HistoryEntry]) -> str:
    if not entries:
        return _layout(
            PANEL_HEADING,
            f'<section class="notice"><p>{escape(EMPTY_MESSAGE)}</p></section>',
        )
    return _layout(PANEL_HEADING, _table(entries))


def render_error() -> str:
    body = (
        f'<section class="notice error">'
        f"<h2>{escape(ERROR_HEADING)}</h2>"
        f"<p>{escape(ERROR_MESSAGE)}</p>"
        f"</section>"
    )
    return _layout(ERROR_HEADING, body)


def _table(entries: list[HistoryEntry]) -> str:
    rows = "\n".join(
        "<tr>"
        f'<td class="date">{escape(format_date(entry.date))}</td>'
        f'<td class="duration">{escape(format_duration(entry.duration_seconds))}</td>'
        f'<td class="amount">{escape(format_amount(entry.amount))}</td>'
        "</tr>"
        for entry in entries
    )
    return (
        "<table>"
        f"<caption>{escape(TABLE_CAPTION)}</caption>"
        "<thead><tr>"
        '<th scope="col">Fecha</th>'
        '<th scope="col">Duración</th>'
        '<th scope="col">Importe</th>'
        "</tr></thead>"
        f"<tbody>\n{rows}\n</tbody>"
        "</table>"
    )


def _layout(heading: str, body: str) -> str:
    return (
        "<!DOCTYPE html>"
        '<html lang="es">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(PAGE_TITLE)} | TaxiTech Solutions</title>"
        f"<style>{STYLE}</style>"
        "</head>"
        "<body><main>"
        f"<h1>{escape(heading)}</h1>"
        f"{body}"
        "<footer>TaxiTech Solutions · Taximetro digital</footer>"
        "</main></body></html>"
    )
