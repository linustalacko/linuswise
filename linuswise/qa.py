"""Ask questions about your highlights — retrieval-augmented, answered by Groq.

Flow: embed the question locally → cosine-retrieve the most relevant highlights →
hand only those snippets to Groq to write a cited answer. Your library never
leaves the machine wholesale; only the handful of retrieved highlights for a
given question are sent at query time.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from . import embeddings

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

_SYSTEM = (
    "You answer the user's question using ONLY the highlights they have saved "
    "from their reading, provided below as numbered sources. Synthesise across "
    "them and cite the ones you use inline like [1], [2]. If the highlights do "
    "not contain the answer, say so plainly rather than inventing one. Be concise."
)


@dataclass
class Answer:
    text: str
    sources: list  # list of sqlite Rows used as context


def _api_key(explicit: str = "") -> str:
    key = explicit or os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError(
            "No Groq API key. Set GROQ_API_KEY (e.g. in ~/.config/linuswise/secrets.env) "
            "or groq_api_key in config."
        )
    return key


def ask(
    conn: sqlite3.Connection,
    question: str,
    *,
    k: int = 10,
    model: str = DEFAULT_GROQ_MODEL,
    api_key: str = "",
    embed_model: str = embeddings.DEFAULT_MODEL,
) -> Answer:
    hits = embeddings.search(conn, question, k=k, model_name=embed_model)
    if not hits:
        return Answer(
            text="No highlights are embedded yet — run `linuswise embed` first.",
            sources=[],
        )

    rows = [r for r, _ in hits]
    context = "\n\n".join(
        f'[{i + 1}] "{r["text"]}" — {r["source_title"]}'
        + (f", {r['source_author']}" if r["source_author"] else "")
        + (f" (note: {r['note']})" if r["note"] else "")
        for i, r in enumerate(rows)
    )

    from groq import Groq

    client = Groq(api_key=_api_key(api_key))
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Highlights:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0.2,
    )
    return Answer(text=resp.choices[0].message.content.strip(), sources=rows)
