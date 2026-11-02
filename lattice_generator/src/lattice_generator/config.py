"""Configuration and preflight checks, without allocating a volume."""

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

PATTERNS = ("cubic", "bcc", "octet", "diamond", "kelvin", "gyroid")


class LatticeError(ValueError):
    """An actionable configuration or geometry error."""


@dataclass(frozen=True)
class Settings:
    pattern: str
    size: tuple[float, float, float]
    cell_size: float
    strut_diameter: float | None = None
    wall_thickness: float | None = None
    base_thickness: float = 0.0
    resolution: float | None = None
    memory_limit_mib: float = 2048.0
    pockets: str = "none"
    magnet_diameter: float = 10.0
    magnet_thickness: float = 2.7
    pocket_diameter_clearance: float = 0.3
    pocket_height_clearance: float = 0.2
    pocket_wall_thickness: float = 1.0
    pocket_floor_thickness: float = 1.0
    pocket_roof_thickness: float = 1.0
    mesh_above_pockets: float | None = None
    pocket_midplane_height: float | None = None
    require_exact_bounds: bool = False
    simplify_tolerance: float = 0.05
    lattice_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def feature_thickness(self):
        return self.wall_thickness if self.pattern == "gyroid" else self.strut_diameter

    @property
    def grid_spacing(self):
        thickness = self.feature_thickness
        if self.base_thickness:
            thickness = min(thickness, self.base_thickness)
        if self.pockets == "four":
            thickness = min(thickness, self.pocket_wall_thickness, self.pocket_floor_thickness,
                            self.pocket_roof_thickness, self.magnet_thickness + self.pocket_height_clearance,
                            self.magnet_diameter + self.pocket_diameter_clearance)
        return self.resolution or min(0.2, thickness / 6, self.cell_size / 24)

    def check(self):
        offset = self.lattice_offset
        if (not isinstance(offset, (list, tuple)) or len(offset) != 3 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                    not math.isfinite(v) for v in offset)):
            raise LatticeError("lattice-offset must contain three finite numeric values in millimeters.")
        if self.pattern == "gyroid" and any(offset):
            raise LatticeError("Nonzero lattice-offset is supported only for strut patterns, not gyroid.")
        value = self.simplify_tolerance
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value < 0:
            raise LatticeError("simplify-tolerance must be finite and nonnegative; zero disables it.")
        if self.pocket_midplane_height is not None:
            if self.mesh_above_pockets is not None:
                raise LatticeError("Specify only one pocket positioning option.")
            value = self.pocket_midplane_height
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise LatticeError("pocket-midplane-height must be finite and positive.")
        if not isinstance(self.require_exact_bounds, bool):
            raise LatticeError("require-exact-bounds must be boolean.")
        value = self.mesh_above_pockets if self.mesh_above_pockets is not None else 2.0
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise LatticeError("mesh-above-pockets must be a finite nonnegative number.")
        if self.pockets not in ("none", "four"):
            raise LatticeError("pockets must be 'none' or 'four'.")
        for name in ("magnet_diameter", "magnet_thickness", "pocket_wall_thickness",
                     "pocket_floor_thickness", "pocket_roof_thickness", "pocket_diameter_clearance", "pocket_height_clearance"):
            value = getattr(self, name)
            minimum_ok = value >= 0 if isinstance(value, (int, float)) and "clearance" in name else isinstance(value, (int, float)) and value > 0
            if isinstance(value, bool) or not minimum_ok or not math.isfinite(value):
                raise LatticeError(f"{name.replace('_', '-')} must be finite and {'nonnegative' if 'clearance' in name else 'positive'}.")
        if self.pattern not in PATTERNS:
            raise LatticeError(f"Unknown pattern {self.pattern!r}; choose {', '.join(PATTERNS)}.")
        if len(self.size) != 3:
            raise LatticeError("size must contain width, depth, and height.")
        values = {"cell-size": self.cell_size, "memory-limit-mib": self.memory_limit_mib,
                  **dict(zip(("width", "depth", "height"), self.size))}
        for name in ("strut_diameter", "wall_thickness", "resolution"):
            if getattr(self, name) is not None:
                values[name.replace("_", "-")] = getattr(self, name)
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise LatticeError(f"{name} must be a finite positive number.")
        if not isinstance(self.base_thickness, (int, float)) or isinstance(self.base_thickness, bool) or not math.isfinite(self.base_thickness) or not 0 <= self.base_thickness < self.size[2]:
            raise LatticeError("base-thickness must be finite, nonnegative, and less than total height.")
        if self.pattern == "gyroid":
            if self.wall_thickness is None or self.strut_diameter is not None:
                raise LatticeError("Gyroid requires wall-thickness and does not accept strut-diameter.")
        elif self.strut_diameter is None or self.wall_thickness is not None:
            raise LatticeError("Strut patterns require strut-diameter and do not accept wall-thickness.")
        thickness = min(self.feature_thickness, self.base_thickness or self.feature_thickness)
        if self.grid_spacing > thickness / 4 + 1e-12:
            raise LatticeError("Unresolved thin feature: resolution must be at most the smallest thickness / 4.")
        if self.grid_spacing > self.cell_size / 16 + 1e-12:
            raise LatticeError("Unresolved cells: resolution must be at most cell-size / 16.")
        if self.feature_thickness >= self.cell_size:
            raise LatticeError("Feature thickness must be smaller than cell-size to preserve a lattice.")
        if self.pockets == "four":
            from .pockets import check_layout
            check_layout(self)
        self.preflight()
        return self

    def preflight(self):
        h = self.grid_spacing
        if not math.isfinite(h) or h <= 0 or any(s / h > 2**31 for s in self.size):
            raise LatticeError("Requested grid is too large; increase feature size or resolution.")
        intervals = tuple(math.ceil(s / h) for s in self.size)
        spacing = tuple(s / n for s, n in zip(self.size, intervals))
        shape = tuple(n + 2 for n in intervals)
        # EDT needs a full repeat of halo to avoid using the edge as an implicit surface.
        halo = tuple(math.ceil(self.cell_size / d) for d in spacing) if self.pattern == "gyroid" else (0, 0, 0)
        work_shape = tuple(n + 2 * p for n, p in zip(shape, halo))
        samples = math.prod(shape)
        work_samples = math.prod(work_shape)
        # Conservative allocation allowance includes marching cubes and mesh validation.
        estimated = max(work_samples * 32 + samples * 16, samples * 96) + 64 * 1024**2
        if self.pockets == "four":
            estimated += samples * 16  # connected-material and enclosed-void labels
        estimated_edges = 0
        if self.pattern != "gyroid":
            motifs = {"cubic": 3, "bcc": 8, "octet": 48, "diamond": 16, "kelvin": 72}
            repeats = math.prod(math.ceil(s / self.cell_size) + 5 for s in self.size)
            estimated_edges = repeats * motifs[self.pattern]
            estimated += estimated_edges * 400
        if estimated > self.memory_limit_mib * 1024**2:
            raise LatticeError(
                f"Estimated working memory {estimated / 1024**2:.0f} MiB exceeds "
                f"{self.memory_limit_mib:g} MiB. Reduce box dimensions, increase feature thickness "
                "and grid spacing, or explicitly raise --memory-limit-mib. Accuracy was not changed."
            )
        return {"grid_shape": shape, "spacing_mm": spacing, "gyroid_halo": halo,
                "estimated_memory_mib": estimated / 1024**2,
                "estimated_edges_upper_bound": estimated_edges}

    def as_dict(self):
        return {k.replace("_", "-"): v for k, v in asdict(self).items()}


def read_preset(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LatticeError(f"Cannot read preset {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LatticeError("Preset must be a JSON object.")
    allowed = {k.replace("_", "-") for k in Settings.__dataclass_fields__} | {"output", "save-blend", "blender-path", "overwrite"}
    unknown = set(data) - allowed
    if unknown:
        raise LatticeError(f"Unknown preset settings: {', '.join(sorted(unknown))}. Use hyphenated option names.")
    if "overwrite" in data and not isinstance(data["overwrite"], bool):
        raise LatticeError("overwrite must be true or false.")
    for key in ("output", "save-blend", "blender-path"):
        if key in data and not isinstance(data[key], str):
            raise LatticeError(f"{key} must be a path string.")
    # Preset paths are relative to the preset, not whichever directory invokes the CLI.
    for key in ("output", "save-blend", "blender-path"):
        if data.get(key):
            candidate = Path(data[key]).expanduser()
            data[key] = str(candidate if candidate.is_absolute() else Path(path).resolve().parent / candidate)
    return {k.replace("-", "_"): v for k, v in data.items()}
