"""Sealed cylindrical holders and checks in physical millimeter coordinates."""

from itertools import combinations
import numpy as np
from scipy.ndimage import label, generate_binary_structure, find_objects

from .config import LatticeError


def layout(settings):
    w, d, h = settings.size
    radius = (settings.magnet_diameter + settings.pocket_diameter_clearance) / 2
    height = settings.magnet_thickness + settings.pocket_height_clearance
    extension = settings.mesh_above_pockets if settings.mesh_above_pockets is not None else 2.0
    holder_top = (settings.pocket_midplane_height + height / 2 + settings.pocket_roof_thickness
                  if settings.pocket_midplane_height is not None else h - extension)
    roof_start = holder_top - settings.pocket_roof_thickness
    floor_top = roof_start - height
    bottom = floor_top - settings.pocket_floor_thickness
    centers = [(x, y) for y in (d/4, 3*d/4) for x in (w/4, 3*w/4)]
    outer_radius = radius + settings.pocket_wall_thickness
    return {
        "count": 4, "magnet_diameter_mm": settings.magnet_diameter,
        "magnet_thickness_mm": settings.magnet_thickness,
        "diametral_clearance_mm": settings.pocket_diameter_clearance,
        "height_clearance_mm": settings.pocket_height_clearance,
        "cavity_diameter_mm": 2*radius, "cavity_height_mm": height,
        "outer_radius_mm": outer_radius, "wall_thickness_mm": settings.pocket_wall_thickness,
        "floor_thickness_mm": settings.pocket_floor_thickness,
        "roof_thickness_mm": settings.pocket_roof_thickness,
        "holder_bottom_z_mm": bottom, "holder_top_z_mm": holder_top,
        "mesh_above_pockets_mm": h - holder_top,
        "pocket_midplane_height_mm": (floor_top + roof_start) / 2,
        "total_mesh_height_mm": h, "roof_start_z_mm": roof_start,
        "holders": [{"center_xy_mm": [x,y], "cavity_center_mm": [x,y,(floor_top+roof_start)/2],
                     "cavity_bounds_mm": [[x-radius,y-radius,floor_top],[x+radius,y+radius,roof_start]],
                     "holder_bounds_mm": [[x-outer_radius,y-outer_radius,bottom],[x+outer_radius,y+outer_radius,holder_top]]}
                    for x,y in centers],
        "pause_guidance": "Pause after the cavity is printed and before the first roof extrusion. Determine the layer from the slicer's actual preview; do not use a rounded layer-number formula."
    }


def check_layout(settings):
    info = layout(settings)
    h = settings.grid_spacing
    features = (settings.pocket_wall_thickness, settings.pocket_floor_thickness,
                settings.pocket_roof_thickness, info["cavity_diameter_mm"], info["cavity_height_mm"])
    if any(t < 4*h - 1e-12 for t in features):
        raise LatticeError("Unresolved pocket feature: resolution must provide at least four samples across each wall, floor, roof, and cavity dimension.")
    if info["holder_bottom_z_mm"] < 0:
        raise LatticeError("Insufficient total model height for the pocket floor, magnet cavity, roof, and mesh above pockets.")
    if info["holder_top_z_mm"] > settings.size[2]:
        raise LatticeError("Pocket holder extends above the model.")
    if 0 < info["mesh_above_pockets_mm"] < 2*h - 1e-12:
        raise LatticeError("mesh-above-pockets must be zero or at least two grid spacings so the extension is resolved.")
    radius = info["outer_radius_mm"]
    centers = [p["center_xy_mm"] for p in info["holders"]]
    for x,y in centers:
        if min(x-radius, settings.size[0]-x-radius, y-radius, settings.size[1]-y-radius) < 2*h - 1e-12:
            raise LatticeError("Pocket holders must remain inside the box with at least two grid spacings of side clearance. Increase width/depth or reduce holder dimensions.")
    for a,b in combinations(centers, 2):
        if np.linalg.norm(np.subtract(a,b)) - 2*radius < 2*h - 1e-12:
            raise LatticeError("Pocket holders overlap or have less than two grid spacings between them.")


def cylinder_field(x, y, z, center_xy, radius, bottom, top):
    """Negative inside; radial and axial distances have millimeter units."""
    return np.maximum(np.hypot(x-center_xy[0], y-center_xy[1])-radius,
                      np.maximum(bottom-z, z-top))


def apply_pockets(field, axes, settings):
    info = layout(settings)
    x,y,z = np.meshgrid(*axes, indexing="ij", sparse=True)
    # Union every holder before subtracting every cavity, including base material.
    for holder in info["holders"]:
        outer = cylinder_field(x,y,z,holder["center_xy_mm"], info["outer_radius_mm"],
                               info["holder_bottom_z_mm"], info["holder_top_z_mm"])
        np.minimum(field, outer, out=field)
    for holder in info["holders"]:
        bounds = holder["cavity_bounds_mm"]
        inner = cylinder_field(x,y,z,holder["center_xy_mm"], info["cavity_diameter_mm"]/2,
                               bounds[0][2], bounds[1][2])
        np.maximum(field, -inner, out=field)
    return info


def validate_regions(field, axes, info):
    # Strict 6-connected material rejects diagonal-only contacts. For air use 26
    # connectivity so even diagonal leaks prevent a false "sealed" conclusion.
    solid_labels, material_count = label(field < 0, structure=generate_binary_structure(3,1))
    if material_count != 1:
        counts = np.bincount(solid_labels.ravel(), minlength=material_count+1)
        boxes = find_objects(solid_labels)
        spacing = [float(axis[1]-axis[0]) for axis in axes]
        summaries = []
        for region, box in enumerate(boxes, 1):
            bounds = [[float(axis[sl.start]), float(axis[sl.stop-1])]
                      for axis, sl in zip(axes, box)]
            summaries.append(f"region {region}: voxels={counts[region]}, "
                             f"approx_volume_mm3={counts[region]*np.prod(spacing):.9g}, "
                             f"voxel_center_bounds_xyz_mm={bounds}")
        raise LatticeError(f"Pocketed material has {material_count} disconnected regions. "
                           "Holders and lattice must form one body; no pieces were removed. " +
                           "; ".join(summaries))
    del solid_labels
    air, count = label(field >= 0, structure=generate_binary_structure(3,3))
    boundary = np.unique(np.concatenate([air[0].ravel(),air[-1].ravel(),air[:,0].ravel(),
                                        air[:,-1].ravel(),air[:,:,0].ravel(),air[:,:,-1].ravel()]))
    enclosed = set(range(1,count+1)) - set(boundary)
    intended = []
    for holder in info["holders"]:
        index = tuple(int(np.argmin(abs(axis-c))) for axis,c in zip(axes, holder["cavity_center_mm"]))
        intended.append(int(air[index]))
    if len(enclosed) != 4 or set(intended) != enclosed or 0 in intended:
        raise LatticeError(f"Expected four enclosed empty magnet cavities at their intended centers; found {len(enclosed)} enclosed voids. Check pocket resolution and connections.")
    return {"material_regions": int(material_count), "enclosed_voids": len(enclosed),
            "cavity_centers_in_distinct_enclosed_voids": True}
