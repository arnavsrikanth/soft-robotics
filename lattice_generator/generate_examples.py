"""Generate the six bundled presets; pass --overwrite to replace prior outputs."""

from pathlib import Path
import sys
from lattice_generator.cli import main

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    failures = []
    for name in ("cubic", "bcc", "octet", "diamond", "kelvin", "gyroid"):
        if main(["generate", "--config", str(root / "presets" / f"{name}.json"), *sys.argv[1:]]):
            failures.append(name)
    if failures:
        print("Failed: " + ", ".join(failures), file=sys.stderr)
        raise SystemExit(2)
