"""Validate an STL round trip before publishing output files."""

from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

import numpy as np

from . import __version__
from .blender_export import find_blender, save_blend
from .config import LatticeError
from .meshing import generate_mesh
from .patterns import PHASES
from .validation import load_mesh, require_valid, validate_mesh


def publish(source, target, overwrite):
    """Publish a complete file atomically; never expose a partially copied STL."""
    fd, name = tempfile.mkstemp(prefix=".lattice-publish-", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as destination, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, destination)
            destination.flush()
            os.fsync(destination.fileno())
        if overwrite:
            os.replace(temporary, target)
        elif os.name == "nt":
            os.rename(temporary, target)  # Windows rename fails if destination exists.
        else:
            os.link(temporary, target)  # Atomic exclusive publication on POSIX.
    finally:
        temporary.unlink(missing_ok=True)


def generate(settings, output, save_blend_path=None, blender_path=None, overwrite=False, log=print):
    settings.check()
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != ".stl":
        raise LatticeError("Output filename must end in .stl.")
    report_path = output.with_suffix(".json")
    blend_path = Path(save_blend_path).expanduser().resolve() if save_blend_path else None
    if blend_path and blend_path.suffix.lower() != ".blend":
        raise LatticeError("save-blend filename must end in .blend.")
    targets = [output, report_path] + ([blend_path] if blend_path else [])
    for path in targets:
        if path.exists() and not overwrite:
            raise LatticeError(f"Output already exists: {path}. Use --overwrite explicitly to replace it.")
        if path.exists() and not path.is_file():
            raise LatticeError(f"Output is not a regular file: {path}")
    executable = find_blender(blender_path) if blend_path else None
    start = time.perf_counter()
    mesh, details = generate_mesh(settings, log)
    log("Checking topology, connectedness, and volume")
    tolerance = 2 * max(details["spacing_mm"])
    original = validate_mesh(mesh, settings.size, tolerance)
    require_valid(original)
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
    # Stage on the same volume as the final STL; no output is published before
    # the binary STL has been reloaded and validated.
    with tempfile.TemporaryDirectory(prefix=".lattice-", dir=output.parent) as temporary:
        staging = Path(temporary)
        staged_stl = staging / "mesh.stl"
        mesh.export(str(staged_stl), file_type="stl")
        reloaded = load_mesh(staged_stl)
        checked = validate_mesh(reloaded, settings.size, tolerance)
        require_valid(checked)
        if not np.allclose(reloaded.bounds, mesh.bounds, rtol=0, atol=1e-4):
            raise LatticeError("STL round trip changed bounds or units.")
        if not np.isclose(reloaded.volume, mesh.volume, rtol=1e-4, atol=1e-6):
            raise LatticeError("STL round trip changed enclosed volume.")
        if blend_path:
            log("Saving optional Blender scene")
            save_blend(staged_stl, staging / "mesh.blend", executable)
        report = {
            "generator_version": __version__, "created_utc": datetime.now(timezone.utc).isoformat(),
            "units": "mm", "settings": settings.as_dict(), "meshing": details,
            "phase": {"cell_fractions": PHASES[settings.pattern],
                      "convention": "strut translation; gyroid coordinate offset in its equation"},
            "geometric_tolerance_mm": tolerance, "validation": checked,
            "stl_round_trip_validated": True, "elapsed_seconds": time.perf_counter() - start,
            "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-image", "trimesh")},
            "files": {"stl": str(output), "report": str(report_path), "blend": str(blend_path) if blend_path else None},
            "notes": ["STL has no unit metadata; numeric coordinates are millimeters.",
                      "Grid meshing approximates surfaces; actual occupied bounds may be smaller than the clipping box.",
                      "Geometric validation does not establish support-free printability.",
                      "Gyroid wall thickness is nominal and has grid-dependent variation."] if settings.pattern == "gyroid" else
                     ["STL has no unit metadata; numeric coordinates are millimeters.",
                      "Grid meshing approximates surfaces; actual occupied bounds may be smaller than the clipping box.",
                      "Geometric validation does not establish support-free printability."]
        }
        staged_report = staging / "report.json"
        staged_report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for source, target in [(staged_stl, output), (staged_report, report_path)] + ([(staging / "mesh.blend", blend_path)] if blend_path else []):
            publish(source, target, overwrite)
        log(f"Saved {output} ({checked['triangles']:,} triangles, {checked['volume_mm3']:.1f} mm^3)")
        return report
