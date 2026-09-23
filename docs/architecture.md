# Architecture and reproducibility

`model.py` owns parameter validation, the physical model, density-matrix evolution, closed-form references, measurement simulation, and diagnostics. It returns plain JSON-compatible data. It has no file or network I/O.

`report.py` validates a suite, runs experiments and a drive–detuning sweep, repeats time traces at tighter solver tolerances, and records provenance. It exports JSON, CSV, Matplotlib plots, and a self-contained browser application. `results.json` is written through a temporary file; the report directory as a whole is not a transactional database. Use a new output directory per run if an interrupted export must not replace an earlier result.

`cli.py` is a small input/output boundary. It accepts a JSON configuration and rejects nonempty output directories unless `--force` is provided. It does not expose a server, obtain credentials, or access quantum hardware. Network access is needed only to install dependencies.

`web/` renders computed arrays with native SVG and DOM APIs. It performs no scientific simulation or remote request. Embedded `data.js` makes direct `file://` opening work; `results.json` remains the machine-readable source. Uploaded JSON is size-checked and structurally checked before rendering. Text is inserted as text rather than interpreted as HTML. Local report artifacts contain no account data or secrets.

Provenance records creation time in UTC, Python and dependency versions, OS/architecture, solver, seeds, configuration, elapsed solver-suite runtime, and a SHA-256 digest of canonical input JSON. Runtime excludes plot/export time. The report does not claim bitwise numerical reproducibility across library versions or architectures.

The displayed scientific story is narrow and testable: how Markovian relaxation, dephasing, and quasistatic frequency spread alter a two-level system, and what ideal echo can recover. The implementation does not hide missing hardware work behind a decorative simulation.
