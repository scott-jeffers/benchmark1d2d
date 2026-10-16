# Friction loss in a pipe: what to build

Steady flow through one pipe from a reservoir. The friction loss over the pipe is known exactly from the Colebrook–White law: 3.09 m.

## Build
- A reservoir with a head of 100 m, feeding a horizontal pipe 1,000 m long, 300 mm in diameter, with a wall roughness of 0.15 mm.
- Darcy–Weisbach friction (Colebrook–White). Water kinematic viscosity 1.0 × 10⁻⁶ m²/s.
- At the far end, draw off 0.0706858 m³/s (70.69 L/s, a velocity of 1 m/s).
- `model/A1P-001.inp` is this pipe as an EPANET file (split into 10 equal pipes so heads are reported along it).

## Run
A single steady solution.
