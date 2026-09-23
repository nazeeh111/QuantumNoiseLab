"""Reproducible suite execution and portable static report export."""

import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
from importlib.resources import files
import json
from pathlib import Path
import platform
import time

import numpy as np

from . import __version__
from .model import Config, simulate


def default_suite():
    common = dict(points=81, t1_us=60, tphi_us=40, shots=512, seed=2026)
    return {"experiments": [
        asdict(Config(kind="relaxation", **common)),
        asdict(Config(kind="dephasing", **common)),
        asdict(Config(kind="rabi", duration_us=20, **common)),
        asdict(Config(kind="ramsey", detuning_sigma_mhz=0.018, ensemble=21, **common)),
        asdict(Config(kind="echo", detuning_sigma_mhz=0.018, ensemble=21, **common)),
    ], "sweep": {"detuning_mhz": [-0.15, 0.15, 17], "drive_mhz": [0, 0.25, 13],
                   "duration_us": 5.0, "t1_us": 60.0, "tphi_us": 40.0}}


def _axis(spec, name):
    if not isinstance(spec, list) or len(spec) != 3:
        raise ValueError(f"{name} must be [start, end, count]")
    start, end, count = spec
    if type(count) is not int or not 2 <= count <= 101:
        raise ValueError(f"{name} count must be 2..101")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x) for x in (start, end)) or end <= start:
        raise ValueError(f"{name} needs finite increasing endpoints")
    return np.linspace(start, end, count)


def validate_suite(spec):
    if not isinstance(spec, dict) or set(spec)-{"experiments", "sweep"}:
        raise ValueError("suite accepts only experiments and optional sweep")
    experiments = spec.get("experiments")
    if not isinstance(experiments, list) or not 1 <= len(experiments) <= 30:
        raise ValueError("suite must contain 1..30 experiment configurations")
    try:
        configs = [Config(**entry) for entry in experiments]
    except TypeError as exc:
        raise ValueError(f"invalid experiment configuration: {exc}") from exc
    work = sum(c.points*(1 if c.kind in ("relaxation", "dephasing") else c.ensemble)*(4 if c.kind == "echo" else 2) for c in configs)
    if any(min(c.atol, c.rtol) < 1e-14 for c in configs):
        raise ValueError("suite solver tolerances atol and rtol must be at least 1e-14 for stable refinement")
    sweep = spec.get("sweep")
    if sweep is not None:
        if not isinstance(sweep, dict) or set(sweep)-{"detuning_mhz", "drive_mhz", "duration_us", "t1_us", "tphi_us"}:
            raise ValueError("invalid sweep fields")
        delta = _axis(sweep.get("detuning_mhz"), "detuning_mhz")
        drive = _axis(sweep.get("drive_mhz"), "drive_mhz")
        work += 2 * len(delta) * len(drive)
        for d in (delta[0], delta[-1]):
            for o in (drive[0], drive[-1]):
                Config(kind="rabi", points=2, shots=0, detuning_mhz=float(d), drive_mhz=float(o),
                       **{k: v for k, v in sweep.items() if k not in ("detuning_mhz", "drive_mhz")})
    if work > 100000:
        raise ValueError("suite exceeds the combined 100000 state-evaluation budget; split it into smaller runs")
    return configs


def run_suite(spec):
    configs = validate_suite(spec)
    started = time.perf_counter()
    experiments = []
    for config in configs:
        result = simulate(config)
        # Same samples and output times, tenfold tighter solver tolerances.
        tighter = simulate(replace(config, atol=config.atol/10, rtol=config.rtol/10, shots=0))
        result["diagnostics"]["tolerance_refinement_max_delta"] = float(np.max(abs(np.array(result["signal"])-tighter["signal"])))
        result["diagnostics"]["refinement_factor"] = 10
        experiments.append(result)
    sweep = None
    if spec.get("sweep") is not None:
        s = spec["sweep"]
        deltas = _axis(s["detuning_mhz"], "detuning_mhz")
        drives = _axis(s["drive_mhz"], "drive_mhz")
        values = []
        for drive in drives:
            row = []
            for delta in deltas:
                c = Config(kind="rabi", points=2, shots=0, drive_mhz=float(drive), detuning_mhz=float(delta),
                           **{k: v for k, v in s.items() if k not in ("detuning_mhz", "drive_mhz")})
                row.append(simulate(c)["signal"][-1])
            values.append(row)
        sweep = {"detuning_mhz": deltas.tolist(), "drive_mhz": drives.tolist(),
                 "excited_population": values, "config": s}
    canonical = json.dumps(spec, sort_keys=True, allow_nan=False, separators=(",", ":"))
    return {"schema_version": 1, "title": "QuantumNoiseLab", "simulation_only": True,
            "units": {"time": "microsecond", "frequency": "MHz (cycles/microsecond)", "signal": "dimensionless"},
            "provenance": {"created_utc": datetime.now(timezone.utc).isoformat(),
                "runtime_seconds": time.perf_counter()-started, "python": platform.python_version(),
                "platform": platform.platform(), "machine": platform.machine(), "project_version": __version__,
                "dependencies": {name: importlib.metadata.version(name) for name in ("qutip", "numpy", "scipy", "matplotlib")},
                "config_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                "solver": "QuTiP mesolve / dop853; normalize_output=False"},
            "suite_config": spec, "experiments": experiments, "sweep": sweep}


def _plot(result, target):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
    count = len(result["experiments"])
    fig, axes = plt.subplots(count, 1, figsize=(9, 3*count), squeeze=False, constrained_layout=True)
    for ax, experiment in zip(axes[:, 0], result["experiments"]):
        t = experiment["time_us"]
        ax.plot(t, experiment["signal"], color="#087f8c", lw=2, label="Lindblad solver")
        if experiment["reference"] is not None:
            ax.plot(t, experiment["reference"], "--", color="#ae6726", label="Analytic reference")
        m = experiment["measurement"]
        if m:
            ax.fill_between(t, m["low95"], m["high95"], color="#087f8c", alpha=.15, label="Synthetic shots: pointwise Wilson 95%")
            ax.scatter(t, m["value"], color="#087f8c", s=6)
        ax.set(title=experiment["config"]["kind"].capitalize(), xlabel="Delay / evolution time (µs)", ylabel=experiment["observable"])
        ax.legend(fontsize=8, loc="best")
        ax.grid(alpha=.15)
    fig.savefig(target/"experiments.png", dpi=140)
    plt.close(fig)
    if result["sweep"]:
        s = result["sweep"]
        fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
        image = ax.pcolormesh(s["detuning_mhz"], s["drive_mhz"], s["excited_population"], shading="nearest", vmin=0, vmax=1, cmap="viridis")
        fig.colorbar(image, ax=ax, label="Excited population")
        ax.set(xlabel="Detuning (MHz)", ylabel="Drive (MHz)", title=f"Driven-qubit response at {s['config'].get('duration_us', 40)} µs")
        fig.savefig(target/"sweep.png", dpi=150)
        plt.close(fig)
    else:
        (target/"sweep.png").unlink(missing_ok=True)


def export_report(result, target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, allow_nan=False)
    temporary = target/"results.json.tmp"
    temporary.write_text(text+"\n", encoding="utf-8")
    temporary.replace(target/"results.json")
    # Embedded JSON supports double-click file:// viewing without a network server.
    (target/"data.js").write_text("window.QUANTUM_NOISE_RESULTS = "+text.replace("<", "\\u003c")+";\n", encoding="utf-8")
    for name in ("index.html", "app.js", "style.css"):
        (target/name).write_text(files("quantumnoiselab").joinpath("web", name).read_text(encoding="utf-8"), encoding="utf-8")
    with (target/"experiments.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["experiment_index", "kind", "time_us", "signal", "reference", "synthetic_measurement", "wilson_low95", "wilson_high95"])
        for i, e in enumerate(result["experiments"]):
            for j, t in enumerate(e["time_us"]):
                m = e["measurement"]
                writer.writerow([i, e["config"]["kind"], t, e["signal"][j], "" if e["reference"] is None else e["reference"][j],
                                 *([m[k][j] for k in ("value", "low95", "high95")] if m else ["", "", ""])])
    if result["sweep"]:
        with (target/"sweep.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["drive_mhz", "detuning_mhz", "excited_population"])
            s = result["sweep"]
            for i, drive in enumerate(s["drive_mhz"]):
                for j, delta in enumerate(s["detuning_mhz"]):
                    writer.writerow([drive, delta, s["excited_population"][i][j]])
    else:
        (target/"sweep.csv").unlink(missing_ok=True)
    _plot(result, target)
