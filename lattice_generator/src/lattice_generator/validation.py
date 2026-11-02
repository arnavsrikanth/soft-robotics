"""Validate the surface without silently repairing or dropping components."""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import trimesh

from .config import LatticeError


def topology(mesh, return_labels=False):
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
    result = {
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "nonmanifold_vertices": bad_vertices,
        "connected_components": int(components),
        "component_triangle_counts": np.bincount(face_labels).tolist(),
    }
    if return_labels:
        result["_face_labels"] = face_labels
    return result


def winding_number(mesh, point, bounds=None):
    """Oriented +X ray crossings for a closed shell, with shared-edge deduplication.

    Projected triangle bounds avoid evaluating every triangle for each point.
    The signed crossing sum is +1 inside an outward shell, -1 inside an inward
    shell, and zero outside. Tangential opposite crossings cancel.
    """
    triangles = mesh.triangles
    lower, upper = bounds if bounds is not None else (triangles.min(axis=1), triangles.max(axis=1))
    keep = (lower[:,1] <= point[1]+1e-9) & (upper[:,1] >= point[1]-1e-9) & (lower[:,2] <= point[2]+1e-9) & (upper[:,2] >= point[2]-1e-9) & (upper[:,0] > point[0])
    tri = triangles[keep]
    if not len(tri):
        return 0.0
    a = tri[:,0]
    e1,e2 = tri[:,1]-a,tri[:,2]-a
    det = e1[:,1]*e2[:,2]-e1[:,2]*e2[:,1]
    keep = abs(det) > 1e-12
    a,e1,e2,det = a[keep],e1[keep],e2[keep],det[keep]
    dy,dz = point[1]-a[:,1],point[2]-a[:,2]
    u = (dy*e2[:,2]-dz*e2[:,1])/det
    v = (e1[:,1]*dz-e1[:,2]*dy)/det
    t = a[:,0]+u*e1[:,0]+v*e2[:,0]-point[0]
    keep = (u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>1e-8)
    if not np.any(keep):
        return 0.0
    distances, indices = np.unique(np.round(t[keep],7),return_inverse=True)
    signs = np.bincount(indices,weights=np.sign(det[keep]),minlength=len(distances))
    return float(np.sign(signs).sum())


def classify_shells(mesh, labels):
    """Separate the outer positive material shell from contained negative voids."""
    shells = []
    for i in range(int(labels.max())+1):
        faces = mesh.faces[labels == i]
        vertex_ids, inverse = np.unique(faces, return_inverse=True)
        shell = trimesh.Trimesh(vertices=mesh.vertices[vertex_ids], faces=inverse.reshape(-1,3), process=False)
        shells.append(shell)
    positive = [s for s in shells if s.volume > 0]
    negative = [s for s in shells if s.volume < 0]
    errors = []
    if len(positive) != 1:
        errors.append(f"Expected one connected material body; found {len(shells)} pieces ({len(positive)} positive shells). Detached solids or incorrectly oriented cavity shells are not allowed.")
    if any(abs(s.volume) < 1e-12 for s in shells):
        errors.append("A boundary shell has zero volume.")
    if len(positive) == 1:
        outer = positive[0]
        outer_bounds = (outer.triangles.min(axis=1), outer.triangles.max(axis=1))
        for i, shell in enumerate(negative):
            # Check spatial extremes as well as a representative surface point.
            ids = np.r_[0, np.argmin(shell.vertices,axis=0), np.argmax(shell.vertices,axis=0)]
            points = shell.vertices[np.unique(ids)]
            if any(abs(winding_number(outer,p,outer_bounds)) < 0.5 for p in points):
                errors.append(f"Cavity shell {i+1} is not contained in the material boundary.")
            for other in negative[:i]:
                if abs(winding_number(other, shell.vertices[0])) > 0.5 or abs(winding_number(shell,other.vertices[0])) > 0.5:
                    errors.append("Nested cavity shells do not describe one connected material body.")
    return positive, negative, errors


def check_pocket_shells(cavities, settings, tolerance):
    """Verify the complete extracted cavity boundaries against intended cylinders."""
    from .pockets import layout
    info = layout(settings)
    errors, measurements = [], []
    if len(cavities) != 4:
        return [f"Expected exactly four sealed pocket cavities; found {len(cavities)}."], measurements
    remaining = list(cavities)
    for holder in info["holders"]:
        center = np.array(holder["cavity_center_mm"])
        shell = min(remaining, key=lambda s: np.linalg.norm(s.bounds.mean(axis=0)-center))
        remaining.remove(shell)
        bounds = np.array(holder["cavity_bounds_mm"])
        if not np.allclose(shell.bounds, bounds, atol=tolerance, rtol=0):
            errors.append("A pocket's measured bounds do not match its specified position and size.")
        if winding_number(shell, center) > -0.5:
            errors.append("A pocket center is not inside an inward-facing cavity shell.")
        vertices = shell.vertices
        radius = info["cavity_diameter_mm"]/2
        radial = np.linalg.norm(vertices[:,:2]-center[:2], axis=1)
        sdf = np.maximum(radial-radius, np.maximum(bounds[0,2]-vertices[:,2], vertices[:,2]-bounds[1,2]))
        if np.max(abs(sdf)) > tolerance:
            errors.append("Pocket boundary deviates from its cylinder: possible lattice obstruction or malformed cavity.")
        expected_volume = np.pi*radius**2*info["cavity_height_mm"]
        measured_volume = -float(shell.volume)
        if abs(measured_volume-expected_volume) > 2*np.pi*radius*(radius+info["cavity_height_mm"])*tolerance:
            errors.append("Pocket void volume is inconsistent with an empty cylinder.")
        measurements.append({"center_mm": center.tolist(), "bounds_mm": shell.bounds.tolist(),
                             "diameter_xy_mm": shell.extents[:2].tolist(), "height_mm": float(shell.extents[2]),
                             "void_volume_mm3": measured_volume,
                             "max_cylinder_surface_error_mm": float(np.max(abs(sdf)))})
    return errors, measurements


def validate_mesh(mesh, expected_size=None, tolerance=0.0, pocket_settings=None, bounds_tolerance=0.001):
    errors = []
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0 or len(mesh.vertices) == 0:
        return {"valid": False, "errors": ["Empty triangle mesh."]}
    finite = bool(np.isfinite(mesh.vertices).all())
    if not finite:
        return {"valid": False, "errors": ["Nonfinite vertex coordinates."]}
    area = mesh.area_faces
    degenerate = int(np.count_nonzero(~np.isfinite(area) | (area <= 1e-14)))
    topo = topology(mesh, return_labels=True)
    labels = topo.pop("_face_labels")
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
    material_count, cavity_count, pocket_measurements = 0, 0, []
    if not errors:
        if topo["connected_components"] == 1:
            material_count = 1
            cavities = []
        else:
            bodies, cavities, shell_errors = classify_shells(mesh, labels)
            errors.extend(shell_errors)
            material_count, cavity_count = len(bodies), len(cavities)
        if pocket_settings is not None:
            if pocket_settings.pockets == "four":
                pocket_errors, pocket_measurements = check_pocket_shells(cavities, pocket_settings, tolerance)
                errors.extend(pocket_errors)
            elif cavity_count:
                errors.append("Plain lattice unexpectedly contains enclosed cavities.")
    bounds = mesh.bounds
    if pocket_settings is not None and pocket_settings.require_exact_bounds:
        if not np.allclose(bounds, [np.zeros(3), pocket_settings.size], atol=bounds_tolerance, rtol=0):
            errors.append(f"Occupied bounds do not match requested dimensions within {bounds_tolerance:g} mm.")
    if expected_size is not None:
        if np.any(bounds[0] < -tolerance) or np.any(bounds[1] > np.array(expected_size) + tolerance):
            errors.append("Mesh extends outside the requested clipping envelope.")
        if abs(bounds[0, 2]) > tolerance:
            errors.append("Lattice does not reach Z=0; increase the box/cell intersection or add a base.")
    return {"valid": not errors, "errors": errors, "finite_coordinates": finite,
            "degenerate_triangles": degenerate, "watertight": bool(mesh.is_watertight),
            "consistent_winding": bool(mesh.is_winding_consistent), **topo,
            "material_bodies": material_count, "enclosed_cavities": cavity_count,
            "pocket_measurements": pocket_measurements,
            "bounds_mm": bounds.tolist(), "occupied_size_mm": mesh.extents.tolist(),
            "bounds_tolerance_mm": bounds_tolerance,
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
