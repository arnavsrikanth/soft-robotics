# Run the lattice generator (Windows / PowerShell)

The project environment is `.venv`, using Python 3.14.7. It includes the runtime dependencies from `pyproject.toml`, all pinned packages in `requirements-lock.txt`, and pytest. The generator is installed in editable mode from this directory, so Python source changes take effect without reinstalling.

## Start here

```powershell
Set-Location 'C:\Users\21arn\Documents\CMU\24-673 Soft Robots\soft-robotics\lattice_generator'
.\.venv\Scripts\Activate.ps1
python -m lattice_generator list-patterns
```

Check which Python you are using:

```powershell
python -c "import sys; print(sys.executable)"
python -m pip check
```

The executable should end in `lattice_generator\.venv\Scripts\python.exe`.

Activation is optional. This works from the project folder even if PowerShell blocks activation:

```powershell
.\.venv\Scripts\python.exe -m lattice_generator list-patterns
```

## Generate a reference-sized sample

Start with one preset. This requests a 43 x 43 x 24.324 mm BCC lattice with four 10.3 mm diameter magnet cavities and a 0.6 mm base plate:

```powershell
python -u -m lattice_generator generate --config presets/reference_size/bcc_baseline_pockets_plate.json --output meshes/my_samples/bcc_plate.stl
```

The command creates the output folder and writes both `bcc_plate.stl` and a JSON settings/validation report. It refuses to overwrite existing outputs. Add `--overwrite` only when you want to replace them.

To generate Kelvin or gyroid, select the corresponding preset:

```powershell
python -u -m lattice_generator generate --config presets/reference_size/kelvin_baseline_pockets_plate.json --output meshes/my_samples/kelvin_plate.stl
python -u -m lattice_generator generate --config presets/reference_size/gyroid_baseline_pockets_plate.json --output meshes/my_samples/gyroid_plate.stl
```

Presets named `no_plate` omit the bottom plate. All reference-size presets request four pockets. Baseline/softer/softest presets are geometry candidates, not measured stiffness grades.

Reference-sized models can need several GiB of RAM and lengthy certification. Run them sequentially. Some reference geometries have known validation failures; successful environment setup does not establish that all 20 presets will generate successfully. The newer 43 mm collection has not been fully verified with the updated simplifier.

## Change parameters

Command-line arguments override preset settings. For example:

```powershell
python -u -m lattice_generator generate --config presets/reference_size/kelvin_baseline_pockets_plate.json --cell-size 8 --strut-diameter 1.0 --output meshes/my_samples/kelvin_custom.stl
```

Dimensions are millimeters. Use `--strut-diameter` for cubic, BCC, octet, diamond, and Kelvin; use `--wall-thickness` for gyroid. Grid resolution is automatic unless `--resolution` is supplied. Changing dimensions, pitch, or thickness can change connectivity and cause a legitimate validation failure.

The default surface simplification tolerance is 0.05 mm. Bounds review also allows 0.05 mm drift for accepted simplified meshes. `--simplify-tolerance 0` disables simplification and can produce very large STLs. If simplification rejects every candidate, generation retains the original mesh. Check `meshing.simplification.accepted` and per-attempt failure messages in the output JSON.

Paths supplied on the command line resolve from your current folder. Paths written inside a JSON preset resolve relative to that preset file.

## Validate or inspect output

```powershell
python -m lattice_generator validate meshes/my_samples/bcc_plate.stl
python -m lattice_generator generate --help
```

The `validate` command checks mesh geometry without a preset. The JSON produced during generation additionally contains the settings-aware pocket checks and simplification certificate. Neither check establishes physical fit or slicer printability.

Save a console log when generating:

```powershell
python -u -m lattice_generator generate --config presets/reference_size/bcc_baseline_pockets_plate.json --output meshes/my_samples/bcc_logged.stl 2>&1 | Tee-Object -FilePath bcc-generation.log
```

## Generate the collection

These commands use the preset output paths under `meshes/reference_size`:

```powershell
python -u generate_examples.py --plates plate
python -u generate_examples.py --plates no-plate
# Or all 20 presets:
python -u generate_examples.py --plates both
```

Choose one command; `both` already includes the two subsets. Add `--overwrite` to replace existing outputs. The batch continues after normal geometry failures and returns exit code 2 if any model fails. Inspect its final failure list and each model's report.

## Optional Blender output

STL generation does not require Blender or the Python `bpy` package. To also save a Blender scene, supply an installed Blender executable if discovery fails:

```powershell
python -u -m lattice_generator generate --config presets/reference_size/bcc_baseline_pockets_plate.json --output meshes/my_samples/bcc_blender.stl --save-blend meshes/my_samples/bcc_blender.blend --blender-path 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

## Rebuild the environment if needed

The current environment is already prepared. For a fresh `.venv`, run the following from the project folder using this machine's base Python installation. Preserve an existing working environment before replacing it.

```powershell
& "$env:USERPROFILE\miniconda3\python.exe" -m venv .venv
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e '.[test]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\Activate.ps1
```

On another machine, use a compatible Python interpreter in place of the Miniconda path. This locked package set was verified with Python 3.14.7. Installing packages on a fresh machine needs access to the package index.

To run the targeted simplification tests:

```powershell
python -m pytest tests/test_simplification.py -q --basetemp .tmp/my-simplification-tests
```

When finished:

```powershell
deactivate
```

## Translate a strut lattice inside the box

Use `--lattice-offset X Y Z` in millimeters, or `"lattice-offset": [X, Y, Z]` in
a preset. The offset adds to the pattern's built-in phase and moves only the
struts. The box, plate, and pockets stay fixed. A nonzero offset is not supported
for gyroid.

The Kelvin softest plate preset now supplies a 0.5 mm upward offset to avoid
small disconnected fragments at the top edges. You can use the original command:

```powershell
python -u -m lattice_generator generate --config presets/reference_size/kelvin_softest_pockets_plate.json --output meshes/my_samples/kelvin_softest_plate.stl
```

If the output already exists, add `--overwrite` to replace it deliberately.
