"""Render the daily review as an HTML email that echoes Readwise's layout.

Highlights are grouped by book. Each highlight is a left-bordered block with the
source title/author above it, the note (if any) below, and a small location
line — the same visual rhythm as Readwise's daily digest. CSS is inlined because
email clients strip <style> blocks.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date

from jinja2 import Environment, select_autoescape

# Monochrome, editorial, minimal. Every dimension is a multiple of 4px; hairline
# 1px rules are the one exception (a 4px rule reads as a bar). No location line.
_TEMPLATE = """\
<!doctype html>
<html>
<body style="margin:0;padding:0;background:#ffffff;color:#111111;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;">
    <tr><td align="center" style="padding:48px 16px;">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

        <tr><td style="padding:0 8px 24px 8px;border-bottom:1px solid #e5e5e5;">
          <div style="font-size:12px;line-height:16px;letter-spacing:4px;text-transform:uppercase;color:#999999;">Daily Review</div>
          <div style="font-size:24px;line-height:32px;font-weight:600;margin-top:8px;color:#111111;">{{ count }} highlight{{ '' if count == 1 else 's' }}</div>
          <div style="font-size:12px;line-height:16px;color:#999999;margin-top:4px;">{{ today }}</div>
        </td></tr>

        {% for book in books %}
        <tr><td style="padding:56px 8px 0 8px;">
          <div style="font-size:12px;line-height:16px;letter-spacing:4px;text-transform:uppercase;color:#111111;">{{ book.title }}</div>
          {% if book.author %}<div style="font-size:12px;line-height:16px;color:#999999;margin-top:4px;">{{ book.author }}</div>{% endif %}
        </td></tr>
          {% for h in book.highlights %}
          <tr><td style="padding:40px 8px 0 8px;">
            <div style="border-left:2px solid #111111;padding:0 0 0 20px;">
              <div style="font-family:Georgia,'Times New Roman',serif;font-size:20px;line-height:32px;color:#111111;">{{ h.text }}</div>
              {% if h.note %}
              <div style="margin-top:12px;font-size:12px;line-height:20px;color:#666666;">— {{ h.note }}</div>
              {% endif %}
            </div>
          </td></tr>
          {% endfor %}
        {% endfor %}

        <tr><td style="padding:48px 8px 0 8px;">
          <div style="border-top:1px solid #e5e5e5;padding-top:16px;font-size:12px;line-height:16px;color:#bbbbbb;">{{ total_known }} highlights in your library</div>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

_env = Environment(autoescape=select_autoescape(["html", "xml"]))
_tmpl = _env.from_string(_TEMPLATE)


def render(rows, total_known: int, today: str | None = None) -> str:
    """rows: sequence of sqlite Rows (or dict-likes) for the chosen highlights."""
    grouped: OrderedDict[tuple, dict] = OrderedDict()
    for r in rows:
        key = (r["source_title"], r["source_author"])
        if key not in grouped:
            grouped[key] = {
                "title": r["source_title"],
                "author": r["source_author"],
                "highlights": [],
            }
        grouped[key]["highlights"].append(
            {"text": r["text"], "note": r["note"], "location": r["location"]}
        )

    return _tmpl.render(
        count=len(rows),
        today=today or date.today().strftime("%A, %B %-d, %Y"),
        books=list(grouped.values()),
        total_known=total_known,
    )
