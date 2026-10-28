"""Exact quarter-cell integer graphs; coordinates are scaled only at the end."""

from itertools import combinations, permutations, product
import math
import numpy as np

DESCRIPTIONS = {
    "cubic": "Cube edges; cell-size is the cube side.",
    "bcc": "Body center to eight corners; cell-size is the conventional cube side.",
    "octet": "FCC nearest-neighbor graph; cell-size is the conventional cubic repeat.",
    "diamond": "Four-connected diamond-cubic graph; cell-size is the conventional cubic repeat.",
    "kelvin": "BCC Voronoi cell edges; cell-size is the conventional BCC cubic repeat (two cells).",
    "gyroid": "Thickened trigonometric gyroid sheet; cell-size is one period along each axis.",
}

# Fixed offsets in conventional-cell fractions, measured from the box origin.
# These are documented alignments, not automatic per-output phase adjustments.
PHASES = {name: (0.0, 0.0, 0.0) for name in DESCRIPTIONS}
PHASES["diamond"] = (0.25, 0.0, 0.0)
PHASES["gyroid"] = (0.25, 0.0, 0.0)


def motif(pattern):
    """Return segment endpoints in units of cell_size/4."""
    fcc = [(0, 0, 0), (0, 2, 2), (2, 0, 2), (2, 2, 0)]
    if pattern == "cubic":
        return np.array([[(0, 0, 0), p] for p in [(4, 0, 0), (0, 4, 0), (0, 0, 4)]], dtype=np.int64)
    if pattern == "bcc":
        return np.array([[(2, 2, 2), p] for p in product((0, 4), repeat=3)], dtype=np.int64)
    if pattern == "octet":
        offsets = sorted(set(p for a, b in product((-2, 2), repeat=2) for p in permutations((0, a, b))))
        return np.array([[p, tuple(np.array(p) + d)] for p in fcc for d in offsets], dtype=np.int64)
    if pattern == "diamond":
        offsets = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
        return np.array([[p, tuple(np.array(p) + d)] for p in fcc for d in offsets], dtype=np.int64)
    if pattern == "kelvin":
        vertices = sorted(set(p for a, b in product((-1, 1), (-2, 2)) for p in permutations((0, a, b))))
        edges = [(a, b) for a, b in combinations(vertices, 2) if sum((x-y)**2 for x,y in zip(a,b)) == 2]
        return np.array([[np.array(a) + c, np.array(b) + c] for c in [(0, 0, 0), (2, 2, 2)] for a,b in edges], dtype=np.int64)
    raise ValueError(f"No strut motif for {pattern!r}")


def segments(pattern, size, cell_size, radius=0.0):
    """Unique undirected edges, including neighbors whose rounded struts enter the box."""
    template = motif(pattern)
    scale = cell_size / 4
    shift = np.array(PHASES[pattern]) * cell_size
    lower = (-radius - shift) / scale
    upper = (np.array(size) + radius - shift) / scale
    ranges = [range(math.floor(-radius / cell_size) - 1, math.ceil((s + radius) / cell_size) + 2) for s in size]
    edges = set()
    for ijk in product(*ranges):
        block = template + 4 * np.array(ijk)
        keep = np.all(block.max(axis=1) >= lower, axis=1) & np.all(block.min(axis=1) <= upper, axis=1)
        for edge in block[keep]:
            a, b = tuple(edge[0]), tuple(edge[1])
            edges.add((a, b) if a < b else (b, a))
    if not edges:
        return np.empty((0, 2, 3), dtype=np.float64)
    return np.array(sorted(edges), dtype=np.float64) * scale + shift
