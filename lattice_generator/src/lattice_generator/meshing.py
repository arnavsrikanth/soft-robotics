"""Distance-field union, box clipping, and closed surface extraction."""

import numpy as np
from scipy.ndimage import distance_transform_edt
from skimage.measure import marching_cubes
import trimesh

from .config import LatticeError
from .patterns import PHASES, segments


def grid(settings):
    info = settings.preflight()
    axes = [((np.arange(n, dtype=np.float64) - 0.5) * d)
            for n, d in zip(info["grid_shape"], info["spacing_mm"])]
    return axes, info


def strut_field(settings, axes, log):
    h = max(a[1] - a[0] for a in axes)
    radius = settings.strut_diameter / 2
    reach = radius + 2 * h
    field = np.full(tuple(map(len, axes)), 2 * h, dtype=np.float32)
    edges = segments(settings.pattern, settings.size, settings.cell_size, reach, lattice_offset=settings.lattice_offset)
    log(f"Evaluating {len(edges):,} unique struts")
    for a, b in edges:
        slices = tuple(slice(np.searchsorted(axis, min(a[i], b[i]) - reach),
                             np.searchsorted(axis, max(a[i], b[i]) + reach, side="right"))
                       for i, axis in enumerate(axes))
        if any(s.start >= s.stop for s in slices):
            continue
        xyz = np.meshgrid(*(axis[s] for axis, s in zip(axes, slices)), indexing="ij", sparse=True)
        direction = b - a
        t = sum((xyz[i] - a[i]) * direction[i] for i in range(3)) / np.dot(direction, direction)
        t = np.clip(t, 0, 1)
        dist = np.sqrt(sum((xyz[i] - a[i] - t * direction[i]) ** 2 for i in range(3))) - radius
        np.minimum(field[slices], dist, out=field[slices])
    return field, {"struts": len(edges), "lattice_offset_mm": list(settings.lattice_offset)}


def gyroid_field(settings, axes, info, log):
    pads = info["gyroid_halo"]
    spacing = info["spacing_mm"]
    extended = [((np.arange(-p, len(a) + p) - 0.5) * d)
                for a, p, d in zip(axes, pads, spacing)]
    phase = [(a.astype(np.float32) + offset * settings.cell_size) * (2 * np.pi / settings.cell_size)
             for a, offset in zip(extended, PHASES["gyroid"])]
    x, y, z = np.meshgrid(*phase, indexing="ij", sparse=True)
    level = np.sin(x) * np.cos(y) + np.sin(y) * np.cos(z) + np.sin(z) * np.cos(x)
    positive = level >= 0
    del level
    crop = tuple(slice(p, p + len(a)) for a, p in zip(axes, pads))
    log("Thickening the gyroid surface using distance transforms")
    # Distance to the opposite sign includes half a voxel across the interface.
    # Subtract half a sample spacing; the remaining directional error is O(h).
    distance = distance_transform_edt(positive, sampling=spacing)
    field = distance[crop].astype(np.float32)
    del distance
    distance = distance_transform_edt(~positive, sampling=spacing)
    field += distance[crop].astype(np.float32)
    del distance, positive
    field -= min(spacing) / 2 + settings.wall_thickness / 2
    return field, {"surface": "sin(x)cos(y)+sin(y)cos(z)+sin(z)cos(x)=0",
                   "thickening": "two-sided distance transform; nominal thickness, O(grid spacing) error"}


def generate_mesh(settings, log=lambda message: None):
    settings.check()
    axes, info = grid(settings)
    log(f"Grid {info['grid_shape']}; estimated memory {info['estimated_memory_mib']:.0f} MiB")
    if settings.pattern == "gyroid":
        field, details = gyroid_field(settings, axes, info, log)
    else:
        field, details = strut_field(settings, axes, log)
    x, y, z = np.meshgrid(*axes, indexing="ij", sparse=True)
    if settings.base_thickness:
        plate = np.maximum(-z, z - settings.base_thickness)
        np.minimum(field, plate, out=field)
    if settings.pockets == "four":
        from .pockets import apply_pockets
        log("Adding four holders and clearing sealed magnet cavities")
        details["pockets"] = apply_pockets(field, axes, settings)
    # Negative material intersected with the exact requested clipping envelope.
    for axis, extent in zip((x, y, z), settings.size):
        np.maximum(field, -axis, out=field)
        np.maximum(field, axis - extent, out=field)
    if settings.pockets == "four":
        from .pockets import validate_regions
        details["pocket_region_validation"] = validate_regions(field, axes, details["pockets"])
    # Tiny positive isovalue avoids exact-zero degeneracies without measurable scaling.
    level = max(info["spacing_mm"]) * 1e-5
    if not (field.min() < 0 and field.max() > level):
        raise LatticeError("The requested box contains no resolved solid surface. Increase size or thickness.")
    log("Extracting the solid boundary")
    vertices, faces, _, _ = marching_cubes(field, level=level, spacing=info["spacing_mm"],
                                          method="lewiner", allow_degenerate=False,
                                          gradient_direction="ascent")
    vertices += np.array([a[0] for a in axes])
    # Round-off around planar caps must not put the part below the build plane.
    vertices = np.clip(vertices, 0, settings.size)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # Marching cubes provides a boundary; orient it as positive material volume.
    if mesh.volume < 0:
        mesh.invert()
    return mesh, {**info, **details}
