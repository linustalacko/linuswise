"""Local semantic embeddings via model2vec.

model2vec is a static-embedding model: a few hundred MB, runs on CPU in
milliseconds, no torch/onnxruntime. Embeddings are computed entirely on your
Mac and stored as float32 blobs on each highlight row. Retrieval is a brute-force
cosine over the whole library held in memory — instant for tens of thousands of
highlights, so no separate vector database is needed.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache

import numpy as np

DEFAULT_MODEL = "minishlab/potion-base-8M"


@lru_cache(maxsize=2)
def get_model(name: str = DEFAULT_MODEL):
    from model2vec import StaticModel  # imported lazily so core CLI starts fast

    return StaticModel.from_pretrained(name)


def _encode(model, texts: list[str]) -> np.ndarray:
    vecs = np.asarray(model.encode(texts), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms  # L2-normalised so dot product == cosine similarity


def embed_missing(
    conn: sqlite3.Connection, model_name: str = DEFAULT_MODEL, batch: int = 256
) -> int:
    """Compute and store embeddings for highlights that don't have one yet."""
    rows = conn.execute(
        "SELECT id, text FROM highlights WHERE discarded = 0 AND (embedding IS NULL OR embedding_model != ?)",
        (model_name,),
    ).fetchall()
    if not rows:
        return 0
    model = get_model(model_name)
    done = 0
    for start in range(0, len(rows), batch):
        chunk = rows[start : start + batch]
        vecs = _encode(model, [r["text"] for r in chunk])
        conn.executemany(
            "UPDATE highlights SET embedding = ?, embedding_model = ? WHERE id = ?",
            [(vecs[i].tobytes(), model_name, chunk[i]["id"]) for i in range(len(chunk))],
        )
        conn.commit()
        done += len(chunk)
    return done


def _load_matrix(conn: sqlite3.Connection, model_name: str):
    rows = conn.execute(
        "SELECT id, embedding FROM highlights WHERE discarded = 0 AND embedding IS NOT NULL AND embedding_model = ?",
        (model_name,),
    ).fetchall()
    if not rows:
        return [], None
    # Guard against malformed/wrong-length blobs (corrupt or hand-edited DB) so a
    # single bad row can't crash all of search.
    ids: list = []
    vecs: list = []
    dim: int | None = None
    for r in rows:
        buf = r["embedding"]
        if not buf or len(buf) % 4 != 0:
            continue
        v = np.frombuffer(buf, dtype=np.float32)
        if dim is None:
            dim = v.shape[0]
        if v.shape[0] != dim:
            continue
        ids.append(r["id"])
        vecs.append(v)
    if not vecs:
        return [], None
    return ids, np.vstack(vecs)


def search(
    conn: sqlite3.Connection, query: str, k: int = 10, model_name: str = DEFAULT_MODEL
) -> list[tuple[sqlite3.Row, float]]:
    """Return up to k (highlight_row, similarity) pairs most relevant to query."""
    ids, mat = _load_matrix(conn, model_name)
    if mat is None:
        return []
    qvec = _encode(get_model(model_name), [query])[0]
    scores = mat @ qvec
    top = np.argsort(scores)[::-1][:k]
    chosen_ids = [ids[i] for i in top]
    placeholders = ",".join("?" * len(chosen_ids))
    rows = {
        r["id"]: r
        for r in conn.execute(f"SELECT * FROM highlights WHERE id IN ({placeholders})", chosen_ids)
    }
    return [(rows[ids[i]], float(scores[i])) for i in top if ids[i] in rows]
