"""Shared offline embedding model — ONE small local model for the whole app.

`all-MiniLM-L6-v2` (~22M params, far smaller than an 8B LLM) runs on CPU with no API call. Loaded once
and cached module-level, so the eval response-similarity scorer and the (designed) business-context
vector retrieval share a single download and a single in-memory instance — not several.

sentence-transformers is imported lazily inside `_model()`, so importing this module (or anything that
imports it, like the eval scorer) stays cheap until an embedding is actually needed.
"""
_MODEL = None
MODEL_NAME = 'all-MiniLM-L6-v2'


def _model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def embed(texts):
    """L2-normalized embedding(s) for a string or list of strings. A single string returns one
    vector; a list returns a 2-D array (one row per text)."""
    single = isinstance(texts, str)
    vecs = _model().encode([texts] if single else list(texts), normalize_embeddings=True)
    return vecs[0] if single else vecs


def similarity(a:str, b:str) -> float:
    """Cosine similarity in [-1, 1] between two texts. Embeddings are L2-normalized, so the cosine is
    just their dot product."""
    import numpy as np
    va, vb = embed([a, b])
    return float(np.dot(va, vb))
