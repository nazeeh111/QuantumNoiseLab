"""Lindblad dynamics with explicit basis, units, and independent analytic limits."""

from dataclasses import asdict, dataclass
import math

import numpy as np
import qutip as qt

KINDS = ("relaxation", "dephasing", "rabi", "ramsey", "echo")


@dataclass(frozen=True)
class Config:
    kind: str = "ramsey"
    duration_us: float = 40.0
    points: int = 81
    t1_us: float | None = 60.0
    tphi_us: float | None = 40.0
    drive_mhz: float = 0.10
    detuning_mhz: float = 0.025
    detuning_sigma_mhz: float = 0.0
    ensemble: int = 1
    shots: int = 512
    seed: int = 2026
    atol: float = 1e-9
    rtol: float = 1e-8

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        for name in ("duration_us", "atol", "rtol"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("t1_us", "tphi_us"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be positive or null (disabled)")
        for name in ("drive_mhz", "detuning_mhz", "detuning_sigma_mhz"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.detuning_sigma_mhz < 0 or self.drive_mhz < 0:
            raise ValueError("drive and detuning spread must be nonnegative")
        for name, lower, upper in (("points", 2, 10001), ("ensemble", 1, 1001),
                                    ("shots", 0, 10000000), ("seed", 0, 2**32-1)):
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"{name} must be an integer in [{lower}, {upper}]")
        effective_ensemble = 1 if self.kind in ("relaxation", "dephasing") else self.ensemble
        budget = 10000 if self.kind == "echo" else 100000
        if self.points*effective_ensemble > budget:
            raise ValueError(f"points × effective ensemble exceeds the {budget} sample budget; reduce points or ensemble")
        rates = [1/t for t in (self.t1_us, self.tphi_us) if t is not None]
        if any(not math.isfinite(rate*self.duration_us) or rate*self.duration_us > 20000 for rate in rates):
            raise ValueError("duration/decay-time ratio exceeds 20000; use a shorter time window")
        cycles = self.duration_us*(abs(self.detuning_mhz)+self.drive_mhz+8*self.detuning_sigma_mhz)
        if not math.isfinite(cycles) or cycles > 20000:
            raise ValueError("frequency × duration exceeds the supported integration budget; use a shorter window")

    @property
    def gamma2(self):
        return (0 if self.t1_us is None else 1 / (2*self.t1_us)) + (0 if self.tphi_us is None else 1/self.tphi_us)


def _collapse(c):
    # |0> is ground, |1> is excited. Avoid spin-lowering basis ambiguity.
    ops = []
    if c.t1_us is not None:
        ops.append((qt.basis(2, 0) * qt.basis(2, 1).dag()) / np.sqrt(c.t1_us))
    if c.tphi_us is not None:
        ops.append(qt.sigmaz() / np.sqrt(2*c.tphi_us))
    return ops


def _evolve(c, rho, times, detuning=0.0, drive=0.0):
    h = np.pi * (detuning * qt.sigmaz() + drive * qt.sigmax())
    if len(times) == 1 or times[-1] == 0:
        return [rho] * len(times)
    return qt.mesolve(h, rho, times, c_ops=_collapse(c), options={
        "method": "dop853", "atol": c.atol, "rtol": c.rtol,
        "normalize_output": False, "store_states": True, "nsteps": 100000,
    }).states


def _wilson(count, n):
    p = count/n
    z = 1.959963984540054
    denominator = 1+z*z/n
    center = (p+z*z/(2*n))/denominator
    half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return np.maximum(0, center-half), np.minimum(1, center+half)


def simulate(c: Config):
    """Return JSON-serializable physical observables, references and diagnostics.

    Ramsey/echo measure X after ideal preparation/readout pulses. Echo inserts an
    instantaneous pi-X rotation halfway through each separately run delay.
    Quasistatic detuning is constant within a trajectory and sampled between runs.
    """
    times = np.linspace(0, c.duration_us, c.points)
    det_rng, shot_rng = [np.random.default_rng(s) for s in np.random.SeedSequence(c.seed).spawn(2)]
    offsets = (det_rng.normal(c.detuning_mhz, c.detuning_sigma_mhz, c.ensemble)
               if c.detuning_sigma_mhz else np.full(c.ensemble, c.detuning_mhz))
    if c.kind in ("relaxation", "dephasing"):
        offsets = np.array([0.0])
    ground, excited = qt.basis(2, 0), qt.basis(2, 1)
    initial = excited.proj() if c.kind == "relaxation" else ground.proj() if c.kind == "rabi" else ((ground+excited).unit()).proj()
    trajectories = []
    checked_states = []
    for delta in offsets:
        if c.kind == "echo":
            states = []
            for t in times:
                first = _evolve(c, initial, [0, t/2], delta)[-1]
                rotated = qt.sigmax()*first*qt.sigmax()
                last = _evolve(c, rotated, [0, t/2], delta)[-1]
                states.append(last)
                checked_states.extend([first, rotated])
        else:
            states = _evolve(c, initial, times, delta, c.drive_mhz if c.kind == "rabi" else 0)
        checked_states.extend(states)
        trajectories.append(np.array([s.full() for s in states]))
    rho = np.mean(trajectories, axis=0)
    operators = {"x": qt.sigmax().full(), "y": qt.sigmay().full(), "z": qt.sigmaz().full()}
    bloch = {k: np.einsum("tij,ji->t", rho, op).real.tolist() for k, op in operators.items()}
    population = rho[:, 1, 1].real
    population_measurement = c.kind in ("relaxation", "rabi")
    signal = population if population_measurement else np.array(bloch["x"])
    if c.kind == "relaxation":
        ref = np.exp(-times/c.t1_us) if c.t1_us else np.ones_like(times)
        reference_label = "exp(-t/T1)"
    elif c.kind == "dephasing" or c.kind == "echo":
        ref = np.exp(-times*c.gamma2)
        reference_label = "exp(-t/T2); ideal echo cancels quasistatic detuning"
    elif c.kind == "ramsey":
        ref = np.exp(-times*c.gamma2) * np.cos(2*np.pi*offsets[:, None]*times).mean(axis=0)
        reference_label = "exp(-t/T2) × sampled ensemble mean cos(2πΔt)"
    elif c.t1_us is None and c.tphi_us is None:
        omega = np.sqrt(c.drive_mhz**2+offsets**2)
        ratio = np.divide(c.drive_mhz**2, omega**2, out=np.zeros_like(omega), where=omega!=0)
        ref = (ratio[:, None]*np.sin(np.pi*omega[:, None]*times)**2).mean(axis=0)
        reference_label = "Ω²/(Ω²+Δ²) × sin²(π√(Ω²+Δ²)t), ensemble averaged"
    else:
        ref = None
        reference_label = "No analytic reference supplied for this dissipative driven case"
    matrices = np.array([s.full() for s in checked_states] + list(rho))
    hermitian = (matrices+matrices.conj().transpose(0, 2, 1))/2
    diagnostics = {
        "max_trace_error": float(np.max(abs(np.trace(matrices, axis1=1, axis2=2)-1))),
        "max_hermiticity_error": float(np.max(abs(matrices-matrices.conj().transpose(0, 2, 1)))),
        "min_eigenvalue": float(np.linalg.eigvalsh(hermitian).min()),
        "max_reference_error": None if ref is None else float(np.max(abs(signal-ref))),
    }
    if diagnostics["max_trace_error"] > 1e-6 or diagnostics["max_hermiticity_error"] > 1e-6 or diagnostics["min_eigenvalue"] < -1e-6:
        raise ArithmeticError("State diagnostics exceed physical tolerance; tighten solver tolerances or shorten the time window")
    probabilities = signal if population_measurement else (signal+1)/2
    if probabilities.min() < -1e-6 or probabilities.max() > 1+1e-6:
        raise ArithmeticError("Solver returned a nonphysical measurement probability")
    measurement = None
    if c.shots:
        counts = shot_rng.binomial(c.shots, np.clip(probabilities, 0, 1))
        low, high = _wilson(counts, c.shots)
        scale, shift = (1, 0) if population_measurement else (2, -1)
        measurement = {"counts_plus": counts.tolist(), "shots_per_point": c.shots,
                       "value": (scale*counts/c.shots+shift).tolist(),
                       "low95": (scale*low+shift).tolist(), "high95": (scale*high+shift).tolist(),
                       "interval": "pointwise Wilson 95%; shot uncertainty only"}
    return {"config": asdict(c), "time_us": times.tolist(), "signal": signal.tolist(),
            "observable": "Excited population" if population_measurement else "X expectation",
            "bloch": bloch, "excited_population": population.tolist(),
            "reference": None if ref is None else ref.tolist(), "reference_label": reference_label,
            "detuning_samples_mhz": offsets.tolist(), "measurement": measurement,
            "diagnostics": diagnostics, "t2_us": None if not c.gamma2 else 1/c.gamma2}
