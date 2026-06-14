"""Extract highlighted text from a PDF's annotations.

Works with PDFs you highlighted anywhere — Preview, Skim, PDF Expert, etc. We
read the PDF's highlight annotations and pull out the text sitting underneath
each one, plus any note text the annotation carries.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from ..models import Highlight, clean_author, clean_title

_HIGHLIGHT_TYPE = 8  # PDF annotation subtype "Highlight"


def _text_under(page: fitz.Page, annot: fitz.Annot) -> str:
    """Reconstruct the highlighted text from the annotation's quad points.

    A highlight stores 4 points per covered line ("quad"). We extract the text
    inside each quad's bounding rect and join them. Falls back to the whole
    annotation rect if quad points are missing.
    """
    verts = annot.vertices
    if not verts:
        return page.get_textbox(annot.rect).strip()

    chunks: list[str] = []
    for i in range(0, len(verts), 4):
        quad_pts = verts[i : i + 4]
        if len(quad_pts) != 4:
            continue
        rect = fitz.Quad(quad_pts).rect
        chunk = page.get_textbox(rect).strip()
        if chunk:
            chunks.append(chunk)
    return " ".join(chunks).strip()


def parse(path: str | Path) -> list[Highlight]:
    path = Path(path)
    doc = fitz.open(path)
    meta = doc.metadata or {}
    title = clean_title((meta.get("title") or "").strip() or path.stem)
    author = clean_author(meta.get("author"))

    results: list[Highlight] = []
    for page in doc:
        annot = page.first_annot
        while annot:
            if annot.type[0] == _HIGHLIGHT_TYPE:
                text = _text_under(page, annot)
                note = (annot.info.get("content") or "").strip() or None
                if text:
                    results.append(
                        Highlight(
                            text=text,
                            source_title=title,
                            source_author=author,
                            source_type="pdf",
                            note=note,
                            location=f"page {page.number + 1}",
                        )
                    )
            annot = annot.next
    doc.close()
    return results
