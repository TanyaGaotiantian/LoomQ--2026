"""OpenQASM 2.0 parser (competition whitelist subset).

The formal evaluation only ever feeds circuits built from the official 12-gate
whitelist:  h, x, s, sdg, t, tdg, rz(theta), ry(theta), cx, cu1(theta), swap, ccx.
This parser is deliberately small and strict about that subset, mirroring the
contest rules: any gate outside the whitelist is a hard error (it would never
appear in a scoring circuit, so failing loudly is safer than guessing).

Supported syntax:
  OPENQASM 2.0;  include "qelib1.inc";
  qreg q[n];  creg c[n];
  <gate> q[i];            single-qubit, e.g. h q[0];  rz(0.5) q[1];
  <gate> q[a], q[b];      two-qubit,   e.g. cx q[0], q[1];  cu1(pi) q[0], q[1];
  ccx q[a], q[b], q[c];
  measure q -> c;  measure q[i] -> c[j];
  barrier q...;           parsed and ignored (not a gate, never in the whitelist)
  // comments, blank lines
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Circuit IR
# ---------------------------------------------------------------------------


@dataclass
class GateOp:
    """One gate application, e.g. `rz(0.5) q[1]`."""

    name: str  # normalized lowercase whitelist name
    qubits: Tuple[int, ...]  # register indices
    params: Tuple[float, ...] = ()  # numeric parameters in radians
    line: int = 0


@dataclass
class MeasureOp:
    qubit: int
    cbit: int
    line: int = 0


@dataclass
class Circuit:
    qreg_size: int
    creg_size: int
    ops: List[object] = field(default_factory=list)  # GateOp | MeasureOp

    @property
    def num_qubits(self) -> int:
        return self.qreg_size

    @property
    def depth(self) -> int:
        """Circuit depth (longest chain of gates; measurements excluded)."""
        layers = [0] * self.qreg_size
        for op in self.ops:
            if isinstance(op, MeasureOp):
                continue
            start = layers[op.qubits[0]]
            for q in op.qubits[1:]:
                start = max(start, layers[q])
            end = start + 1
            for q in op.qubits:
                layers[q] = end
        return max(layers, default=0)

    @property
    def num_gates(self) -> int:
        return sum(1 for op in self.ops if isinstance(op, GateOp))

    @property
    def num_measurements(self) -> int:
        return sum(1 for op in self.ops if isinstance(op, MeasureOp))


# ---------------------------------------------------------------------------
# Whitelist
# ---------------------------------------------------------------------------

#: The official 12-gate whitelist (normalized lowercase names).
WHITELIST = frozenset(
    {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"}
)

#: Gates that take a numeric angle parameter.
PARAMETERIZED = frozenset({"rz", "ry", "cu1"})


class QasmSyntaxError(ValueError):
    """Raised when the input is not valid whitelist OpenQASM 2.0."""


# ---------------------------------------------------------------------------
# Tokenizer / parser
# ---------------------------------------------------------------------------

_COMMENT_RE = re.compile(r"//.*$")
_WHITESPACE_RE = re.compile(r"\s+")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Numeric literal: 0, 3.14, .5, 1e-3, -pi/2, pi, 2*pi, -0.5*pi ...
_NUM_RE = re.compile(
    r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
    r"(?:\s*\*\s*pi|\s*pi)?"
)
_PI_RE = re.compile(r"[+-]?\s*pi(?:/\s*\d+)?")
_PI_EXPR_RE = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)?\s*\*?\s*pi\s*(?:/\s*(\d+))?$"
)


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def parse_qasm(qasm_str: str) -> Circuit:
    """Parse whitelist OpenQASM 2.0 text into a :class:`Circuit`."""
    if not isinstance(qasm_str, str) or not qasm_str.strip():
        raise QasmSyntaxError("empty circuit")
    text = _strip_comments(qasm_str)

    circuit = Circuit(qreg_size=0, creg_size=0)
    qreg: Optional[str] = None
    creg: Optional[str] = None
    saw_version = False

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue

        # OPENQASM 2.0;
        m = re.match(r"OPENQASM\s+2\.0\s*;", line)
        if m:
            saw_version = True
            continue
        if re.match(r"OPENQASM\s+", line):
            raise QasmSyntaxError(f"line {line_no}: only OpenQASM 2.0 is accepted")

        # include "qelib1.inc";
        m = re.match(r'include\s+"([^"]+)"\s*;', line)
        if m:
            continue

        # qreg q[2];  creg c[2];
        m = re.match(r"(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]\s*;", line)
        if m:
            kind, name, size = m.group(1), m.group(2), int(m.group(3))
            if size < 1:
                raise QasmSyntaxError(f"line {line_no}: register size must be >= 1")
            if kind == "qreg":
                if qreg is not None:
                    raise QasmSyntaxError(f"line {line_no}: duplicate qreg")
                qreg, circuit.qreg_size = name, size
            else:
                if creg is not None:
                    raise QasmSyntaxError(f"line {line_no}: duplicate creg")
                creg, circuit.creg_size = name, size
            continue

        # measure q -> c;  measure q[0] -> c[1];
        m = re.match(
            r"measure\s+(\w+)(?:\[\s*(\d+)\s*\])?\s*->\s*(\w+)(?:\[\s*(\d+)\s*\])?\s*;",
            line,
        )
        if m:
            q_name, q_idx, c_name, c_idx = m.groups()
            if q_name != qreg or c_name != creg:
                raise QasmSyntaxError(f"line {line_no}: measure references undeclared register")
            qi = int(q_idx) if q_idx is not None else None
            ci = int(c_idx) if c_idx is not None else None
            if qi is None and ci is not None:
                raise QasmSyntaxError(
                    f"line {line_no}: cannot measure whole register into a single cbit"
                )
            if qi is not None and ci is None:
                raise QasmSyntaxError(
                    f"line {line_no}: cannot measure a single qubit into the whole register"
                )
            if qi is None:
                # measure q -> c : all qubits -> same-index cbits
                if circuit.qreg_size != circuit.creg_size:
                    raise QasmSyntaxError(
                        f"line {line_no}: whole-register measure requires equal sizes"
                    )
                for k in range(circuit.qreg_size):
                    circuit.ops.append(MeasureOp(qubit=k, cbit=k, line=line_no))
            else:
                circuit.ops.append(MeasureOp(qubit=qi, cbit=ci, line=line_no))
            continue

        # barrier q[0], q[1];  (ignored)
        m = re.match(r"barrier\b", line)
        if m:
            continue

        # gate application
        gate_line = line
        op = _parse_gate_application(gate_line, line_no, circuit, qreg, creg)
        if op is not None:
            circuit.ops.append(op)
            continue

        raise QasmSyntaxError(f"line {line_no}: unrecognized statement: {line!r}")

    if not saw_version:
        raise QasmSyntaxError("missing OPENQASM 2.0; header")
    if qreg is None:
        raise QasmSyntaxError("missing qreg declaration")
    if creg is None:
        raise QasmSyntaxError("missing creg declaration")
    return circuit


def _parse_gate_application(
    line: str, line_no: int, circuit: Circuit, qreg: str, creg: str
) -> Optional[GateOp]:
    # forms:
    #   name q[i];
    #   name(θ) q[i];
    #   name q[i], q[j];
    #   name(θ) q[i], q[j];
    #   name q[i], q[j], q[k];
    m = re.match(r"([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s*(.+?)\s*;", line)
    if not m:
        return None
    name = m.group(1).lower()
    param_text = (m.group(2) or "").strip()
    qubit_text = m.group(3).strip()

    if name not in WHITELIST:
        raise QasmSyntaxError(
            f"line {line_no}: gate {name!r} is outside the official 12-gate whitelist"
        )

    params: Tuple[float, ...] = ()
    if name in PARAMETERIZED:
        if not param_text:
            raise QasmSyntaxError(f"line {line_no}: gate {name} requires a parameter")
        params = tuple(_parse_number(p.strip()) for p in param_text.split(","))
    elif param_text:
        raise QasmSyntaxError(f"line {line_no}: gate {name} takes no parameter")

    qubits = _parse_qubit_list(qubit_text, qreg, circuit.qreg_size, line_no)
    expected = 3 if name == "ccx" else 2 if name in ("cx", "cu1", "swap") else 1
    if len(qubits) != expected:
        raise QasmSyntaxError(
            f"line {line_no}: gate {name} expects {expected} qubit argument(s), got {len(qubits)}"
        )
    return GateOp(name=name, qubits=qubits, params=params, line=line_no)


def _parse_qubit_list(text: str, qreg: str, size: int, line_no: int) -> Tuple[int, ...]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    out = []
    for part in parts:
        m = re.fullmatch(r"(\w+)\s*\[\s*(\d+)\s*\]", part)
        if not m:
            raise QasmSyntaxError(f"line {line_no}: expected qubit index like q[0], got {part!r}")
        reg, idx = m.group(1), int(m.group(2))
        if reg != qreg:
            raise QasmSyntaxError(f"line {line_no}: unknown register {reg!r}")
        if not (0 <= idx < size):
            raise QasmSyntaxError(f"line {line_no}: qubit index {idx} out of range")
        out.append(idx)
    return tuple(out)


def _parse_number(text: str) -> float:
    """Parse a numeric literal; supports pi and arithmetic with pi."""
    if not text:
        raise QasmSyntaxError("empty numeric parameter")
    text = text.replace(" ", "")
    m = _PI_EXPR_RE.fullmatch(text)
    if m:
        coeff = 1.0 if not m.group(1) else float(m.group(1))
        denom = 1.0 if not m.group(2) else float(m.group(2))
        return coeff * math.pi / denom
    try:
        return float(text)
    except ValueError as exc:
        raise QasmSyntaxError(f"invalid numeric parameter {text!r}") from exc
