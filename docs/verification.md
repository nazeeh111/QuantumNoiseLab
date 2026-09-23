# Local verification record

Verified September 23, 2026 on macOS arm64 with Python 3.13. Environment versions: QuTiP 5.3.1, NumPy 2.5.3, SciPy 1.18.1, Matplotlib 3.11.2. Full dependency snapshot is in `requirements-tested.txt`.

| Check | Observed result |
|---|---|
| Scientific, input-validation, export, CLI tests | **34 passed**, parent verification run 9.49 seconds including imports |
| Complete default suite | Five experiments, 81 time samples each; Ramsey/echo use 21 detuning trajectories |
| Drive–detuning parameter sweep | 17 × 13 = 221 independently solved cells |
| Default suite compute time | 2.37 seconds, excludes plotting/export and initial library import |
| Maximum analytical-reference error | 1.913 × 10⁻⁹, in echo; dissipative Rabi has no supplied analytical reference |
| Maximum change with tenfold tighter tolerances | 1.717 × 10⁻⁹ |
| Maximum density-matrix trace error | 1.333 × 10⁻¹⁵ |
| Maximum Hermiticity error | 0 in the recorded default suite |
| Minimum eigenvalue | 0 in the recorded default suite |
| Distribution build | Wheel and source archive built successfully |
| Installed wheel smoke test | Five quick experiments and report generated from `/tmp`, outside the source checkout |
| Dependency integrity | `pip check`: no broken requirements |
| Browser JavaScript syntax | `node --check`: passed |
| Real Chrome interaction smoke test | Experiment switching, overlays, Bloch selection, sample inspection, invalid/valid JSON import, imported-run JSON download, and no browser exceptions: passed |
| Responsive check | 1440 × 1100 desktop and 390 × 844 mobile screenshots inspected; mobile page width fits viewport |

The exact default numerical data and runtime provenance are checked into `docs/demo/results.json`. The five-experiment report can be opened offline at `docs/demo/index.html`. Synthetic shot intervals do not quantify model error or finite detuning-ensemble uncertainty.

The optional `tests/browser-smoke.mjs` uses Node's built-in WebSocket client to drive a separately launched, isolated Chrome instance through its local debugging port. It takes `PORT /absolute/report/index.html [screenshot-directory]`. It is not required to use the project. Python CI is configured for Linux 3.11/3.12/3.13; those remote runs were not yet executed when this local record was written. Windows and physical quantum hardware were not tested.

One local environment issue was observed: macOS FileProvider applied a hidden flag to editable-install `.pth` files, causing Python to skip them. A normal wheel installation ran correctly. The documented installation uses a normal install, not an editable one. Initial imports may also build a Matplotlib font cache; this setup cost is excluded from the solver runtime.

These checks validate the stated examples and invariants. They do not establish accuracy for every allowed configuration, certify a new quantum algorithm, or demonstrate hardware performance.

Independent review identified two validation defects before publication: parameter-sweep work was omitted from the combined work budget, and subnormal tolerances could underflow during refinement. Both were reproduced with failing tests, fixed, and included in the 34-test run.
