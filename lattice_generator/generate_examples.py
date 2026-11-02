"""Generate reference-sized pocketed samples sequentially."""
import argparse
from pathlib import Path
from lattice_generator.cli import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plates", choices=("plate", "no-plate", "both"), default="both")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    failures = []
    for preset in sorted((Path(__file__).resolve().parent / "presets/reference_size").glob("*.json")):
        no_plate = preset.stem.endswith("no_plate")
        if args.plates != "both" and no_plate != (args.plates == "no-plate"):
            continue
        print(f"Generating {preset.stem}", flush=True)
        if main(["generate", "--config", str(preset), *(["--overwrite"] if args.overwrite else [])]):
            failures.append(preset.stem)
    if failures:
        print("Failed: " + ", ".join(failures), flush=True)
        raise SystemExit(2)
