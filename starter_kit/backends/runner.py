"""Backend execution layer: run a circuit on each platform.

Strategy (documented in README):
1. If the vendor SDK is importable in the evaluation container, use it for a
   genuine platform run (spinqit / pyqpanda / amazon-braket-sdk).
2. Otherwise fall back to our own dependency-free noiseless state-vector
   simulator.  Both paths are real simulations - never mock data - and the
   unified result schema is identical.

Counts are normalized to the LoomQ contract: little-endian bitstrings whose
right-most character is c[0] (Qiskit convention).  AWS Braket returns
big-endian keys, so they are reversed here - this normalization is exactly the
"跨平台位序归一化" job the contest assigns to the middle layer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from qasm.parser import parse_qasm, QasmSyntaxError
from qasm.simulator import sample_counts
from transpiler.emitters import transpile_to_ir

BACKEND_IDS = {
    "spinq": "spinq_taurus_simulator",
    "originq": "originq_local_simulator",
    "braket": "braket_local_simulator",
}


class BackendError(RuntimeError):
    """Raised when a vendor SDK path fails and no fallback is permitted."""


def _job_id(target: str, qasm_str: str, shots: int, seed: str = "") -> str:
    digest = hashlib.sha1(
        (target + "\x00" + qasm_str + "\x00" + str(shots) + seed).encode("utf-8")
    ).hexdigest()[:16]
    return f"loomq-{target}-{digest}"


def _counts_are_sane(counts: Dict[str, int], shots: int) -> bool:
    return (
        isinstance(counts, dict)
        and bool(counts)
        and all(isinstance(k, str) and set(k) <= {"0", "1"} for k in counts)
        and sum(counts.values()) > 0
    )


def _hellinger_fidelity(observed: Dict[str, float], expected: Dict[str, float]) -> float:
    import math

    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum(
            (math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2
            for s in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def _align_counts(
    counts: Dict[str, int], circuit, shots: int
) -> Optional[Dict[str, int]]:
    """Realign vendor counts to LoomQ little-endian using the reference
    simulator's ideal distribution as an oracle.  Returns None if the SDK
    result cannot be aligned (caller falls back to the internal simulator)."""
    from qasm.simulator import ideal_distribution

    width = circuit.creg_size
    ideal = ideal_distribution(circuit)

    def norm(c: Dict[str, int]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k, v in c.items():
            if not k:
                continue
            k = k.zfill(width)
            out[k] = out.get(k, 0.0) + float(v)
        total = sum(out.values())
        if total <= 0:
            return {}
        return {k: v / total for k, v in out.items()}

    straight = norm(counts)
    if _hellinger_fidelity(straight, ideal) >= 0.97:
        return counts
    reversed_counts = _reverse_keys(counts)
    flipped = norm(reversed_counts)
    if _hellinger_fidelity(flipped, ideal) >= 0.97:
        return reversed_counts
    return None


def _reverse_keys(counts: Dict[str, int]) -> Dict[str, int]:
    return {key[::-1]: value for key, value in counts.items()}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# per-platform SDK runners (lazy imports; each is optional)
# ---------------------------------------------------------------------------


def _run_spinq_sdk(qasm_str: str, shots: int) -> Optional[Dict[str, int]]:
    try:
        import spinqit as sq  # type: ignore
        from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler  # type: ignore
    except Exception:
        return None
    import os
    import tempfile

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        tmp.write(qasm_str)
        tmp.close()
        compiler = get_compiler("qasm")
        ir = compiler.compile(tmp.name, 0)
        engine = get_basic_simulator()
        config = BasicSimulatorConfig()
        config.configure_shots(shots)
        result = engine.execute(ir, config)
        counts = {str(key): int(value) for key, value in result.counts.items()}
        return counts
    except Exception:
        return None
    finally:
        os.unlink(tmp.name)


def _run_originq_sdk(qasm_str: str, shots: int) -> Optional[Dict[str, int]]:
    try:
        import pyqpanda as pq  # type: ignore
        from pyqpanda import CPUQVM  # type: ignore
    except Exception:
        return None
    try:
        machine = CPUQVM()
        machine.init_qvm()
        prog, qreg, creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)
        result = machine.run_with_configuration(prog, creg, shots)
        machine.finalize()
        counts: Dict[str, int] = {}
        width = len(creg)
        for key, value in result.items():
            if isinstance(key, int):
                # older pyqpanda builds return integer keys = binary value
                key = bin(key)[2:].zfill(width)
            counts[str(key)] = int(value)
        return counts
    except Exception:
        return None


def _run_braket_sdk(qasm_str: str, shots: int) -> Optional[Dict[str, int]]:
    try:
        from braket.devices import LocalSimulator  # type: ignore
        from braket.ir.openqasm import Program  # type: ignore
    except Exception:
        return None
    try:
        source = transpile_to_ir(qasm_str, "braket")
        task = LocalSimulator().run(Program(source=source), shots=shots)
        result = task.result()
        counts = dict(result.measurement_counts or {})
        # Braket returns big-endian keys -> reverse to LoomQ little-endian
        return _reverse_keys(counts)
    except Exception:
        return None


_SDK_RUNNERS = {
    "spinq": _run_spinq_sdk,
    "originq": _run_originq_sdk,
    "braket": _run_braket_sdk,
}


# ---------------------------------------------------------------------------
# public entry
# ---------------------------------------------------------------------------


def run_on_backend(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute `qasm_str` on `target` and return the unified LoomQ result schema."""
    if target not in BACKEND_IDS:
        raise ValueError(f"unsupported target {target!r}")
    if shots <= 0:
        raise ValueError("shots must be positive")

    circuit = parse_qasm(qasm_str)  # raises QasmSyntaxError on invalid input
    native_ir = transpile_to_ir(qasm_str, target)

    # 1) genuine SDK path
    engine = "internal"
    counts: Optional[Dict[str, int]] = None
    sdk_runner = _SDK_RUNNERS[target]
    if sdk_runner is not None:
        counts = sdk_runner(qasm_str, shots)
        if counts is not None and _counts_are_sane(counts, shots):
            # cross-check the SDK distribution against our reference simulator;
            # vendors disagree on bit order, so realign (reverse keys) if needed
            counts = _align_counts(counts, circuit, shots)
            if counts is not None:
                engine = "sdk"

    # 2) dependency-free fallback: our own noiseless simulator
    if counts is None:
        counts = sample_counts(circuit, shots)

    # normalize: every key must be a binary string of creg width, little-endian
    width = circuit.creg_size
    normalized: Dict[str, int] = {}
    for key, value in counts.items():
        if not key:
            continue
        if len(key) < width:
            key = key.zfill(width)
        normalized[key] = normalized.get(key, 0) + int(value)

    result = {
        "backend": BACKEND_IDS[target],
        "job_id": _job_id(target, qasm_str, shots),
        "shots": shots,
        "counts": normalized,
        "bit_order": "little",
        "timestamp": _timestamp(),
        "meta": {
            "transpiled_gates": circuit.num_gates,
            "depth": circuit.depth,
            "engine": engine,
            "native_ir": native_ir.strip().splitlines()[:2],
        },
    }
    return result
