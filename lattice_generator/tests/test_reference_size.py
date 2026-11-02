from dataclasses import replace
import numpy as np
import pytest
import trimesh
from lattice_generator.config import Settings, LatticeError
from lattice_generator.pockets import layout
from lattice_generator.validation import validate_mesh

def settings(**kw):
    values = dict(pattern="cubic", size=(43,43,24.324), cell_size=6, strut_diameter=1.2,
                  pockets="four", pocket_midplane_height=11.6)
    values.update(kw)
    return Settings(**values)

def test_reference_layout():
    info = layout(settings().check())
    assert info["cavity_diameter_mm"] == pytest.approx(10.3)
    assert info["cavity_height_mm"] == pytest.approx(2.9)
    assert info["holder_bottom_z_mm"] == pytest.approx(9.15)
    assert info["holder_top_z_mm"] == pytest.approx(14.05)
    assert info["roof_start_z_mm"] == pytest.approx(13.05)
    for height in (20,30):
        assert layout(settings(size=(43,43,height))) ["holders"] == info["holders"]

@pytest.mark.parametrize("kwargs", [dict(mesh_above_pockets=2),dict(pocket_midplane_height=-1),
    dict(pocket_midplane_height=float("nan")),dict(pocket_midplane_height=1),dict(pocket_midplane_height=24)])
def test_invalid_position(kwargs):
    with pytest.raises(LatticeError): settings(**kwargs).check()

def test_exact_bounds_reject_short_mesh():
    s=settings(pockets="none",require_exact_bounds=True)
    mesh=trimesh.creation.box(bounds=[[0,0,0],[43,43,24]])
    result=validate_mesh(mesh,s.size,0.4,pocket_settings=s)
    assert not result["valid"]
    assert any("0.001" in error for error in result["errors"])
