"""Hybrid retrieval: vector + trigram keyword search over every query variant, fused with RRF."""
from dataclasses import dataclass

import numpy as np

from . import db
from .embed import embed
from .georgian import normalize, query_variants


@dataclass
class Hit:
    chunk_id: int
    document_id: str
    filename: str
    page: int
    text: str
    score: float


_VECTOR_SQL = """
SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE d.owner_id = %(owner)s AND d.status = 'ready'
ORDER BY c.embedding <=> %(vec)s LIMIT %(k)s
"""

# Georgian has no Postgres stemmer and stacks suffixes (ხელშეკრულება / ხელშეკრულების / ხელშეკრულებაში),
# so keyword matching uses trigram word similarity per query term instead of full-text search.
_KEYWORD_SQL = """
SELECT c.id, sum(word_similarity(t, c.norm)) AS score
FROM chunks c JOIN documents d ON d.id = c.document_id, unnest(%(terms)s::text[]) AS t
WHERE d.owner_id = %(owner)s AND d.status = 'ready'
GROUP BY c.id HAVING max(word_similarity(t, c.norm)) >= 0.5
ORDER BY score DESC LIMIT %(k)s
"""


def _rrf(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def search(owner_id: str, query: str, top_k: int = 6, per_list: int = 20) -> list[Hit]:
    variants = [normalize(v) for v in query_variants(query)]
    vectors = embed(variants)
    rankings: list[list[int]] = []
    with db.conn() as c:
        for variant, vec in zip(variants, vectors):
            rows = c.execute(_VECTOR_SQL, {"owner": owner_id, "vec": np.array(vec), "k": per_list}).fetchall()
            rankings.append([r["id"] for r in rows])
            terms = [t for t in variant.split() if len(t) >= 3]
            if terms:
                rows = c.execute(_KEYWORD_SQL, {"owner": owner_id, "terms": terms, "k": per_list}).fetchall()
                rankings.append([r["id"] for r in rows])
        fused = sorted(_rrf(rankings).items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        if not fused:
            return []
        rows = c.execute(
            "SELECT c.id, c.document_id, d.filename, c.page, c.text FROM chunks c "
            "JOIN documents d ON d.id = c.document_id WHERE c.id = ANY(%s)",
            ([cid for cid, _ in fused],),
        ).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [
        Hit(cid, str(by_id[cid]["document_id"]), by_id[cid]["filename"], by_id[cid]["page"], by_id[cid]["text"], score)
        for cid, score in fused if cid in by_id
    ]
