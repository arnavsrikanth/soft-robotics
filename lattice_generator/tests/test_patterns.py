from collections import defaultdict
import numpy as np
import pytest

from lattice_generator.patterns import motif, segments


@pytest.mark.parametrize("pattern,degree,length", [
    ("cubic", 6, 1), ("bcc", 8, np.sqrt(3)/2), ("octet", 12, 1/np.sqrt(2)),
    ("diamond", 4, np.sqrt(3)/4), ("kelvin", 4, np.sqrt(2)/4),
])
def test_exact_graph_geometry(pattern, degree, length):
    edges = segments(pattern, (3, 3, 3), 1)
    assert np.allclose(np.linalg.norm(edges[:, 1] - edges[:, 0], axis=1), length)
    graph = defaultdict(set)
    for a, b in edges:
        graph[tuple(a)].add(tuple(b))
        graph[tuple(b)].add(tuple(a))
    interior = [p for p in graph if all(0 < c < 3 for c in p)]
    assert interior
    assert all(len(graph[p]) == degree for p in interior)
    canonical = {tuple(sorted((tuple(a), tuple(b)))) for a, b in edges}
    assert len(canonical) == len(edges)
    # Cubic translations preserve topology, including edges crossing cell boundaries.
    for p in interior:
        q = (p[0] + 1, p[1], p[2])
        if q in interior:
            assert {tuple(np.array(n) + (1, 0, 0)) for n in graph[p]} == graph[q]


def test_kelvin_cell_is_truncated_octahedron():
    edges = motif("kelvin")[:36]
    vertices, degree = np.unique(edges.reshape(-1, 3), axis=0, return_counts=True)
    assert len(vertices) == 24
    assert np.all(degree == 3)
    # Six square support planes and eight hexagonal support planes.
    assert all(np.count_nonzero(vertices[:, i] == s*2) == 4 for i in range(3) for s in (-1, 1))
    from itertools import product
    assert all(np.count_nonzero(vertices @ np.array(s) == 3) == 6 for s in product((-1, 1), repeat=3))
