import json
from pathlib import Path
import pytest

from lattice_generator.cli import parser, resolve
from lattice_generator.config import LatticeError, Settings
from lattice_generator.export import generate
from lattice_generator.validation import load_mesh, validate_mesh


@pytest.mark.parametrize("changes", [
    {"size": (-1, 12, 12)}, {"size": (float("nan"), 12, 12)}, {"cell_size": 0},
    {"strut_diameter": 0}, {"base_thickness": 12}, {"base_thickness": -1},
    {"resolution": 0.4}, {"wall_thickness": 1}, {"pattern": "unknown"},
    {"memory_limit_mib": 1}, {"size": (100000,100000,100000)},
])
def test_bad_settings(changes):
    values = dict(pattern="cubic", size=(12,12,12), cell_size=6, strut_diameter=1.2)
    values.update(changes)
    with pytest.raises(LatticeError):
        Settings(**values).check()


def test_preset_override_and_relative_output(tmp_path):
    path = tmp_path / "preset.json"
    path.write_text(json.dumps({"pattern":"cubic", "size":[12,12,12], "cell-size":6,
                                "strut-diameter":1.2, "output":"out.stl"}))
    settings, options = resolve(parser().parse_args(["generate", "--config",str(path),"--size","15","12","12"]))
    assert settings.size == (15,12,12)
    assert Path(options["output"]) == tmp_path / "out.stl"


def test_export_round_trip_and_overwrite(tmp_path):
    output = tmp_path / "sample.stl"
    settings = Settings("cubic", (6,6,6), 6, strut_diameter=1.2)
    report = generate(settings, output, log=lambda _:None)
    assert report["stl_round_trip_validated"]
    assert validate_mesh(load_mesh(output))["valid"]
    assert len(output.read_bytes()) == 84 + 50*report["validation"]["triangles"]
    before = output.read_bytes()
    with pytest.raises(LatticeError, match="already exists"):
        generate(settings, output)
    assert output.read_bytes() == before
    generate(settings, output, overwrite=True, log=lambda _:None)


def test_empty_geometry_and_failed_validation_do_not_publish(tmp_path):
    # Kelvin has no strut at the phase origin: this tiny box contains no material.
    output = tmp_path / "empty.stl"
    with pytest.raises(LatticeError, match="no resolved solid"):
        generate(Settings("kelvin", (0.1,0.1,0.1), 6, strut_diameter=1.2), output, log=lambda _:None)
    assert not output.exists()


def test_clipped_island_is_reported_not_discarded(tmp_path):
    output = tmp_path / "fragment.stl"
    with pytest.raises(LatticeError, match="found 2 pieces"):
        generate(Settings("octet", (13.3,10.7,8.2), 6, strut_diameter=1.2, base_thickness=1), output, log=lambda _:None)
    assert not output.exists()
