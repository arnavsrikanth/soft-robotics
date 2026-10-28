import numpy as np
import trimesh

from lattice_generator.validation import validate_mesh


def test_rejects_open_mesh():
    mesh = trimesh.creation.box()
    mesh.update_faces(np.arange(len(mesh.faces)-1))
    result = validate_mesh(mesh)
    assert not result["valid"]
    assert result["boundary_edges"] > 0


def test_rejects_disconnected_solids():
    a = trimesh.creation.box()
    b = trimesh.creation.box()
    b.apply_translation((3,0,0))
    result = validate_mesh(trimesh.util.concatenate((a,b)))
    assert not result["valid"]
    assert result["connected_components"] == 2


def test_rejects_pinched_vertex_even_with_closed_edges():
    a = trimesh.creation.box()
    b = trimesh.creation.box()
    b.apply_translation((1,1,1))
    mesh = trimesh.util.concatenate((a,b))
    mesh.merge_vertices()
    result = validate_mesh(mesh)
    assert result["watertight"]
    assert result["nonmanifold_vertices"] == 1
    assert not result["valid"]


def test_negative_volume_and_nonfinite_are_rejected():
    mesh = trimesh.creation.box()
    mesh.invert()
    assert not validate_mesh(mesh)["valid"]
    mesh.vertices[0,0] = np.nan
    assert not validate_mesh(mesh)["valid"]
