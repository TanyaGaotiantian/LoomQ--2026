"""Noiseless state-vector simulator for the official 12-gate whitelist.

Pure Python + stdlib, no third-party dependencies.  This is the reference
execution engine used by ``run()`` on all three backends whenever the vendor
SDK is not installed in the evaluation container, so results are reproducible
anywhere.  When a vendor SDK *is* importable, ``backends/runner.py`` prefers
the genuine SDK and only falls back here.

Bit-order contract (LoomQ rules): counts keys are binary strings whose
right-most character is ``c[0]`` (Qiskit convention).  Our state vector is
indexed with qubit 0 as the least-significant bit, so ``bin(i)[2:].zfill(n)``
is exactly the required key.
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Dict, List, Tuple

from qasm.parser import Circuit, GateOp, MeasureOp, WHITELIST

# ---------------------------------------------------------------------------
# Gate matrices
# ---------------------------------------------------------------------------

SQRT2 = math.sqrt(2.0)
_I = complex(0, 1)


def _gate_matrix(name: str, params: Tuple[float, ...]):
    """Return the 2x2 (single-qubit) or 4x4 (two-qubit) unitary."""
    if name == "h":
        return [[1 / SQRT2, 1 / SQRT2], [1 / SQRT2, -1 / SQRT2]]
    if name == "x":
        return [[0, 1], [1, 0]]
    if name == "s":
        return [[1, 0], [0, _I]]
    if name == "sdg":
        return [[1, 0], [0, -_I]]
    if name == "t":
        return [[1, 0], [0, cmath.exp(_I * math.pi / 4)]]
    if name == "tdg":
        return [[1, 0], [0, cmath.exp(-_I * math.pi / 4)]]
    if name in ("rz", "ry"):
        theta = params[0]
        if name == "rz":
            return [
                [cmath.exp(-_I * theta / 2), 0],
                [0, cmath.exp(_I * theta / 2)],
            ]
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return [[c, -s], [s, c]]
    if name == "cx":
        # control q[0], target q[1]
        return [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
        ]
    if name == "cu1":
        phase = cmath.exp(_I * params[0])
        return [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, phase],
        ]
    if name == "swap":
        return [
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
        ]
    raise KeyError(name)


def gate_supported(name: str) -> bool:
    return name in WHITELIST


# ---------------------------------------------------------------------------
# State-vector machinery
# ---------------------------------------------------------------------------


def _apply_single(state: List[complex], matrix, q: int, n: int) -> None:
    """Apply a 2x2 matrix to qubit q in place."""
    step = 1 << q
    span = 1 << (q + 1)
    for base in range(0, len(state), span):
        for off in range(step):
            i0 = base + off
            i1 = i0 + step
            a, b = state[i0], state[i1]
            m00, m01 = matrix[0]
            m10, m11 = matrix[1]
            state[i0] = m00 * a + m01 * b
            state[i1] = m10 * a + m11 * b


def _apply_two(state: List[complex], matrix, q0: int, q1: int, n: int) -> None:
    """Apply a 4x4 matrix with control/least-significant qubit q0, target q1."""
    s0 = 1 << q0
    s1 = 1 << q1
    span0 = 1 << (q0 + 1)
    span1 = 1 << (q1 + 1)
    # iterate over all indices where qubits q0/q1 take each of the 4 combinations
    mask = (1 << n) - 1
    for base in range(1 << n):
        b0 = (base >> q0) & 1
        b1 = (base >> q1) & 1
        idx = base | (0 << q0) | (0 << q1)
        # build the 4 indices with qubit pair (00,01,10,11)
        idx00 = (base & ~((1 << q0) | (1 << q1))) | (0 << q0) | (0 << q1)
        idx01 = idx00 | (1 << q1)
        idx10 = idx00 | (1 << q0)
        idx11 = idx00 | (1 << q0) | (1 << q1)
        if base != idx00:
            continue  # each 4-tuple is processed once via its idx00
        vals = [state[idx00], state[idx01], state[idx10], state[idx11]]
        new_vals = [
            sum(matrix[r][c] * vals[c] for c in range(4)) for r in range(4)
        ]
        state[idx00], state[idx01], state[idx10], state[idx11] = new_vals


def simulate(circuit: Circuit) -> List[complex]:
    """Run the circuit on a noiseless state vector (amplitudes)."""
    n = circuit.qreg_size
    size = 1 << n
    state = [0j] * size
    state[0] = 1.0 + 0.0j
    for op in circuit.ops:
        if isinstance(op, MeasureOp):
            continue  # measurements are sampling-only; state evolves unitarily
        if isinstance(op, GateOp):
            if len(op.qubits) == 1:
                _apply_single(state, _gate_matrix(op.name, op.params), op.qubits[0], n)
            elif len(op.qubits) == 2:
                _apply_two(state, _gate_matrix(op.name, op.params), op.qubits[0], op.qubits[1], n)
            elif op.name == "ccx":
                _apply_ccx(state, op.qubits[0], op.qubits[1], op.qubits[2])
            else:
                raise ValueError(f"unsupported gate {op.name}")
    return state


def _apply_ccx(state: List[complex], a: int, b: int, c: int) -> None:
    """Apply Toffoli: flip qubit c when a and b are both |1>."""
    for i in range(len(state)):
        if (i >> a) & 1 and (i >> b) & 1 and not ((i >> c) & 1):
            j = i ^ (1 << c)
            state[i], state[j] = state[j], state[i]


def sample_counts(circuit: Circuit, shots: int, rng: random.Random = None) -> Dict[str, int]:
    """Sample `shots` measurement outcomes, returning little-endian bitstring counts.

    Measurement follows the circuit's measure ops: a qubit measured into cbit k
    contributes bit k of the key.  Qubits that are never measured still collapse
    through tracing; to keep behaviour identical across backends we sample the
    full register and then read off the measured cbits.
    """
    if shots <= 0:
        raise ValueError("shots must be positive")
    state = simulate(circuit)
    n = circuit.qreg_size
    probs = [abs(amp) ** 2 for amp in state]

    # map cbit -> qubit for measured pairs; unmeasured cbits stay 0
    cbit_to_qubit: Dict[int, int] = {}
    for op in circuit.ops:
        if isinstance(op, MeasureOp):
            cbit_to_qubit[op.cbit] = op.qubit
    width = max(circuit.creg_size, 1)

    rng = rng or random.Random()
    # alias-sampling-free: draw per shot via bisect on cumulative distribution
    cum = []
    acc = 0.0
    for p in probs:
        acc += p
        cum.append(acc)
    counts: Dict[str, int] = {}
    for _ in range(shots):
        r = rng.random() * acc
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] <= r:
                lo = mid + 1
            else:
                hi = mid
        idx = lo
        key_chars = ["0"] * width
        for cbit, qubit in cbit_to_qubit.items():
            key_chars[width - 1 - cbit] = "1" if (idx >> qubit) & 1 else "0"
        key = "".join(key_chars)
        counts[key] = counts.get(key, 0) + 1
    return counts


def ideal_distribution(circuit: Circuit) -> Dict[str, float]:
    """Exact measurement distribution (probabilities) for the measured cbits."""
    state = simulate(circuit)
    n = circuit.qreg_size
    cbit_to_qubit: Dict[int, int] = {}
    for op in circuit.ops:
        if isinstance(op, MeasureOp):
            cbit_to_qubit[op.cbit] = op.qubit
    width = max(circuit.creg_size, 1)
    dist: Dict[str, float] = {}
    for idx, amp in enumerate(state):
        key_chars = ["0"] * width
        for cbit, qubit in cbit_to_qubit.items():
            key_chars[width - 1 - cbit] = "1" if (idx >> qubit) & 1 else "0"
        key = "".join(key_chars)
        dist[key] = dist.get(key, 0.0) + abs(amp) ** 2
    return dist
