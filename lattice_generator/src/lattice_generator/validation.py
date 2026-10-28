"""Validate the surface without silently repairing or dropping components."""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import trimesh

from .config import LatticeError


def topology(mesh):
    """Check edge incidence, vertex links, and face-connected shells in bulk.

    A triangle corner is a node in its vertex's link. Across each two-sided
    edge, connect the corresponding corners. A manifold vertex has one link
    component, not two or more fans meeting at a single point.
    """
    faces = np.asarray(mesh.faces)
    corner = np.arange(faces.size).reshape(-1, 3)
    edges = np.stack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=1).reshape(-1, 2)
    corners = np.stack((corner[:, [0, 1]], corner[:, [1, 2]], corner[:, [2, 0]]), axis=1).reshape(-1, 2)
    reverse = edges[:, 0] > edges[:, 1]
    edges[reverse] = edges[reverse, ::-1]
    corners[reverse] = corners[reverse, ::-1]
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    sorted_edges = edges[order]
    starts = np.r_[0, 1 + np.flatnonzero(np.any(np.diff(sorted_edges, axis=0), axis=1))]
    counts = np.diff(np.r_[starts, len(edges)])
    two = starts[counts == 2]
    a, b = order[two], order[two + 1]
    rows, cols = corners[a].ravel(), corners[b].ravel()
    links = coo_matrix((np.ones(len(rows), dtype=np.uint8), (rows, cols)), shape=(faces.size, faces.size)).tocsr()
    _, labels = connected_components(links, directed=False)
    vertex_links = np.unique(np.column_stack((faces.ravel(), labels)), axis=0)
    fans = np.bincount(vertex_links[:, 0], minlength=len(mesh.vertices))
    bad_vertices = int(np.count_nonzero(fans != 1))
    face_links = coo_matrix((np.ones(len(a), dtype=np.uint8), (a // 3, b // 3)), shape=(len(faces), len(faces))).tocsr()
    components, face_labels = connected_components(face_links, directed=False)
    return {
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "nonmanifold_vertices": bad_vertices,
        "connected_components": int(components),
        "component_triangle_counts": np.bincount(face_labels).tolist(),
    }


def validate_mesh(mesh, expected_size=None, tolerance=0.0):
    errors = []
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0 or len(mesh.vertices) == 0:
        return {"valid": False, "errors": ["Empty triangle mesh."]}
    finite = bool(np.isfinite(mesh.vertices).all())
    if not finite:
        return {"valid": False, "errors": ["Nonfinite vertex coordinates."]}
    area = mesh.area_faces
    degenerate = int(np.count_nonzero(~np.isfinite(area) | (area <= 1e-14)))
    topo = topology(mesh)
    if degenerate:
        errors.append(f"{degenerate} degenerate triangles.")
    if topo["boundary_edges"]:
        errors.append(f"{topo['boundary_edges']} open boundary edges.")
    if topo["nonmanifold_edges"] or topo["nonmanifold_vertices"]:
        errors.append("Nonmanifold edges or vertex fans detected.")
    if not mesh.is_winding_consistent:
        errors.append("Inconsistent triangle winding.")
    volume = float(mesh.volume)
    if not np.isfinite(volume) or volume <= 0:
        errors.append("Mesh does not enclose a positive finite volume.")
    if topo["connected_components"] != 1:
        errors.append(f"Expected one connected solid boundary; found {topo['connected_components']} pieces. "
                      "Adjust the box size/cell pitch/thickness or add a base; pieces were not removed.")
    bounds = mesh.bounds
    if expected_size is not None:
        if np.any(bounds[0] < -tolerance) or np.any(bounds[1] > np.array(expected_size) + tolerance):
            errors.append("Mesh extends outside the requested clipping envelope.")
        if abs(bounds[0, 2]) > tolerance:
            errors.append("Lattice does not reach Z=0; increase the box/cell intersection or add a base.")
    return {"valid": not errors, "errors": errors, "finite_coordinates": finite,
            "degenerate_triangles": degenerate, "watertight": bool(mesh.is_watertight),
            "consistent_winding": bool(mesh.is_winding_consistent), **topo,
            "bounds_mm": bounds.tolist(), "occupied_size_mm": mesh.extents.tolist(),
            "volume_mm3": volume, "surface_area_mm2": float(mesh.area),
            "vertices": len(mesh.vertices), "triangles": len(mesh.faces)}


def require_valid(result):
    if not result["valid"]:
        raise LatticeError("Mesh validation failed: " + " ".join(result["errors"]))


def load_mesh(path):
    try:
        # STL repeats triangle vertices. Weld numerically identical coordinates,
        # but do not run automatic hole filling, component removal, or repairs.
        mesh = trimesh.load_mesh(str(path), process=False)
        if not isinstance(mesh, trimesh.Trimesh):
            raise LatticeError("Input must contain a triangle mesh.")
        mesh.merge_vertices(digits_vertex=8)
        return mesh
    except (OSError, ValueError, TypeError) as exc:
        raise LatticeError(f"Cannot load mesh {path}: {exc}") from exc
