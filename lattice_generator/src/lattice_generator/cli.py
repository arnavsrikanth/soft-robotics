"""Command-line entry points and JSON preset merging."""

import argparse
import json
from pathlib import Path
import sys

from .config import LatticeError, Settings, read_preset


def parser():
    root = argparse.ArgumentParser(description="Generate connected, closed lattice solids in millimeters.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("list-patterns", help="Describe available lattice patterns")
    generate = commands.add_parser("generate", help="Generate and validate an STL")
    generate.add_argument("--config", type=Path, help="JSON preset; command-line values take priority")
    generate.add_argument("--pattern")
    generate.add_argument("--size", type=float, nargs=3, metavar=("WIDTH", "DEPTH", "HEIGHT"))
    for flag in ("cell-size", "strut-diameter", "wall-thickness", "base-thickness", "resolution", "memory-limit-mib"):
        generate.add_argument("--" + flag, type=float)
    generate.add_argument("--output")
    generate.add_argument("--save-blend", help="Optional .blend output filename")
    generate.add_argument("--blender-path", help="Override Blender executable discovery")
    generate.add_argument("--overwrite", action="store_true", default=None)
    validate = commands.add_parser("validate", help="Check an existing mesh without modifying it")
    validate.add_argument("input", type=Path)
    return root


def resolve(args):
    values = read_preset(args.config) if args.config else {}
    values.update({k: v for k, v in vars(args).items() if k not in ("command", "config") and v is not None})
    for required in ("pattern", "size", "cell_size", "output"):
        if required not in values:
            raise LatticeError(f"Missing --{required.replace('_', '-')} (or its preset value).")
    if not isinstance(values["size"], (list, tuple)):
        raise LatticeError("size must be a list of three numbers.")
    values["size"] = tuple(values["size"])
    settings = Settings(**{k: v for k, v in values.items() if k in Settings.__dataclass_fields__}).check()
    return settings, {k: v for k, v in values.items() if k not in Settings.__dataclass_fields__}


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "list-patterns":
            from .patterns import DESCRIPTIONS
            for name, description in DESCRIPTIONS.items():
                print(f"{name:8} {description}")
        elif args.command == "validate":
            from .validation import load_mesh, validate_mesh
            result = validate_mesh(load_mesh(args.input))
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0 if result["valid"] else 2
        else:
            from .export import generate
            settings, options = resolve(args)
            generate(settings, options["output"], save_blend_path=options.get("save_blend"),
                     blender_path=options.get("blender_path"), overwrite=options.get("overwrite", False))
        return 0
    except (LatticeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except MemoryError:
        print("Error: Not enough memory. Reduce dimensions or increase grid spacing; accuracy was not changed.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
