# Lattice-to-STL generator

Generate closed, connected 3D lattice solids with dimensions in **millimeters**. Supported patterns: **cubic, BCC, octet, diamond, Kelvin, and sheet gyroid**. Includes six generated examples, JSON presets, and optional Blender export.

## Quick start on this device

Open PowerShell in this project directory:

```powershell
cd 'C:\Users\21arn\Documents\CMU\24-673 Soft Robots\lattice_generator'
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

# Regenerate all six delivered examples (explicit replacement).
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

The generator checks finite coordinates, nondegenerate triangles, closed edges, manifold vertex fans, consistent winding, positive volume, and one connected boundary. It also checks that generated geometry stays inside the requested box and reaches the build plane within tolerance. Nested closed cavity shells are conservatively rejected as multiple boundaries in this version.

STL repeats vertices per triangle. On reload only coincident vertices are welded; there is no hole filling, automatic component deletion, or other repair. The reloaded mesh is validated again and compared to the pre-export bounds and volume. Output files are staged and individually published atomically. Existing outputs require `--overwrite`; the collection of STL/report/Blender files is not a multi-file transaction.

STL itself has no unit metadata. Numeric coordinates are millimeters. Blender scenes set `scale_length=0.001` for correct millimeter display. If re-exporting from Blender, use export scale 1 and disable scene-unit scaling to preserve the STL values.

## OrcaSlicer checks

1. Import the examples as separate objects. Keep scale at 100%; each supplied sample's envelope is **24 × 24 × 18 mm**.
2. Select your actual printer, nozzle, material, and layer height. The presets describe geometry and do not configure a printer.
3. Slice and inspect the first layer, interior layers, junctions, and the final layer. Pores should remain open. Gyroid's supplied example has a 1.2 mm solid base, so its first layers are intentionally filled.
4. Look for missing narrow features, floating islands, long bridges, and overhang warnings. Adjust physical dimensions or slicing settings as needed. A valid STL does not imply every orientation is support-free.
5. Slicer infill operates **inside** these modeled struts/walls. It is not the lattice generator itself. Do not substitute slicer infill for the modeled pattern when comparing samples.

See `VALIDATION.md` for the actual tests and slicer observations from this delivery.

## Project layout and extension

The package separates `config`, `patterns`, `meshing`, `validation`, `export`, and optional `blender_export`/`blender_worker` modules. `patterns.motif()` defines graph edges in exact quarter-cell coordinates; periodic copies are deduplicated before scaling. To add a graph pattern, define its motif and fixed phase, register its description and preflight estimate, then add topology and generated-solid tests.

Version one has no GUI, arbitrary outer shapes, graded geometry, mechanical simulation, or automatic printer/support profiles. It uses verified geometric constructions rather than the approximate AI-generated reference image.

References: [scikit-image marching cubes](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.marching_cubes), [trimesh](https://trimesh.org/), [Blender Python API](https://docs.blender.org/api/current/), [bpy packaging requirements](https://pypi.org/project/bpy/).
