"""Optional subprocess integration; bpy is only imported by Blender itself."""

import os
from pathlib import Path
import shutil
import subprocess

from .config import LatticeError


def find_blender(explicit=None):
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        raise LatticeError(f"Blender executable does not exist: {explicit}")
    candidate = shutil.which("blender")
    if candidate:
        return candidate
    root = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Blender Foundation"
    candidates = sorted(root.glob("Blender */blender.exe"), reverse=True)
    if candidates:
        return str(candidates[0])
    raise LatticeError("Blender was not found; supply --blender-path or omit --save-blend.")


def save_blend(stl_path, blend_path, executable):
    worker = Path(__file__).with_name("blender_worker.py")
    command = [executable, "--background", "--factory-startup", "--python-exit-code", "1",
               "--python", str(worker), "--", str(Path(stl_path).resolve()), str(Path(blend_path).resolve())]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LatticeError(f"Blender export failed: {exc}") from exc
    if result.returncode or not Path(blend_path).is_file():
        raise LatticeError(f"Blender export failed: {(result.stdout + result.stderr)[-3000:]}")

