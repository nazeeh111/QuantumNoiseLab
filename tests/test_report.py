import csv
import json

import pytest

from quantumnoiselab.cli import main
from quantumnoiselab.report import export_report, run_suite, validate_suite


def test_report_roundtrip_and_real_exports(tmp_path):
    spec = {"experiments": [{"kind": "ramsey", "points": 7, "ensemble": 3,
                             "detuning_sigma_mhz": 0.02}],
            "sweep": {"detuning_mhz": [-0.1, 0.1, 3], "drive_mhz": [0, 0.1, 3], "duration_us": 2}}
    result = run_suite(spec)
    export_report(result, tmp_path)
    restored = json.loads((tmp_path/"results.json").read_text())
    assert restored == result
    assert len(result["provenance"]["config_sha256"]) == 64
    assert result["experiments"][0]["diagnostics"]["tolerance_refinement_max_delta"] < 1e-6
    rows = list(csv.DictReader((tmp_path/"experiments.csv").open()))
    assert len(rows) == 7
    assert float(rows[2]["signal"]) == result["experiments"][0]["signal"][2]
    assert (tmp_path/"experiments.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path/"sweep.png").read_bytes().startswith(b"\x89PNG")
    assert "window.QUANTUM_NOISE_RESULTS" in (tmp_path/"data.js").read_text()
    assert len(list(csv.DictReader((tmp_path/"sweep.csv").open()))) == 9


def test_cli_protects_existing_files(tmp_path):
    (tmp_path/"keep.txt").write_text("user data")
    assert main(["run", "--output", str(tmp_path)]) == 2
    assert (tmp_path/"keep.txt").read_text() == "user data"


def test_cli_reports_integrator_failure_without_traceback(tmp_path, monkeypatch, capsys):
    from qutip.solver.integrator import IntegratorException
    from quantumnoiselab import cli
    def fail(_):
        raise IntegratorException("integration did not converge")
    monkeypatch.setattr(cli, "run_suite", fail)
    assert main(["run", "--output", str(tmp_path)]) == 2
    assert "did not converge" in capsys.readouterr().err


@pytest.mark.parametrize("spec", [{}, {"experiments": []}, {"experiments": [{"kind": "rabi", "typo": 4}]},
    {"experiments": [{}], "sweep": {"drive_mhz": [0, 1, 0], "detuning_mhz": [0, 1, 3]}},
    {"experiments": [{}], "sweep": {"drive_mhz": [-1, 1, 3], "detuning_mhz": [0, 1, 3]}},
    {"experiments": [{}], "sweep": {"drive_mhz": [0, 1, 3], "detuning_mhz": [1, 0, 3]}}])
def test_invalid_suite(spec):
    with pytest.raises(ValueError):
        validate_suite(spec)


def test_combined_budget_includes_sweep():
    spec = {"experiments": [{"kind": "ramsey", "points": 10000, "ensemble": 5}],
            "sweep": {"detuning_mhz": [-0.1, 0.1, 101], "drive_mhz": [0, 0.1, 101]}}
    with pytest.raises(ValueError, match="budget"):
        validate_suite(spec)


def test_tolerance_rejected_before_refinement_underflow():
    with pytest.raises(ValueError, match="tolerance|atol|rtol"):
        validate_suite({"experiments": [{"points": 2, "atol": 5e-324, "rtol": 5e-324}]})
