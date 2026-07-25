"""Pure vector maths. No IO, fully unit-testable."""

from __future__ import annotations

import re

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9ऀ-ॿ஀-௿]+")
_STOPWORDS = frozenset(
    """a an the and or but if while of to in on for with without from by at as is are was were be been
    this that these those it its his her their our your my he she they we you i not no so than then""".split()
)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def content_tokens(text: str) -> list[str]:
    return [token for token in tokenize(text) if token not in _STOPWORDS and len(token) > 2]


def normalize(vector: list[float] | np.ndarray) -> list[float]:
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        return array.tolist()
    return (array / norm).tolist()


def cosine(left: list[float], right: list[float]) -> float:
    """Raw cosine similarity clamped to [0, 1].

    Deliberately clamped rather than rescaled from [-1,1]. Modern text embeddings are
    almost never negatively correlated — unrelated passages sit around 0.1-0.25 raw.
    Rescaling with (raw+1)/2 maps that band to 0.55-0.62 and pushes genuinely similar
    pairs to 0.85+, which collapses the gap between 'unrelated' and 'duplicate' and
    makes every threshold in the system meaningless. Clamping keeps the scale
    interpretable: ~0.15 unrelated, ~0.6 related, >0.9 duplicate.

    Returns 0.0 for missing or mismatched vectors.
    """
    if not left or not right or len(left) != len(right):
        return 0.0
    a = np.asarray(left, dtype=np.float32)
    b = np.asarray(right, dtype=np.float32)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0.0:
        return 0.0
    return round(max(0.0, min(1.0, float(np.dot(a, b) / denominator))), 6)


def cosine_matrix(query: list[float], matrix: np.ndarray) -> np.ndarray:
    """Vectorised counterpart of `cosine` against a stacked (n, d) matrix."""
    if matrix.size == 0 or not query:
        return np.zeros(matrix.shape[0] if matrix.ndim == 2 else 0, dtype=np.float32)
    q = np.asarray(query, dtype=np.float32)
    q_norm = float(np.linalg.norm(q)) or 1.0
    row_norms = np.linalg.norm(matrix, axis=1)
    row_norms[row_norms == 0.0] = 1.0
    raw = (matrix @ q) / (row_norms * q_norm)
    return np.clip(raw, 0.0, 1.0).astype(np.float32)


def weighted_mean(vectors: list[list[float]], weights: list[float]) -> list[float]:
    """L2-normalised weighted centroid. Negative weights push the centroid away."""
    usable = [(v, w) for v, w in zip(vectors, weights) if v]
    if not usable:
        return []
    dimensions = len(usable[0][0])
    matrix = np.asarray([v for v, _ in usable if len(v) == dimensions], dtype=np.float32)
    weight_array = np.asarray([w for v, w in usable if len(v) == dimensions], dtype=np.float32)
    if matrix.size == 0 or float(np.abs(weight_array).sum()) == 0.0:
        return []
    centroid = (matrix * weight_array[:, None]).sum(axis=0) / float(np.abs(weight_array).sum())
    return normalize(centroid)


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left | right)
    return round(len(left & right) / union, 6) if union else 0.0


def shingles(text: str, size: int = 5) -> set[str]:
    """Word-level n-gram shingles — the standard near-duplicate detector for prose."""
    words = content_tokens(text)
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[index : index + size]) for index in range(len(words) - size + 1)}


def softmax_normalise(scores: dict[str, float], temperature: float = 1.0) -> dict[str, float]:
    """Turn signed affinity sums into a probability-like distribution that sums to 1."""
    if not scores:
        return {}
    keys = list(scores)
    values = np.asarray([scores[key] for key in keys], dtype=np.float32) / max(temperature, 1e-6)
    values = values - values.max()
    exponentials = np.exp(values)
    total = float(exponentials.sum()) or 1.0
    return {key: round(float(value / total), 6) for key, value in zip(keys, exponentials)}


def minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    array = np.asarray(values, dtype=np.float32)
    low, high = float(array.min()), float(array.max())
    if high - low < 1e-9:
        return [0.5] * len(values)
    return ((array - low) / (high - low)).tolist()
