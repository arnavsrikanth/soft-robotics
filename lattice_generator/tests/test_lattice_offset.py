from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from lattice_generator.config import Settings, LatticeError, read_preset
from lattice_generator.cli import parser, resolve
from lattice_generator.patterns import segments
from lattice_generator.meshing import grid, strut_field
from lattice_generator.pockets import apply_pockets, validate_regions, layout

PRESET = Path(__file__).resolve().parents[1] / 'presets/reference_size/kelvin_softest_pockets_plate.json'

def preset():
    values = read_preset(PRESET)
    return Settings(**{k:v for k,v in values.items() if k in Settings.__dataclass_fields__})

@pytest.mark.parametrize('offset', [None, 1, [0,0], [0,0,0,0], [True,0,0], [0,'1',0], [0,float('nan'),0], [0,0,float('inf')]])
def test_invalid_offset(offset):
    with pytest.raises(LatticeError, match='lattice-offset'):
        replace(preset(), lattice_offset=offset).check()

def test_gyroid_offset():
    s=Settings('gyroid',(12,12,12),6,wall_thickness=1.2)
    s.check()
    with pytest.raises(LatticeError, match='only for strut patterns'):
        replace(s,lattice_offset=(0,0,.5)).check()

def test_preset_cli_override_and_report():
    s,_=resolve(parser().parse_args(['generate','--config',str(PRESET)]))
    assert s.lattice_offset == [0,0,.5]
    changed,_=resolve(parser().parse_args(['generate','--config',str(PRESET),'--lattice-offset','-1','2','3']))
    assert changed.as_dict()['lattice-offset']==[-1,2,3]
    assert layout(s)==layout(replace(s,lattice_offset=(0,0,0)))

@pytest.mark.parametrize('pattern',['cubic','bcc','octet','diamond','kelvin'])
def test_offset_periodicity_and_default(pattern):
    def keys(edges):
        return {tuple(np.round(edge.ravel(),8)) for edge in edges}
    base=segments(pattern,(13,11,9),4,.5)
    assert np.array_equal(base,segments(pattern,(13,11,9),4,.5,lattice_offset=(0,0,0)))
    assert keys(base)==keys(segments(pattern,(13,11,9),4,.5,lattice_offset=(40,-32,20)))
    shifted=segments(pattern,(13,11,9),4,.5,lattice_offset=(.3,-.7,.5))
    periodic=segments(pattern,(13,11,9),4,.5,lattice_offset=(40.3,-32.7,20.5))
    assert keys(shifted)==keys(periodic)

def test_full_size_kelvin_connectivity_regression():
    s=preset().check()
    axes,_=grid(s)
    xyz=np.meshgrid(*axes,indexing='ij',sparse=True)
    for offset in ((0,0,0),(0,0,.5)):
        current=replace(s,lattice_offset=offset)
        field,_=strut_field(current,axes,lambda _:None)
        z=xyz[2]
        np.minimum(field,np.maximum(-z,z-s.base_thickness),out=field)
        info=apply_pockets(field,axes,current)
        for axis,extent in zip(xyz,s.size):
            np.maximum(field,-axis,out=field)
            np.maximum(field,axis-extent,out=field)
        if offset==(0,0,0):
            with pytest.raises(LatticeError, match='11 disconnected regions') as error:
                validate_regions(field,axes,info)
            assert 'approx_volume_mm3=' in str(error.value)
            assert 'voxel_center_bounds_xyz_mm=' in str(error.value)
        else:
            result=validate_regions(field,axes,info)
            assert result['material_regions']==1 and result['enclosed_voids']==4
        del field
