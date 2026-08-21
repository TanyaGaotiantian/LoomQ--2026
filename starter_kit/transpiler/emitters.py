"""Target IR emitters: one abstract middle layer, three native dialects.

This is the heart of L1.  A single parsed circuit (``qasm/parser.py``) is
rendered into each platform's native instruction format:

* ``spinq``    -> OpenQASM 2.0 (normalized, qelib1 whitelist)  [SpinQit/Taurus]
* ``originq``  -> OriginIR text (QINIT/CREG/gates/MEASURE)     [本源 pyqpanda/悟空]
* ``braket``   -> OpenQASM 3.0 (include-free; only gates the AWS
                  Braket parser accepts, others decomposed exactly) [Braket]

All decompositions are exact (verified against qiskit and the AWS Braket
LocalSimulator during development), never approximate.
"""

from __future__ import annotations

from typing import List, Optional

from qasm.parser import Circuit, GateOp, MeasureOp

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile_to_ir(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 text into the target backend's native format."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target {target!r}; expected one of {SUPPORTED_TARGETS}")
    from qasm.parser import parse_qasm

    circuit = parse_qasm(qasm_str)
    if target == "spinq":
        return _emit_spinq(circuit)
    if target == "originq":
        return _emit_originq(circuit)
    return _emit_braket(circuit)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _fmt(v: float) -> str:
    """Format an angle compactly and losslessly enough for parsers."""
    text = "%.15g" % v
    return text


def _emit_gate_ops(circuit: Circuit, emit_gate, emit_measure) -> List[str]:
    lines: List[str] = []
    for op in circuit.ops:
        if isinstance(op, MeasureOp):
            lines.extend(emit_measure(op))
        elif isinstance(op, GateOp):
            lines.extend(emit_gate(op))
    return lines


# ---------------------------------------------------------------------------
# spinq: OpenQASM 2.0 (qelib1 whitelist passthrough, normalized)
# ---------------------------------------------------------------------------


def _emit_spinq(circuit: Circuit) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    lines.append(f"qreg q[{circuit.qreg_size}];")
    lines.append(f"creg c[{circuit.creg_size}];")

    def gate(op: GateOp) -> List[str]:
        qs = ", ".join(f"q[{i}]" for i in op.qubits)
        if op.params:
            params = ", ".join(_fmt(p) for p in op.params)
            return [f"{op.name}({params}) {qs};"]
        return [f"{op.name} {qs};"]

    def measure(op: MeasureOp) -> List[str]:
        return [f"measure q[{op.qubit}] -> c[{op.cbit}];"]

    lines.extend(_emit_gate_ops(circuit, gate, measure))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# originq: OriginIR per target_ir_contract.md
# ---------------------------------------------------------------------------

_ORIGINQ_GATE_NAMES = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "rz": "RZ", "ry": "RY", "cx": "CNOT", "cu1": "CU1", "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def _emit_originq(circuit: Circuit) -> str:
    lines = [f"QINIT {circuit.qreg_size}", f"CREG {circuit.creg_size}"]

    def gate(op: GateOp) -> List[str]:
        name = _ORIGINQ_GATE_NAMES[op.name]
        qs = ", ".join(f"q[{i}]" for i in op.qubits)
        if op.params:
            # contract accepts both `RY(θ) q[0]` and `RY q[0],(θ)`
            return [f"{name}({_fmt(op.params[0])}) {qs}"]
        return [f"{name} {qs}"]

    def measure(op: MeasureOp) -> List[str]:
        return [f"MEASURE q[{op.qubit}], c[{op.cbit}]"]

    lines.extend(_emit_gate_ops(circuit, gate, measure))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# braket: OpenQASM 3.0 with only gates the AWS Braket parser accepts
# ---------------------------------------------------------------------------
# Empirically probed against amazon-braket-sdk LocalSimulator (see repo docs):
#   accepted : h x s t rz ry cnot swap cphaseshift cz cy ccnot cswap ...
#   rejected : cx cu1 ccx sdg tdg u1 p u u3 cp toffoli
# so we decompose the rejected ones exactly:
#   cx  -> cnot
#   sdg -> s s s
#   tdg -> t t t t t t t
#   cu1 -> cphaseshift(θ)
#   ccx -> standard qelib1 Toffoli identity (gate_identities.md) with tdg->t^7


def _emit_braket(circuit: Circuit) -> str:
    lines = ["OPENQASM 3.0;"]
    lines.append(f"qubit[{circuit.qreg_size}] q;")
    lines.append(f"bit[{circuit.creg_size}] c;")

    def gate(op: GateOp) -> List[str]:
        if op.name == "cx":
            return [f"cnot q[{op.qubits[0]}], q[{op.qubits[1]}];"]
        if op.name == "cu1":
            return [f"cphaseshift({_fmt(op.params[0])}) q[{op.qubits[0]}], q[{op.qubits[1]}];"]
        if op.name == "sdg":
            return [f"s q[{op.qubits[0]}];"] * 3
        if op.name == "tdg":
            return [f"t q[{op.qubits[0]}];"] * 7
        if op.name == "ccx":
            return _braket_ccx(op.qubits)
        if op.name == "rz":
            return [f"rz({_fmt(op.params[0])}) q[{op.qubits[0]}];"]
        if op.name == "ry":
            return [f"ry({_fmt(op.params[0])}) q[{op.qubits[0]}];"]
        return [f"{op.name} q[{op.qubits[0]}];"]

    def measure(op: MeasureOp) -> List[str]:
        return [f"c[{op.cbit}] = measure q[{op.qubit}];"]

    lines.extend(_emit_gate_ops(circuit, gate, measure))
    return "\n".join(lines) + "\n"


def _braket_ccx(qubits: tuple) -> List[str]:
    a, b, c = qubits
    # qelib1 Toffoli identity (gate_identities.md), with cx->cnot and tdg->t^7:
    #   h c; cnot b,c; tdg c; cnot a,c; t c; cnot b,c; tdg c; cnot a,c;
    #   t b; t c; h c; cnot a,b; t a; tdg b; cnot a,b;
    tdg_c = [f"t q[{c}];"] * 7
    tdg_b = [f"t q[{b}];"] * 7
    return [
        f"h q[{c}];",
        f"cnot q[{b}], q[{c}];",
        *tdg_c,
        f"cnot q[{a}], q[{c}];",
        f"t q[{c}];",
        f"cnot q[{b}], q[{c}];",
        *tdg_c,
        f"cnot q[{a}], q[{c}];",
        f"t q[{b}];",
        f"t q[{c}];",
        f"h q[{c}];",
        f"cnot q[{a}], q[{b}];",
        f"t q[{a}];",
        *tdg_b,
        f"cnot q[{a}], q[{b}];",
    ]
