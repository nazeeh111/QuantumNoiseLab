"""Small offline command-line interface."""

import argparse
import json
from pathlib import Path
import sys

from qutip.solver.integrator import IntegratorException

from .report import default_suite, export_report, run_suite, validate_suite


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run reproducible quantum-noise simulations locally.")
    sub = parser.add_subparsers(dest="command", required=True)
    config_parser = sub.add_parser("config", help="Print the default JSON configuration")
    run = sub.add_parser("run", help="Compute a suite and export an offline dashboard, plots and data")
    run.add_argument("--config", type=Path, help="JSON suite configuration; defaults to the five-experiment suite")
    run.add_argument("--output", type=Path, default=Path("results"))
    run.add_argument("--force", action="store_true", help="Allow overwriting report files in an existing directory")
    args = parser.parse_args(argv)
    if args.command == "config":
        print(json.dumps(default_suite(), indent=2))
        return 0
    try:
        spec = json.loads(args.config.read_text(encoding="utf-8")) if args.config else default_suite()
        validate_suite(spec)
        if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())) and not args.force:
            raise ValueError("output is not empty; choose a new directory or pass --force")
        result = run_suite(spec)
        export_report(result, args.output)
    except (ValueError, OSError, ArithmeticError, RuntimeError, IntegratorException) as exc:
        print(f"quantum-noise-lab: {exc}", file=sys.stderr)
        return 2
    print(f"Computed {len(result['experiments'])} experiments in {result['provenance']['runtime_seconds']:.2f}s")
    print(f"Open {args.output.resolve() / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
