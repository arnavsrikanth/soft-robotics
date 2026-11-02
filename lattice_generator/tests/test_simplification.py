import numpy as np
import pytest
import trimesh
from lattice_generator.config import Settings, LatticeError
from lattice_generator.simplification import simplify, within_distance

def test_planar_reduction():
    mesh=trimesh.creation.box(bounds=[[0,0,0],[2,2,2]])
    for _ in range(3): mesh=mesh.subdivide()
    settings=Settings("cubic",(2,2,2),1,strut_diameter=.4,require_exact_bounds=True)
    result, report=simplify(mesh,settings,lambda _:None)
    assert report["accepted"]
    assert len(result.faces)<len(mesh.faces)/2
    assert result.is_watertight
    assert np.allclose(result.bounds,mesh.bounds,atol=.001)
    assert report["certified_surface_error_mm"]<=.05

def test_error_check_rejects_displacement():
    a=trimesh.creation.box()
    b=a.copy(); b.apply_translation([.2,0,0])
    assert not within_distance(a,b,.05)[0]

@pytest.mark.parametrize("value",[-1,float("nan"),True])
def test_invalid_tolerance(value):
    with pytest.raises(LatticeError):
        Settings("cubic",(2,2,2),1,strut_diameter=.4,simplify_tolerance=value).check()

def test_bounds_review_tolerance():
    from lattice_generator.validation import validate_mesh
    mesh = trimesh.creation.box(bounds=[[-.02, 0, 0], [2.02, 2, 2]])
    settings = Settings('cubic', (2,2,2), 1, strut_diameter=.4, require_exact_bounds=True)
    assert not validate_mesh(mesh, settings.size, .1, pocket_settings=settings)['valid']
    assert validate_mesh(mesh, settings.size, .1, pocket_settings=settings, bounds_tolerance=.05)['valid']
    mesh.vertices[mesh.vertices[:,0] > 2, 0] = 2.06
    assert not validate_mesh(mesh, settings.size, .1, pocket_settings=settings, bounds_tolerance=.05)['valid']


def test_distance_failure_is_logged():
    a = trimesh.creation.box()
    b = a.copy(); b.apply_translation([.2,0,0])
    messages = []
    assert not within_distance(a,b,.05,messages.append)[0]
    assert any('Surface-distance failure' in message for message in messages)

def test_convex_certificate_large_planar_faces():
    # Large triangles should certify without exhaustive tiny subdivisions.
    mesh = trimesh.creation.box(extents=(1000,1000,1000))
    valid, bound = within_distance(mesh, mesh, .05)
    assert valid and bound <= .05


def test_certificate_accepts_bounded_offset():
    mesh = trimesh.creation.box()
    shifted = mesh.copy(); shifted.apply_translation([.02,0,0])
    assert within_distance(mesh, shifted, .05)[0]
    assert within_distance(shifted, mesh, .05)[0]
