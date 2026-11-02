from dataclasses import replace
import json
import numpy as np
import pytest
import trimesh

from lattice_generator.config import Settings, LatticeError
from lattice_generator.cli import parser, resolve
from lattice_generator.export import generate
from lattice_generator.meshing import generate_mesh, grid
from lattice_generator.pockets import apply_pockets, layout, validate_regions
from lattice_generator.validation import validate_mesh


def small(pattern="cubic", **kwargs):
    values = dict(pattern=pattern, size=(12,12,12), cell_size=6, pockets="four",
                  mesh_above_pockets=0,
                  magnet_diameter=3, magnet_thickness=2, pocket_wall_thickness=0.6,
                  pocket_floor_thickness=0.6, pocket_roof_thickness=0.6)
    if pattern == "cubic":
        values["cell_size"] = 4  # Small holders must intersect the grid, not sit in an empty pore.
    values["wall_thickness" if pattern == "gyroid" else "strut_diameter"] = 1.2
    values.update(kwargs)
    return Settings(**values)


@pytest.mark.parametrize("pattern", ["cubic","bcc","octet","diamond","kelvin","gyroid"])
def test_pockets_all_patterns_roundtrip(pattern, tmp_path):
    report = generate(small(pattern), tmp_path / f"{pattern}.stl", log=lambda _:None)
    assert report["validation"]["valid"]
    assert report["validation"]["material_bodies"] == 1
    assert report["validation"]["enclosed_cavities"] == 4
    assert report["meshing"]["pocket_region_validation"]["enclosed_voids"] == 4
    assert report["stl_round_trip_validated"]
    for p in report["validation"]["pocket_measurements"]:
        assert np.allclose(p["diameter_xy_mm"],3.3,atol=report["geometric_tolerance_mm"])
        assert abs(p["height_mm"]-2.2) < report["geometric_tolerance_mm"]


def test_default_layout():
    s = Settings("cubic", (36,36,18),6,strut_diameter=1.2,pockets="four").check()
    info = layout(s)
    assert info["cavity_diameter_mm"] == pytest.approx(10.3)
    assert info["cavity_height_mm"] == pytest.approx(2.9)
    assert info["roof_start_z_mm"] == 15
    assert info["holder_top_z_mm"] == 16
    assert info["total_mesh_height_mm"] == 18
    assert info["holder_bottom_z_mm"] == pytest.approx(11.1)
    assert [p["center_xy_mm"] for p in info["holders"]] == [[9,9],[27,9],[9,27],[27,27]]
    assert s.grid_spacing == pytest.approx(1/6)


@pytest.mark.parametrize("changes", [
    {"magnet_diameter":-1},{"magnet_thickness":float("nan")},
    {"pocket_diameter_clearance":-0.1},{"pocket_height_clearance":float("inf")},
    {"pocket_wall_thickness":0},{"pocket_floor_thickness":0},{"pocket_roof_thickness":0},
    {"magnet_diameter":9.525},{"size":(12,12,3)}, {"resolution":.2},
    {"pockets":"two"}, {"pocket_roof_thickness":True},
])
def test_invalid_pockets(changes):
    with pytest.raises(LatticeError):
        small(**changes).check()


def test_preset_and_cli_options(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"pattern":"cubic","size":[36,36,18],"cell-size":6,
                               "strut-diameter":1.2,"pockets":"four","output":"out.stl"}))
    s,_ = resolve(parser().parse_args(["generate","--config",str(path),"--pocket-height-clearance","0.3"]))
    assert s.pockets == "four" and s.pocket_height_clearance == .3
    s,_ = resolve(parser().parse_args(["generate","--config",str(path),"--pockets","none"]))
    assert s.pockets == "none"


def test_shell_containment_and_orientation():
    outer = trimesh.creation.box(extents=(10,10,10))
    cavity = trimesh.creation.box(extents=(2,2,2)); cavity.invert()
    valid = trimesh.util.concatenate((outer,cavity))
    result = validate_mesh(valid)
    assert result["valid"] and result["material_bodies"] == 1 and result["enclosed_cavities"] == 1
    cavity.invert()
    assert not validate_mesh(trimesh.util.concatenate((outer,cavity)))["valid"]
    cavity.invert(); cavity.apply_translation((10,0,0))
    result = validate_mesh(trimesh.util.concatenate((outer,cavity)))
    assert not result["valid"] and any("contained" in e for e in result["errors"])


def test_open_roof_is_not_a_valid_pocket():
    s = small()
    mesh,_ = generate_mesh(s)
    center = layout(s)["holders"][0]["center_xy_mm"]
    top = mesh.triangles_center
    cut = (top[:,2] > 11.95) & (np.linalg.norm(top[:,:2]-center,axis=1) < 1)
    assert cut.any()
    mesh.update_faces(~cut)
    assert not validate_mesh(mesh, s.size, .2, pocket_settings=s)["valid"]


def test_floors_walls_roofs_empty_cavities_and_disconnected_holders():
    s = small()
    axes,_ = grid(s)
    # Holders without any lattice connection must fail.
    field = np.full(tuple(map(len,axes)),2,dtype=np.float32)
    info = apply_pockets(field,axes,s)
    with pytest.raises(LatticeError,match="disconnected"):
        validate_regions(field,axes,info)
    from scipy.ndimage import map_coordinates
    for p in info["holders"]:
        x,y,z = p["cavity_center_mm"]
        radius = info["cavity_diameter_mm"]/2
        samples = [(x,y,p["cavity_bounds_mm"][0][2]-.3),(x,y,11.7)]
        samples += [(x+(radius+.3)*np.cos(t),y+(radius+.3)*np.sin(t),z) for t in np.linspace(0,2*np.pi,16,endpoint=False)]
        coordinates = np.array([[(v[i]-axis[0])/(axis[1]-axis[0]) for v in samples] for i,axis in enumerate(axes)])
        assert np.all(map_coordinates(field,coordinates,order=1) < 0)
        idx = tuple(int(np.argmin(abs(axis-c))) for axis,c in zip(axes,(x,y,z)))
        assert field[idx] > 0


def test_rectangular_box_and_base():
    s = small(size=(12,15,12),base_thickness=1.2)
    mesh,_ = generate_mesh(s)
    result = validate_mesh(mesh, s.size, 2*s.grid_spacing,pocket_settings=s)
    assert result["valid"],result["errors"]
    assert np.allclose(mesh.bounds,[[0,0,0],[12,15,12]],atol=.2)


@pytest.mark.parametrize("extension", [0, 1, 2])
def test_mesh_extension_preserves_total_height(extension, tmp_path):
    s = small(mesh_above_pockets=extension)
    report = generate(s,tmp_path/f'extension_{extension}.stl',log=lambda _:None)
    info=report['pockets']
    assert info['holder_top_z_mm'] == 12-extension
    assert info['roof_start_z_mm'] == pytest.approx(12-extension-.6)
    assert report['validation']['bounds_mm'][1][2] == pytest.approx(12,abs=.2)
    assert report['validation']['enclosed_cavities'] == 4
    # Above the holder, the field must contain just the original lattice.
    s.check()
    axes,_=grid(s)
    field=np.full(tuple(map(len,axes)),2,dtype=np.float32)
    apply_pockets(field,axes,s)
    if extension:
        assert np.all(field[:,:,axes[2] > info['holder_top_z_mm']+.2] > 0)


@pytest.mark.parametrize('extension',[-1,float('nan'),float('inf'),True,10,.05])
def test_bad_mesh_extension(extension):
    with pytest.raises(LatticeError):
        small(mesh_above_pockets=extension).check()


def test_mesh_extension_cli_and_plain_compatibility():
    s,_=resolve(parser().parse_args(['generate','--pattern','cubic','--size','36','36','18',
        '--cell-size','6','--strut-diameter','1.2','--pockets','four','--mesh-above-pockets','3','--output','x.stl']))
    assert layout(s)['holder_top_z_mm'] == 15
    a,_=generate_mesh(replace(s,pockets='none',size=(6,6,6)))
    b,_=generate_mesh(replace(s,pockets='none',size=(6,6,6),mesh_above_pockets=0))
    assert np.array_equal(a.vertices,b.vertices) and np.array_equal(a.faces,b.faces)
