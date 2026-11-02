# Lattice-to-STL generator

Generate closed, connected 3D lattice solids with dimensions in **millimeters**. Supported patterns: **cubic, BCC, octet, diamond, Kelvin, and sheet gyroid**. Includes plain and four-pocket variants, JSON presets, and optional Blender export.

## Quick start on this device

Open PowerShell in this project directory:

```powershell
cd 'C:\Users\21arn\Documents\CMU\24-673 Soft Robots\soft-robotics\lattice_generator'
.\.venv\Scripts\python.exe -m lattice_generator list-patterns
.\.venv\Scripts\python.exe -m lattice_generator generate --pattern octet --size 24 24 18 --cell-size 6 --strut-diameter 1.2 --output my_octet.stl
.\.venv\Scripts\python.exe -m lattice_generator generate --pattern gyroid --size 24 24 18 --cell-size 6 --wall-thickness 1.2 --base-thickness 1.2 --output my_gyroid.stl
```

The isolated environment is already installed. You can use `python -m lattice_generator` after activating it with `.\.venv\Scripts\Activate.ps1`. The explicit interpreter path above also works when script activation is disabled.

Open the resulting STL in OrcaSlicer. The companion `.json` records the settings, actual dimensions, volume, mesh validation, dependency versions, and numerical resolution.

## Installing elsewhere

Python 3.11+ is supported by the project interface; this installation was tested with **Python 3.14.7 on Windows x64**. The exact dependency snapshot is `requirements-lock.txt`, including test dependencies. Other Python/platform combinations may need compatible versions from `pyproject.toml` rather than the exact snapshot.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

Alternatively install compatible dependencies with `python -m pip install -e ".[test]"` inside a new environment. Blender and PyPI `bpy` are **not required for STL generation**.

## Commands and presets

```powershell
# Load a preset, overriding only the output filename.
.\.venv\Scripts\python.exe -m lattice_generator generate --config presets\diamond.json --output my_diamond.stl

# Inspect an STL without changing it.
.\.venv\Scripts\python.exe -m lattice_generator validate my_diamond.stl

# Save a Blender scene as well as the STL and report.
.\.venv\Scripts\python.exe -m lattice_generator generate --config presets\octet.json --output preview.stl --save-blend preview.blend

# Generate the 12 paired examples (explicit replacement if they exist).
.\.venv\Scripts\python.exe generate_examples.py --overwrite

# Run the test suite.
.\.venv\Scripts\python.exe -m pytest -q
```

CLI values override JSON preset values. Preset keys use hyphens, exactly like CLI options. File paths inside a preset are relative to that preset; paths passed on the command line are relative to the current working directory. Unknown keys fail rather than being ignored.

| Option | Meaning |
|---|---|
| `--pattern` | `cubic`, `bcc`, `octet`, `diamond`, `kelvin`, or `gyroid` |
| `--size W D H` | Clipping-box width, depth, and total height in mm |
| `--cell-size C` | Conventional cubic repeat distance in mm |
| `--strut-diameter D` | Strut diameter, required for the five graph lattices |
| `--wall-thickness T` | Nominal sheet thickness, required for gyroid |
| `--base-thickness B` | Solid bottom plate from Z=0 to Z=B; default 0 |
| `--resolution H` | Maximum grid spacing in mm; smaller is finer |
| `--memory-limit-mib M` | Estimated working-memory limit; default 2048 MiB |
| `--output FILE.stl` | STL path; creates `FILE.json` alongside it |
| `--save-blend FILE.blend` | Optional Blender scene |
| `--blender-path PATH` | Explicit Blender executable if discovery fails |
| `--overwrite` | Permit replacing the requested output files |

Required dimensions and thickness values must be finite and positive. A base must be thinner than the total height. Incompatible thickness options, unresolved features, and excessive estimated memory are rejected before meshing. Exit status is 0 for success, 2 for invalid settings/geometry or an I/O failure, and 130 for cancellation.

## Geometry, dimensions, and phase

The box is `[0,W] × [0,D] × [0,H]`, with Z up. The plate fits **inside** this height. A 20 mm model with a 1 mm base is still 20 mm high.

Cell size is a **repeat distance**, not pore diameter or strut length:

| Pattern | Unit geometry | Interior node degree | Strut length / cell size |
|---|---|---:|---:|
| Cubic | Cube edges | 6 | 1 |
| BCC | Body center to eight cube corners | 8 | √3/2 |
| Octet | FCC nearest-neighbor edges | 12 | 1/√2 |
| Diamond | Diamond-cubic connections | 4 | √3/4 |
| Kelvin | Edges of BCC Voronoi truncated octahedra | 4 | √2/4 |
| Gyroid | Periodic curved sheet | — | — |

The Kelvin cubic repeat contains two truncated-octahedral cells. Its individual polyhedral vertices have degree three, while the full shared-edge tessellation has degree four.

Coordinates use a fixed alignment anchored to the box origin. Cubic, BCC, octet, and Kelvin have zero translation. **Diamond is translated by +C/4 along X.** For gyroid use `X=2π(x/C+1/4)`, `Y=2πy/C`, `Z=2πz/C` in:

```text
sin(X) cos(Y) + sin(Y) cos(Z) + sin(Z) cos(X) = 0
```

These documented quarter-cell alignments avoid the detached corner pieces that zero-phase diamond and gyroid can create in whole-period boxes. The alignment never changes automatically between runs.

Noninteger repeats are trimmed without stretching cells. Neighboring cells are included before clipping so boundary connections are represented. Struts use circular cross-sections with rounded ends; their overlapping material is fused. Clipped cross-sections are closed, while the lattice pores remain open.

Some arbitrary cuts still produce detached pieces, even when all dimensions are valid. The program reports and rejects them instead of discarding geometry. Try whole-repeat dimensions, slightly different box dimensions, a larger thickness, or a base if the fragments touch the bottom. A base cannot reconnect detached fragments near the top. Actual occupied bounds can be smaller than the clipping box when no material reaches a particular face; the report records these bounds.

## Resolution and memory

The default maximum spacing is:

```text
min(0.2 mm, smallest feature thickness / 6, cell size / 24)
```

The smallest feature includes the base when enabled. Each axis uses an integer number of intervals, so the actual spacing can be slightly finer. Explicit resolution must provide at least four samples across the smallest feature and sixteen samples per repeat.

Surfaces are numerical approximations. The report states a geometric checking tolerance of twice the largest actual grid spacing. This is a numerical acceptance tolerance, not a printer accuracy guarantee. Gyroid thickness is nominal: a two-sided distance transform approximates the distance to its sampled surface, with orientation-dependent error on the scale of the grid spacing.

Halving the spacing increases volume samples by approximately eight times and surface triangles by approximately four times. Memory is estimated before allocating the volume, with a default 2 GiB budget. Requests exceeding the estimate fail with suggestions; resolution is never silently reduced. The estimate is a preflight heuristic, not an operating-system memory reservation. Close other large applications or reduce the part if actual available memory is lower. STL files can reach tens of megabytes for detailed samples.

## Validation and output safety

The generator checks finite coordinates, nondegenerate triangles, closed edges, manifold vertex fans, consistent winding, positive volume, and one connected boundary. It also checks that generated geometry stays inside the requested box and reaches the build plane within tolerance. Contained, inward-facing cavity shells are accepted; detached positive solids, nested cavities, and misoriented cavity shells are rejected. `connected_components` counts boundary shells, while `material_bodies` counts positive material bodies.

STL repeats vertices per triangle. On reload only coincident vertices are welded; there is no hole filling, automatic component deletion, or other repair. The reloaded mesh is validated again and compared to the pre-export bounds and volume. Output files are staged and individually published atomically. Existing outputs require `--overwrite`; the collection of STL/report/Blender files is not a multi-file transaction.

STL itself has no unit metadata. Numeric coordinates are millimeters. Blender scenes set `scale_length=0.001` for correct millimeter display. If re-exporting from Blender, use export scale 1 and disable scene-unit scaling to preserve the STL values.

## OrcaSlicer checks

1. Import the examples as separate objects. Keep scale at 100%; the original samples are **24 × 24 × 18 mm** and the paired samples are **36 × 36 × 18 mm**.
2. Select your actual printer, nozzle, material, and layer height. The presets describe geometry and do not configure a printer.
3. Slice and inspect the first layer, interior layers, junctions, and the final layer. Pores should remain open. Gyroid's supplied example has a 1.2 mm solid base, so its first layers are intentionally filled.
4. Look for missing narrow features, floating islands, long bridges, and overhang warnings. Adjust physical dimensions or slicing settings as needed. A valid STL does not imply every orientation is support-free.
5. Slicer infill operates **inside** these modeled struts/walls. It is not the lattice generator itself. Do not substitute slicer infill for the modeled pattern when comparing samples.

See `VALIDATION.md` for the actual tests and slicer observations from this delivery.

## Four sealed magnet pockets

Enable `--pockets four` for four cylindrical holders with sealed magnet cavities. Use `--pockets none` (the default) for a plain lattice. These holders follow the reference pouch concept, but use sealed roofs for insertion during a print pause instead of a flexible retaining lip.

```powershell
.\.venv\Scripts\python.exe -m lattice_generator generate --pattern octet --size 36 36 18 --cell-size 6 --strut-diameter 1.2 --pockets four --output my_octet_pockets.stl
.\.venv\Scripts\python.exe -m lattice_generator generate --config presets\paired\gyroid_pockets.json --output my_gyroid_pockets.stl
.\.venv\Scripts\python.exe generate_examples.py --variants both
```

`--variants plain`, `--variants pockets`, or `--variants both` select the paired outputs. Existing original presets and STLs are preserved. The new presets live in `presets/paired`; output files live in `examples/paired`. Both variants use the same 36 × 36 × 18 mm box, 6 mm repeat, and 1.2 mm lattice thickness. The gyroid pair both include a 1.2 mm base.

| Pocket option | Default | Interpretation |
|---|---:|---|
| `--pockets` | `none` | `none` or `four` |
| `--mesh-above-pockets` | 2 | Distance from holder tops to mesh top, mm; included in total height |
| `--magnet-diameter` | 9.525 | Magnet diameter, mm |
| `--magnet-thickness` | 3.175 | Magnet axial thickness, mm |
| `--pocket-diameter-clearance` | 0.3 | Total **diametral**, not radial, clearance, mm |
| `--pocket-height-clearance` | 0.2 | Total axial clearance, mm |
| `--pocket-wall-thickness` | 1 | Radial holder wall, mm |
| `--pocket-floor-thickness` | 1 | Material below the cavity, mm |
| `--pocket-roof-thickness` | 1 | Material above the cavity, mm |

All options are also valid hyphenated preset keys. The cavity defaults to **9.825 mm diameter × 3.375 mm high**, inside an **11.825 mm diameter holder**. Clearances are initial tuning values, not a verified physical fit.

The holder centers are `(W/4,D/4)`, `(3W/4,D/4)`, `(W/4,3D/4)`, and `(3W/4,3D/4)`. Holder tops sit below the box top by `--mesh-above-pockets` (default **2 mm**). A zero value restores flush holders. `--size W D H` always includes this lattice extension; no height is added to H. For an 18 mm-high model, holders start at **Z=10.625 mm**, cavities extend from **Z=11.625 to 15 mm**, and roofs occupy **Z=15 to 16 mm**. The lattice continues to **Z=18 mm**. The overall height remains 18 mm.

The generator first unions the holder cylinders into the lattice/base and then subtracts the cavities from the entire material field. Lattice struts and gyroid sheets cannot remain inside the intended cavity. It checks connected material and four enclosed air regions before surface extraction, then checks shell containment, cavity position, full cavity-boundary deviation from the intended cylinders, and dimensions before and after STL export. It does not silently reconnect detached holders or drop islands.

Holder-to-holder and holder-to-box side gaps must be at least two grid spacings. Floors, walls, roofs, and cavity dimensions must have at least four samples across them; automatic resolution uses six samples across the smallest feature. Default pocket examples therefore use approximately **0.167 mm** spacing. The original 24 mm-wide examples are too narrow for these default magnets plus the required margin; use the larger paired presets.

### Inserting the magnets during printing

1. Import a pocketed STL at 100% scale and choose the actual printer, nozzle, and filament profile.
2. Slice and inspect a cross-section below the pocket floor, through the cavity, and through the roof. Four circular empty interiors should appear during the cavity section; lattice material must not cross them.
3. Locate the **first roof extrusion** in the actual layer preview and insert a pause immediately before that layer, after the cavities have finished printing. The nominal roof start is **15 mm** for the supplied examples. Meshing and slicer layer sampling affect the observed transition: do not infer a layer number by rounding 15/layer-height.
4. At the pause, place the four magnets into the cavities and verify that each is fully seated **below the next print path** before resuming. No printer-specific pause G-code is generated by this program.
5. Resume to close the roofs. Check that the chosen bridging and extrusion settings can span the pocket openings. Avoid supports inside the cavities; they would obstruct magnet insertion.

The JSON report contains the resolved pocket dimensions, holder centers, cavity bounds, measured cavity sizes, numerical tolerance, and nominal roof-start elevation. Use `--save-blend` to inspect the same mesh in Blender; a viewport clipping region or a temporary section cut on a duplicate reveals the internal cavities without changing the exported STL.

## Project layout and extension

The package separates `config`, `patterns`, `meshing`, `validation`, `export`, and optional `blender_export`/`blender_worker` modules. `patterns.motif()` defines graph edges in exact quarter-cell coordinates; periodic copies are deduplicated before scaling. To add a graph pattern, define its motif and fixed phase, register its description and preflight estimate, then add topology and generated-solid tests.

Version one has no GUI, arbitrary outer shapes, graded geometry, mechanical simulation, or automatic printer/support profiles. It uses verified geometric constructions rather than the approximate AI-generated reference image.

References: [scikit-image marching cubes](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.marching_cubes), [trimesh](https://trimesh.org/), [Blender Python API](https://docs.blender.org/api/current/), [bpy packaging requirements](https://pypi.org/project/bpy/).

The reference eFlesh-DefaultCuboid(1).stl has total Z bounds 0 to 24.324 mm and substantial holder-top faces around Z=14 to 14.003 mm. For a similar vertical separation, use --mesh-above-pockets 10.321 with sufficient total height. This setting changes vertical placement only; it does not reproduce the reference lattice or holder design. Older example STLs must be regenerated to apply the new default.


## Reference-sized pocketed collection

Run `python generate_examples.py --plates both` to generate 20 pocketed samples in
`meshes/reference_size`. Use `--plates plate` or `--plates no-plate` to select a base.
Existing files require `--overwrite`. Presets are in `presets/reference_size`.
All models are 43 x 43 x 24.324 mm. Plates occupy Z=0 to 0.6 mm within this height.
Magnets are 10 mm diameter x 2.7 mm high; cavities are 10.3 x 2.9 mm, with 1 mm
walls, floor, and roof. Pocket midplanes are Z=11.60 mm; roof extrusion starts
nominally at Z=13.05 mm. Locate the actual transition in OrcaSlicer preview and
pause before roof extrusion; ensure magnets sit below the next toolpath.

`--pocket-midplane-height` anchors cavities from the bottom independently of model
height. It cannot be combined with `--mesh-above-pockets`. With neither option,
the legacy 2 mm extension remains. `--require-exact-bounds` checks all six bounds
within 0.001 mm without scaling geometry. Physical print accuracy is separate.

Kelvin candidates use pitch/strut pairs 6/1.2, 8/1.0, and 10/0.8 mm; gyroid uses
pitch/wall pairs 6/1.2, 8/0.8, and 10/0.6 mm. Softer labels are hypotheses for TPU.
Compare X, Y, Z compression at 10%, 20%, 30% and recovery using the same material,
print settings, and magnet state. Compare plate variants separately. Record force,
permanent deformation, and magnet fit. Slicer inspection and physical testing are
required before claiming a softness ranking.


## Export simplification

The fine creation grid is retained. Before export, outer surfaces are simplified
with a default `--simplify-tolerance 0.05` mm. Set it to zero to disable.
Enclosed cavity shells are retained verbatim. Candidate surfaces must preserve
bounds within 0.001 mm, pass manifold and cavity checks, and pass a conservative
bidirectional surface-distance certificate. Unresolved distance checks reject the
candidate. Attempts retain 10%, 25%, then 50% of outer triangles; if none passes,
the original mesh is exported. Reports record acceptance, counts and certified
error. STL reload validation still runs. Existing STLs are not modified automatically.

### Simplification review tolerance and diagnostics

Simplification permits at most 0.05 mm movement of the occupied bounds. The
original generated mesh still undergoes the strict 0.001 mm bounds check;
accepted simplified meshes use the 0.05 mm bounds threshold during validation
and STL reload. The surface-distance tolerance remains independently controlled
by `--simplify-tolerance` (default 0.05 mm). Pocket shells remain unchanged.

Each rejected attempt logs its retained fraction and failure reason: bounds
movement, individual mesh-validation errors, directed surface-distance violations,
or an unresolved distance certificate at its work/subdivision limit. Reports
retain these messages in `meshing.simplification.attempts`, along with triangle
counts and bounds drift. A failed simplification still retains the original mesh;
check `accepted` before treating an output as reduced.

Distance certification uses both centroid covering balls and a conservative
convex target-triangle bound, in larger query batches. It reports progress every
30 seconds while processing blocks; this does not replace the full bidirectional
surface certificate with sampling.

### Lattice translation and Kelvin softest

`--lattice-offset X Y Z` (JSON: `"lattice-offset": [X, Y, Z]`) translates
strut lattices in millimeters, in addition to the pattern's built-in phase.
The default is `[0, 0, 0]`. The clipping box, base plate, and magnet pockets stay
fixed. Cubic, BCC, octet, diamond, and Kelvin support translation; gyroid rejects
nonzero offsets. Reports record the offset in settings and meshing metadata.

The Kelvin softest plate preset uses `[0, 0, 0.5]`. Its former alignment left ten
small detached pieces at the top box edges. Moving the lattice up 0.5 mm removes
that clipping configuration while retaining the 43 x 43 x 24.324 mm box, 10 mm
pitch, 0.8 mm struts, and fixed four-pocket layout. Other presets retain their
existing alignments. Disconnected-region failures now list voxel counts,
approximate volumes, and voxel-center bounding boxes; components are never
silently deleted.
