import numpy as np
import pytest

from lattice_generator.config import Settings
from lattice_generator.meshing import generate_mesh
from lattice_generator.validation import validate_mesh


@pytest.mark.parametrize("pattern", ["cubic", "bcc", "octet", "diamond", "kelvin", "gyroid"])
def test_patterns_are_closed_solids(pattern):
    thickness = {"wall_thickness" if pattern == "gyroid" else "strut_diameter": 1.2}
    settings = Settings(pattern, (12, 12, 12), 6, **thickness)
    mesh, _ = generate_mesh(settings)
    result = validate_mesh(mesh, settings.size, 2*settings.grid_spacing)
    assert result["valid"], result
    assert np.allclose(mesh.bounds[0], 0, atol=2*settings.grid_spacing)
    assert np.allclose(mesh.bounds[1], settings.size, atol=2*settings.grid_spacing)


def test_rectangular_partial_cells_and_plate():
    settings = Settings("cubic", (13.3, 10.7, 8.2), 6, strut_diameter=1.2, base_thickness=1)
    mesh, _ = generate_mesh(settings)
    result = validate_mesh(mesh, settings.size, 2*settings.grid_spacing)
    assert result["valid"], result
    assert np.allclose(mesh.bounds, [[0, 0, 0], settings.size], atol=2*settings.grid_spacing)
    plain, _ = generate_mesh(Settings("cubic", settings.size, 6, strut_diameter=1.2, resolution=settings.grid_spacing))
    assert mesh.volume > plain.volume


def section_width(mesh, x=3):
    # At x=3, the cubic x-strut centered on y=z=6 is far from its junctions.
    lines = __import__("trimesh").intersections.mesh_plane(mesh, (1, 0, 0), (x, 0, 0))
    points = lines.reshape(-1, 3)
    points = points[(abs(points[:, 1]-6) < 2) & (abs(points[:, 2]-6) < 2)]
    return np.ptp(points[:, 1]), np.ptp(points[:, 2])


def test_strut_thickness_and_resolution_convergence():
    coarse, _ = generate_mesh(Settings("cubic", (12, 12, 12), 6, strut_diameter=1.2))
    fine, _ = generate_mesh(Settings("cubic", (12, 12, 12), 6, strut_diameter=1.2, resolution=0.1))
    assert np.allclose(section_width(coarse), 1.2, atol=0.4)
    assert np.allclose(section_width(fine), 1.2, atol=0.2)
    assert abs(fine.volume-coarse.volume) / fine.volume < 0.12
    # A particular coarse grid can fortuitously pass through the diameter exactly;
    # require convergence within tolerance rather than monotonic pointwise error.
    assert np.allclose(section_width(fine), section_width(coarse), atol=0.05)
    assert np.allclose(section_width(fine), 1.2, atol=0.012)


def test_gyroid_thickness_convergence():
    # With the documented quarter-cell x offset, F=0 at (1.5,3,3).
    import trimesh
    measurements = []
    for h in (0.2, 0.1):
        settings = Settings("gyroid", (6, 6, 6), 6, wall_thickness=1.2, resolution=h)
        mesh, _ = generate_mesh(settings)
        result = validate_mesh(mesh, settings.size, 2*h)
        assert result["valid"], result
        # Intersect triangles with a line using an explicit vectorized Moller-Trumbore
        # calculation, avoiding an optional spatial-index dependency in tests.
        tri = mesh.triangles
        origin = np.array([1.5,3,3]) - np.ones(3)*2
        direction = np.ones(3)/np.sqrt(3)
        e1, e2 = tri[:,1]-tri[:,0], tri[:,2]-tri[:,0]
        p = np.cross(direction, e2)
        determinant = np.einsum("ij,ij->i", e1, p)
        keep = abs(determinant) > 1e-10
        e1,e2,p,tri,determinant = e1[keep],e2[keep],p[keep],tri[keep],determinant[keep]
        s = origin-tri[:,0]
        u = np.einsum("ij,ij->i", s,p)/determinant
        q = np.cross(s,e1)
        v = q @ direction / determinant
        t = np.einsum("ij,ij->i", e2,q)/determinant
        ts = np.unique(np.round(t[(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)], 6))
        center_t = 2*np.sqrt(3)
        near = ts[abs(ts-center_t)<1.2]
        assert len(near) == 2, near
        thickness = near[1]-near[0]
        assert abs(thickness-1.2) < 2*h
        measurements.append(thickness)
    assert abs(measurements[0]-measurements[1]) < 0.4
