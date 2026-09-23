import numpy as np
import pytest

from quantumnoiselab.model import Config, simulate


@pytest.mark.parametrize("kind", ["relaxation", "dephasing", "ramsey", "rabi", "echo"])
def test_analytic_limits_and_density_invariants(kind):
    c = Config(kind=kind, points=31, duration_us=20, t1_us=35,
               tphi_us=22, drive_mhz=0.1, detuning_mhz=0.07,
               ensemble=3, detuning_sigma_mhz=0.02)
    if kind == "rabi":
        c = Config(kind=kind, points=61, duration_us=10, t1_us=None,
                   tphi_us=None, drive_mhz=0.13, detuning_mhz=0.04)
    r = simulate(c)
    assert max(abs(np.array(r["signal"]) - r["reference"])) < 2e-6
    assert r["diagnostics"]["max_trace_error"] < 1e-7
    assert r["diagnostics"]["max_hermiticity_error"] < 1e-10
    assert r["diagnostics"]["min_eigenvalue"] > -1e-7


def test_echo_refocuses_static_detuning_but_not_markovian_dephasing():
    common = dict(points=21, duration_us=25, t1_us=None, tphi_us=40,
                  ensemble=11, detuning_sigma_mhz=0.05, seed=19)
    ramsey = simulate(Config(kind="ramsey", **common))
    echo = simulate(Config(kind="echo", **common))
    assert abs(ramsey["signal"][-1]) < echo["signal"][-1] - 0.2
    assert echo["signal"][-1] == pytest.approx(np.exp(-25/40), abs=2e-7)


def test_noise_reproducibility_and_confidence_bounds():
    c = Config(kind="ramsey", points=11, shots=200, ensemble=7,
               detuning_sigma_mhz=0.02, seed=313)
    a, b = simulate(c), simulate(c)
    assert a["measurement"] == b["measurement"]
    assert a["detuning_samples_mhz"] == b["detuning_samples_mhz"]
    for lo, value, hi in zip(a["measurement"]["low95"], a["measurement"]["value"], a["measurement"]["high95"]):
        assert -1 <= lo <= value <= hi <= 1


def test_solver_tolerance_convergence():
    common = dict(kind="rabi", points=101, duration_us=40, drive_mhz=0.3,
                  detuning_mhz=0.12, t1_us=40, tphi_us=25)
    ordinary = simulate(Config(**common, atol=1e-8, rtol=1e-7))
    tight = simulate(Config(**common, atol=1e-11, rtol=1e-10))
    assert max(abs(np.array(ordinary["signal"]) - tight["signal"])) < 2e-5


@pytest.mark.parametrize("kwargs", [{"t1_us": 0}, {"tphi_us": -1}, {"points": 1},
    {"duration_us": float("nan")}, {"drive_mhz": float("inf")}, {"ensemble": 0},
    {"shots": -1}, {"points": 1.2}, {"seed": -1}, {"kind": "invalid"},
    {"detuning_sigma_mhz": -1}, {"rtol": 0},
    {"kind": "echo", "points": 10001, "ensemble": 1001},
    {"t1_us": 1e-310}, {"duration_us": 1e308}])
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)
