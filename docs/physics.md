# Physical model and analytical checks

The basis is explicit: ground `|0> = (1,0)` and excited `|1> = (0,1)`. Pauli Z is `diag(1,-1)`. Time is measured in microseconds and frequencies in MHz (cycles per microsecond). We set ℏ = 1 in the rotating-frame equations.

The Hamiltonian is `H = π (Δ σz + Ω σx)`. The `2π` conversion from cycles to radians is therefore included before dividing by two. Free-evolution experiments set Ω to zero. Relaxation/coherence experiments also set Δ to zero.

The Lindblad equation is `dρ/dt = -i[H,ρ] + Σ (LρL† - {L†L,ρ}/2)`. Collapse operators are `L1 = |0><1| / sqrt(T1)` and `Lφ = σz / sqrt(2 Tφ)`. A null time disables that operator. This gives `γ2 = 1/(2 T1) + 1/Tφ`; missing channels contribute zero. The pure-dephasing factor of two is important: a diagonal Pauli-Z collapse operator acts on an off-diagonal density entry with twice its squared coefficient.

For relaxation, `ρ11(t) = exp(-t/T1)` from initial excitation. For an X superposition with no drive, `x(t) = exp(-γ2 t) cos(2π Δ t)`. Zero detuning gives the T2 reference. For noiseless Rabi evolution starting in ground, `Pe(t) = Ω²/(Ω²+Δ²) sin²(π sqrt(Ω²+Δ²) t)`, with zero population when both frequencies vanish. References are calculated independently from closed-form scalar expressions, not by calling the solver again.

Ramsey samples a Gaussian distribution of detunings between trajectories, holding each sampled value fixed during evolution. Its reference averages the cosine over the **same finite detuning sample**, multiplied by `exp(-γ2 t)`. This tests the time integration independently; it does not test whether the finite sample accurately approximates an infinite Gaussian ensemble. Change ensemble size and seed to assess that separate approximation. The Gaussian infinite-ensemble envelope would additionally contain `exp(-2π² σ² t²)`.

For Hahn echo, every plotted delay is a separate experiment: evolve for t/2, apply an instantaneous π-X rotation, and evolve for t/2 again. This negates accumulated phase from constant detuning while X coherence still decays at γ2. The expected X signal is `exp(-γ2 t)`. The plotted echo Bloch points are final states from these separate pulse sequences, not the intermediate history of one pulse sequence. Echo does not remove irreversible Lindblad noise in this model.

Synthetic shots sample the appropriate Bernoulli probability: `Pe` for relaxation/Rabi and `(1+x)/2` for X readout. Independent child random streams separate detuning draws from shot sampling. Wilson 95% pointwise intervals are transformed back into X units when needed. These intervals are neither simultaneous confidence bands nor model-parameter or ensemble-error bounds.

The integrator is QuTiP `mesolve` with `dop853`, explicit tolerances, and `normalize_output=False`. Disabling output normalization prevents silent renormalization from hiding trace drift. Diagnostics inspect all computed trajectory states, intermediate echo states, and ensemble-averaged states for trace error, Hermiticity error, and minimum eigenvalue. Positivity is evaluated on the Hermitian part and is reported alongside the Hermiticity error. Minor negative eigenvalues within numerical tolerance can occur. Physical probabilities beyond 1e-6 of [0,1] abort sampling; only rounding-level excursions are clipped.

Each report reruns every time trace with tenfold tighter tolerances and the same detuning samples. The maximum signal difference is reported. This checks solver sensitivity for the chosen run, not all possible parameters or sampling error. The sweep uses the regular tolerances and records its full input configuration. Tests separately exercise stiff-looking fast-drive and dissipative cases, but do not establish numerical convergence for arbitrary user configurations.

Suite validation includes the sweep in its combined 100,000 state-evaluation budget and requires input tolerances of at least 1e-14 before the tenfold refinement run. These bounds prevent an accepted configuration from overflowing the work budget or underflowing during refinement; they do not establish convergence for every configuration.
