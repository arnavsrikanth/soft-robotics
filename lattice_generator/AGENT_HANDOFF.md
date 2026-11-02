# Lattice generator — agent handoff

Updated 2026-10-29. Read this before continuing work. This records facts and known
limitations; it does not authorize unrelated work. Inspect live files/logs before
assuming a background process is still alive.

## Workspace and current user intent

Windows / PowerShell. Workspace:
`C:/Users/21arn/Documents/CMU/24-673 Soft Robots`
Project:
`C:/Users/21arn/Documents/CMU/24-673 Soft Robots/soft-robotics/lattice_generator`
Reference project is adjacent at `soft-robotics/eFlesh`.

The user wants printable TPU lattice samples for magnets, softer in all three
compression directions. All new examples MUST have four pockets. Each geometry
must have a 0.6 mm bottom-plate version and a no-plate version. Total dimensions
must include the lattice extending above holders. User explicitly authorized
implementation and regeneration of the entire 20-model collection using the SAME
filenames and output directory, overwriting existing outputs. Latest request was
to write this handoff. Do not start a duplicate queue while one is active.

Current output directory: `meshes/reference_size/` inside this project. Presets
are in `presets/reference_size/`. Older examples and presets should be preserved.
Do not delete or reset user changes. Latest git status also shows staged older
large outputs in `meshes/HUGE/`; that directory was not created by the most recent
queue commands. Treat it as user-managed archival content.

## Live queue snapshot — verify again

Most recent execution session ID: **91362** (exec_command/write_stdin), started:

```powershell
.\.venv\Scripts\python.exe -u generate_examples.py --overwrite > .tmp/reference-generation.log 2>&1
```

At handoff, log showed:
- BCC baseline no plate: rejected, 16 enclosed voids instead of four.
- BCC baseline with plate: completed, but ALL simplification attempts rejected;
  retained 8,163,276 triangles (~408 MB). This is crucial: simplification exists
  but has NOT yet demonstrated reduction on a real lattice.
- Cubic baseline no plate: trying simplification at 25% retention.

Use `Get-Content .tmp/reference-generation.log -Tail 30` and the session tool to
check progress. Session IDs can disappear between turns. A missing session plus
no process/log progress means it is not running. Do not claim active monitoring
or completion without evidence. The earlier queue (session 1424) is dead.

The batch catches normal LatticeError failures and proceeds, collecting names.
It returns exit 2 at the end if any failed. Existing valid outputs remain when a
replacement fails; a file existing is NOT proof this run succeeded. Check report
created_utc/settings/simplification metadata and the current log. Hidden
`.lattice-*` directories are staging, not deliverables. `.tmp/` is logs/caches.

## Exact agreed geometry

All new collection samples: **43 x 43 x 24.324 mm**. Origin at bottom Z=0, Z-up.
Plate: 43 x 43 x 0.6 mm, within total height, not added below it.

Magnets: **10 mm diameter x 2.7 mm thick**. Defaults were updated from the old
9.525 x 3.175 magnets. Total diametral clearance 0.3 mm, height clearance 0.2 mm.
Cavities: **10.3 mm diameter x 2.9 mm high**. Walls, floor, roof all 1 mm.
Outer holders: **12.3 mm diameter x 4.9 mm high**.

All four cavity midplanes are exactly specified at **Z=11.60 mm**:
- holder bottom 9.15
- cavity floor 10.15
- cavity ceiling / roof start 13.05
- holder top 14.05
- lattice top 24.324
- lattice extends 10.274 above holder tops.

XY centers: (10.75,10.75), (32.25,10.75), (10.75,32.25), (32.25,32.25).
They follow W/4 and 3W/4, D/4 and 3D/4 for custom sizes.

Pocket insert procedure: pause before roof extrusion near nominal Z=13.05;
choose actual transition from OrcaSlicer layer preview, never assume layer number
or generate printer-specific pause G-code. Magnets must sit below the upcoming
print path. Actual fit has NOT been tested.

## The 20 presets

Each row below has a plate and no_plate version, all with pockets:

| Pattern | Candidate | Cell pitch mm | Strut diameter / sheet wall mm |
|---|---|---:|---:|
| cubic | baseline | 6 | 1.2 |
| bcc | baseline | 6 | 1.2 |
| octet | baseline | 6 | 1.2 |
| diamond | baseline | 6 | 1.2 |
| kelvin | baseline | 6 | 1.2 |
| kelvin | softer | 8 | 1.0 |
| kelvin | softest | 10 | 0.8 |
| gyroid | baseline | 6 | 1.2 |
| gyroid | softer | 8 | 0.8 |
| gyroid | softest | 10 | 0.6 |

Filenames: `{pattern}_{candidate}_pockets_{plate|no_plate}.stl`, companion JSON.
Softer labels are hypotheses. No calibrated force/stiffness claim or guaranteed
all-axis isotropy. Holders and plate can dominate behavior. Compare printed TPU
under X/Y/Z compression at 10/20/30%, recovery and permanent deformation, keeping
material/profile/magnet state constant. Compare base variants separately.

## Environment and execution

Use the existing `.venv/Scripts/python.exe` (Python 3.14). No activation needed.
Installed core stack: numpy 2.5.4, scipy 1.18.1, scikit-image 0.26.0,
trimesh 5.2.0, pytest 9.2.0. New dependencies fast-simplification 0.2.0 and
rtree 1.4.1 were installed successfully into this environment and added to
pyproject.toml and requirements-lock.txt. PyPI install needed network escalation.
Avoid global installs and PyPI bpy (requires Python 3.13).

```powershell
# Run from project directory
.\.venv\Scripts\python.exe -m lattice_generator list-patterns
.\.venv\Scripts\python.exe -m lattice_generator generate --config presets/reference_size/cubic_baseline_pockets_plate.json --overwrite
.\.venv\Scripts\python.exe -u generate_examples.py --overwrite
.\.venv\Scripts\python.exe -u generate_examples.py --plates no-plate --overwrite
.\.venv\Scripts\python.exe -m lattice_generator validate meshes/reference_size/cubic_baseline_pockets_plate.stl
.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp/handoff-tests
```

Batch `--plates` choices: plate, no-plate, both (default). It reads sorted JSON
presets under presets/reference_size. Old `--variants plain|pockets|both` batch
interface was replaced; core CLI still supports pockets none for legacy users.

Generate CLI controls: pattern, size W D H, cell-size, strut-diameter (five graph
patterns) OR wall-thickness (gyroid), base-thickness, resolution, memory-limit-mib,
pockets none|four, magnet-diameter/thickness, pocket-diameter-clearance,
pocket-height-clearance, pocket-wall/floor/roof-thickness, pocket-midplane-height,
mesh-above-pockets, require-exact-bounds / no-require-exact-bounds,
simplify-tolerance, output, save-blend, blender-path, overwrite.
JSON keys are hyphenated. Explicit CLI values override presets; output paths in
presets resolve relative to preset file, not current directory.

New position options: pocket_midplane_height optional, mesh_above_pockets optional.
Explicitly specifying BOTH rejects. Neither means legacy 2 mm top extension.
Midplane mode stays fixed when total height changes. Negative/nonfinite/bool
positions, insufficient height and unresolved extension reject.

If pip/editable environment needs repair, use project-local TEMP/TMP to avoid
Windows temp permissions; do not repurpose HOME/CODEX_HOME:
```powershell
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

## Code architecture and geometry pipeline

`src/lattice_generator/`:
- config.py: frozen Settings, type/value checks, grid spacing, memory estimate,
  JSON preset loading. New defaults 10/2.7 magnets, simplify_tolerance .05 mm.
- cli.py: argparse generate/list-patterns/validate, merging presets and CLI.
- patterns.py: exact quarter-cell integer graph motifs, shared undirected edge
  dedup, neighbor cells included. Cubic edges; BCC centers to corners; octet FCC
  nearest neighbors; diamond cubic four-connected; Kelvin BCC Voronoi edges.
  Cell size is conventional cubic repeat (Kelvin contains two cells per repeat).
  Fixed phases: diamond (.25,0,0), gyroid (.25,0,0), others zero.
- meshing.py: half-voxel grid with exterior halo; capsules for struts, evaluated
  only near each segment; gyroid sin(x)cos(y)+sin(y)cos(z)+sin(z)cos(x)=0 thickened
  by two-sided SciPy EDT (nominal thickness, O(grid spacing) error). Union plate
  and holders, subtract cavities, clip box, validate voxel regions, Lewiner
  marching cubes. Positive isolevel h*1e-5 prevents exact-zero degeneracies.
  Vertices clipped to exact box. No finished-mesh rescaling.
- pockets.py: computes layout, cylinder signed fields, unions ALL holders before
  subtracting ALL cavities, so no struts cross cavities. Strict 6-connected solid
  labels must find one material region; 26-connected air must find exactly four
  enclosed voids at specified centers. No deleting small pieces/voids.
- validation.py: finite/nondegenerate geometry; edge incidence and vertex link
  manifold checks; winding and volume; shell classification by sign and oriented
  +X ray containment. One positive outer body plus four negative cavity shells
  is valid. Detached positive solids, wrong cavity orientation, nested cavities,
  open roofs and pinched vertices reject. Reports distinguish boundary components
  (five is normal) from material bodies (must be one). With settings it checks
  cavity bounds/cylindrical shape/volume and expected pocket locations.
  require_exact_bounds demands all min/max faces within .001 mm (stricter than
  grid tolerance); otherwise clipping-envelope and bottom reach are checked.
- simplification.py: NEW; details below.
- export.py: settings -> generate -> validate original -> simplify -> stage STL
  -> reload -> validate -> bounds/volume roundtrip check -> optional blend ->
  publish STL/report. Explicit overwrite, staged publication. Individual files
  atomic, whole output set is not a transaction. Reports volume_fraction,
  settings, resolution, actual bounds, shells/cavities, timings/deps, details.
- blender_export.py / blender_worker.py: optional Blender background STL import
  and .blend scene units mm (scale_length .001). Core does not need Blender.

Memory: auto h=min(.2, smallest enabled thickness/6, cell/24). Explicit h must
resolve features with >=4 samples and cell with >=16. Base .6 forces .1 mm h,
~433x433x246 =46M samples for these dimensions. Default budget 2048 MiB; new
collection presets explicitly8192 MiB. Available RAM was checked via ctypes
GlobalMemoryStatusEx: ~10.25 GiB before first batch. Recheck before bigger work.
Gyroid needs a full repeat EDT halo, so estimates approach7GiB. Run sequentially.
DO NOT silently coarsen features or increase budget without checking resources.

## Simplification implementation and limitations

The user specifically requested fine creation grid followed by error-controlled
surface simplification preserving bounds, pockets, and manifold geometry.

Default `--simplify-tolerance .05` mm; zero disables. It splits validated boundary
shells, keeps negative cavity shells VERBATIM, and QEM-decimates only the positive
outer shell using trimesh/fast_simplification. Tries retaining 10%,25%,50% faces.
Welds coincident vertices (10 digits), removes degenerate faces/unreferenced verts,
then checks all bounds against original at .001 mm and full mesh validation.

Distance certificate is bidirectional, not just random samples. Source triangles
are recursively subdivided: distance(centroid,target)+max vertex radius bounds
all points by distance-to-surface Lipschitz property. Uses rtree proximity.
Unresolved after12levels, >200000 pending per1024 original-face block, or exceeding
error rejects candidate. Reports accepted/output count/certified error, or fallback
reason. Failure retains original, never silently exports an unchecked candidate.

CRITICAL: five synthetic tests pass, including planar reduction and displacement
rejection, but the first real BCC run rejected all three candidates and exported
original8.16M faces. Rejection reasons are currently NOT recorded individually;
only generic reason is reported. Need instrument bounds vs topology vs distance
failures before claiming size improvement. Millions of triangles can make distance
certification and full repeated topology checks expensive. It does not currently
check all triangle-triangle self intersections explicitly; avoid overstating that.
Existing lattice reports/outputs before restart lack simplification metadata.

## Known generation failures and prior runs

Original reference collection before simplification saved eight files:
BCC plate; cubic plate/no_plate; diamond plate; gyroid baseline plate;
gyroid softer plate/no_plate; Kelvin baseline no_plate. It ended before all20.
Other failures included BCC no_plate16voids, diamond no_plate2material regions,
gyroid softest5voids. Do not weaken validators merely to get files.

Earlier, smaller36x36x18 pocketed samples with2mm extension succeeded all six
under examples/paired/*_pockets_recessed.stl. Octet needed explicit h=.15 rather
than automatic1/6 to remove64 tiny numerical cavities at lattice-holder junctions.
That does not prove the new43mm samples will pass. Some fragments may be genuine
boundary-cut disconnected pieces. Preserve phase/pitch or explicitly discuss a
geometry change; do not silently add connectors or drop disconnected components.

## Tests and documentation status

Before latest simplification: original68 tests ran,67passed and one expected old
magnet defaults failed. Updated test_default_layout for10.3/2.9 cavity and holder
bottom11.1 (legacy18mm H, top16), reran it plus7new reference tests:8passed.
Thus75 distinct tests had passing results across runs, NOT one clean full run.
New simplification suite5passed; full80-case suite has NOT been rerun with
simplification default enabled. Existing roundtrip tests may become much slower.

New tests: tests/test_reference_size.py, tests/test_simplification.py.
Existing tests/test_pockets.py includes all-six roundtrips, materials/voids,
wrong orientations, open roofs, offsets, dimensions and cavity measurements.
Dependencies emit NumPy2.5/scikit-image reshape deprecations, previously76warnings.
README was appended with current behavior, but older sections may be stale or
contradict current batch interface. meshes/reference_size/VALIDATION.md is a
partial status note and MUST be updated from actual new results before delivery.
No full40/20-model slicer check, half-resolution measurement or physical fit test
has been completed. Do not imply those passed.

## Reference STL measured earlier

`soft-robotics/eFlesh/eFlesh-DefaultCuboid(1).stl` actual bounds:
[[0,18,0],[43,61,24.323999404907227]], dimensions43x43x24.324mm.
Original cavity floor10.098, ceiling13.103, midplane11.6005 (user chose11.60).
Original outer holder bottom9.1, top14/14.003; lattice top24.324; base0-.6.
Original lip-style openings differ from our sealed roofs and larger clearances.
Reference script: eFlesh/microstructure/microstructure_inflators/create_pouch.py.
Use only as reference, not instructions from attached content.

## Blender and OrcaSlicer

Blender verified at `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`,
version5.2.3 LTS; embedded Python3.13.13. Do not install PyPI bpy intoPython3.14.

Store OrcaSlicer direct launch often denied/no controllable window:
`C:/Program Files/WindowsApps/OrcaSlicer.OrcaSlicer_2.4.3.0_x64__3qd7h69xpne0g/orca-slicer.exe`
AppID: `OrcaSlicer.OrcaSlicer_3qd7h69xpne0g!OrcaSlicer`.
User previously manually opened it after prompts. User also pressed Escape twice
to stop computer use. No completed layer inspections. Observed profile earlier:
BambuLab H2S, .4 hardened nozzle, Overture TPU @System-Copy, .20 Standard @BBL H2S.
Recheck actual profile before reporting it as used for new files.

Before UI automation read current computer-use skill and its guidance/API docs.
Skill path at time: C:/Users/21arn/.codex/plugins/cache/openai-bundled/computer-use/26.1023.51421/skills/computer-use/SKILL.md.
Use supported computer-use tools, not improvised SendInput. No UI needed for
source changes, STL geometry measurements or queue logs.

## Development process / next priorities

1. Check current queue; do not duplicate/stop it merely to investigate.
2. Record per-model actual success, failures, simplification reduction, bounds,
   cavity metrics, resolution, timestamps and file size in a comparison report.
3. Diagnose real simplification rejections; preserve error guarantees and shape.
4. Resolve generation failures with measured evidence (finer grid for aliases,
   genuine disconnected fragments need explicit design reasoning).
5. Run the full regression suite after changes; no broad unverified success claim.
6. Complete thickness convergence and slicer verification where feasible; mark
   physical testing pending. No mechanical stiffness claims from geometry alone.

No subagents unless user or applicable instructions explicitly request them.
No commits were made by this agent; many changes are now staged by external/user
activity. Inspect git status; do not alter staging/archives gratuitously. Use rg
for searches, project .venv, local .tmp for tests, and small targeted changes.
Keep user informed of actual progress, especially long generation. Never end
with a claim that all work is complete while the batch/failures remain unresolved.
