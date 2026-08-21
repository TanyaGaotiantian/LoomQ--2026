"""Small state-vector engine for the quantum RISC-V extension.

Reuses the exact same gate matrices as `qasm/simulator.py` so results agree
with the L1 reference simulator bit-for-bit.
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Dict, List

_I = complex(0, 1)
_SQRT2 = math.sqrt(2.0)


def _matrix(name: str, params: tuple):
    if name == "h":
        return [[1 / _SQRT2, 1 / _SQRT2], [1 / _SQRT2, -1 / _SQRT2]]
    if name == "x":
        return [[0, 1], [1, 0]]
    if name == "z":
        return [[1, 0], [0, -1]]
    if name == "s":
        return [[1, 0], [0, _I]]
    if name == "sdg":
        return [[1, 0], [0, -_I]]
    if name == "rz":
        theta = params[0]
        return [[cmath.exp(-_I * theta / 2), 0], [0, cmath.exp(_I * theta / 2)]]
    if name == "ry":
        theta = params[0]
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return [[c, -s], [s, c]]
    if name == "cx":
        return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]]
    if name == "swap":
        return [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]]
    raise KeyError(name)


class QuantumState:
    """State vector over dynamically allocated qubits (indices 0..n-1)."""

    def __init__(self, rng: random.Random = None):
        self._amps: List[complex] = [1.0 + 0.0j]
        self._n = 0
        self._rng = rng or random.Random()

    @property
    def num_qubits(self) -> int:
        return self._n

    def allocate(self) -> int:
        """Add one qubit in |0>; return its index."""
        idx = self._n
        self._amps = self._amps + [0j] * len(self._amps)
        self._n += 1
        return idx

    def _apply_single(self, q: int, name: str, params: tuple = ()) -> None:
        m = _matrix(name, params)
        step = 1 << q
        span = 1 << (q + 1)
        for base in range(0, len(self._amps), span):
            for off in range(step):
                i0, i1 = base + off, base + off + step
                a, b = self._amps[i0], self._amps[i1]
                self._amps[i0] = m[0][0] * a + m[0][1] * b
                self._amps[i1] = m[1][0] * a + m[1][1] * b

    def _apply_two(self, q0: int, q1: int, name: str) -> None:
        m = _matrix(name, ())
        for i in range(len(self._amps)):
            if (i >> q0) & 1 or (i >> q1) & 1:
                continue
            idx00 = i
            idx01 = i | (1 << q1)
            idx10 = i | (1 << q0)
            idx11 = i | (1 << q0) | (1 << q1)
            vals = [self._amps[idx00], self._amps[idx01], self._amps[idx10], self._amps[idx11]]
            new_vals = [sum(m[r][c] * vals[c] for c in range(4)) for r in range(4)]
            self._amps[idx00], self._amps[idx01], self._amps[idx10], self._amps[idx11] = new_vals

    def apply_gate(self, name: str, *qubits: int, params: tuple = ()) -> None:
        if len(qubits) == 1:
            if name == "ccx":
                raise ValueError("ccx needs three qubits")
            self._apply_single(qubits[0], name, params)
        elif len(qubits) == 2:
            if name == "ccx":
                raise ValueError("ccx needs three qubits")
            self._apply_two(qubits[0], qubits[1], name)
        elif len(qubits) == 3 and name == "ccx":
            a, b, c = qubits
            for i in range(len(self._amps)):
                if (i >> a) & 1 and (i >> b) & 1 and not ((i >> c) & 1):
                    j = i ^ (1 << c)
                    self._amps[i], self._amps[j] = self._amps[j], self._amps[i]
        else:
            raise ValueError(f"unsupported gate {name}{qubits}")

    def measure(self, q: int) -> int:
        """Sample qubit q and collapse the state. Returns 0 or 1."""
        prob1 = 0.0
        for i, amp in enumerate(self._amps):
            if (i >> q) & 1:
                prob1 += abs(amp) ** 2
        outcome = 1 if self._rng.random() < prob1 else 0
        mask = 1 << q
        norm = 0.0
        for i in range(len(self._amps)):
            amp = self._amps[i]
            if ((i >> q) & 1) == outcome:
                self._amps[i] = amp
                norm += abs(amp) ** 2
            else:
                self._amps[i] = 0j
        if norm > 0:
            scale = math.sqrt(norm)
            self._amps = [a / scale for a in self._amps]
        return outcome

    def probabilities(self) -> Dict[str, float]:
        n = self.num_qubits
        return {
            format(i, "0%db" % n): abs(amp) ** 2 for i, amp in enumerate(self._amps)
        }
