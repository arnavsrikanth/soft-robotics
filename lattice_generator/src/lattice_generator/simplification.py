"""Error-bounded simplification, retaining enclosed pocket shells verbatim."""
import time
import numpy as np
import trimesh
from .config import LatticeError
from .validation import validate_mesh


def within_distance(source, target, tolerance, log=print):
    """Certify directed surface distance using triangle covering radii.

    Distance to a closed triangle set is 1-Lipschitz. Each triangle is covered
    by a ball at its centroid, so distance(center)+radius bounds every point.
    A convex target-triangle bound can tighten the covering ball bound.
    Subdivision tightens unresolved bounds. Unresolved checks reject.
    """
    query = trimesh.proximity.ProximityQuery(target)
    maximum = 0.0
    last_progress = time.monotonic()
    for start in range(0, len(source.faces), 16384):
        if time.monotonic() - last_progress > 30:
            log(f"Distance certification progress: {start:,}/{len(source.faces):,} source triangles")
            last_progress = time.monotonic()
        pending = source.triangles[start:start+16384]
        for depth in range(12):
            center = pending.mean(axis=1)
            _, distance, target_ids = query.on_surface(center)
            radius = np.linalg.norm(pending-center[:,None,:],axis=2).max(axis=1)
            if not np.isfinite(distance).all() or np.any(distance > tolerance):
                log(f"Surface-distance failure: nonfinite distance or measured distance {float(np.max(distance)):.9g} mm exceeds {tolerance:g} mm; block={start}, depth={depth}")
                return False, None
            # Distance to a single convex target triangle is convex: the
            # maximum vertex distance bounds every point of the source triangle.
            # That triangle is part of the target surface, so this is also a
            # conservative surface-distance bound, often tight on flat regions.
            target_triangles = np.repeat(target.triangles[target_ids], 3, axis=0)
            vertices = pending.reshape(-1, 3)
            closest = trimesh.triangles.closest_point(target_triangles, vertices)
            convex_upper = np.linalg.norm(vertices-closest, axis=1).reshape(-1,3).max(axis=1)
            upper = np.minimum(distance + radius, convex_upper)
            accepted = upper <= tolerance
            if np.any(accepted): maximum = max(maximum, float(upper[accepted].max()))
            pending = pending[~accepted]
            if not len(pending): break
            if len(pending) > 200000 or depth == 11:
                log(f"Surface-distance certification unresolved: block={start}, depth={depth}, pending={len(pending)}; subdivision/work limit reached")
                return False, None
            a,b,c = pending[:,0],pending[:,1],pending[:,2]
            ab,bc,ca = (a+b)/2,(b+c)/2,(c+a)/2
            pending = np.concatenate([np.stack(t,axis=1) for t in
                                      ((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca))])
    return True, maximum


def simplify(mesh, settings, log=print):
    tolerance = settings.simplify_tolerance
    report = {"enabled": tolerance > 0, "input_triangles": len(mesh.faces),
              "tolerance_mm": tolerance, "bounds_tolerance_mm": 0.05, "attempts": [], "accepted": False}
    if not tolerance:
        return mesh, report
    shells = mesh.split(only_watertight=False)
    outer = [s for s in shells if s.volume > 0]
    cavities = [s for s in shells if s.volume < 0]
    if len(outer) != 1:
        log(f"Simplification failed: expected one material body, found {len(outer)}")
        raise LatticeError("Simplification requires one validated material body.")
    original = outer[0]
    for retained in (0.1, 0.25, 0.5):
        attempt = {"retained_fraction": retained, "failures": []}
        report["attempts"].append(attempt)
        def reject(message):
            if "certification progress:" not in message:
                attempt["failures"].append(message)
            log(f"Simplification {retained:.0%}: {message}")
        log(f"Trying simplification retaining {retained:.0%} of outer triangles")
        candidate = original.simplify_quadric_decimation(face_count=max(4,int(len(original.faces)*retained)))
        candidate.merge_vertices(digits_vertex=10)
        candidate.update_faces(candidate.nondegenerate_faces())
        candidate.remove_unreferenced_vertices()
        combined = trimesh.util.concatenate([candidate, *cavities])
        drift = float(np.max(np.abs(combined.bounds-mesh.bounds)))
        attempt.update(output_triangles=len(combined.faces), bounds_drift_mm=drift)
        if drift > 0.05:
            reject(f"Bounds drift {drift:.9g} mm exceeds 0.05 mm")
            continue
        checks = validate_mesh(combined, settings.size, 2*settings.grid_spacing, pocket_settings=settings, bounds_tolerance=0.05)
        if not checks["valid"]:
            for error in checks["errors"]: reject("Validation failed: " + error)
            continue
        forward, bound1 = within_distance(original, candidate, tolerance, lambda msg: reject("Original to candidate: " + msg))
        if not forward: continue
        backward, bound2 = within_distance(candidate, original, tolerance, lambda msg: reject("Candidate to original: " + msg))
        if not backward: continue
        report.update(accepted=True, output_triangles=len(combined.faces),
                      certified_surface_error_mm=max(bound1,bound2), pocket_shells_preserved=True)
        log(f"Simplification accepted: {len(mesh.faces):,} -> {len(combined.faces):,} triangles; certified error {max(bound1,bound2):.6g} mm")
        return combined, report
    log("No simplification passed all checks; retaining the original surface")
    report.update(output_triangles=len(mesh.faces), reason="No candidate passed bounds, topology and surface-error checks")
    return mesh, report
