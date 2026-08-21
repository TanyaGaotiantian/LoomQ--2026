"""LoomQ Bonus: fork of the official `riscv_emulator.py` with quantum instructions.

This class extends the official `TinyRISCVEmulator` (whose `li/add/sub/addi/
beq/bne/j` semantics are preserved verbatim - see the parent file) with the
custom quantum extension defined in `encoding_spec.md`:

    qinit rd | h rd | x rd | z rd | s rd | sdg rd
    cx rs1, rd | meas rs1, rd | rz rd, imm | ry rd, imm
    swap rs1, rd | ccx rs1, rs2, rd

Quantum state is held in a `QuantumState` engine; `meas` collapses the state
and writes the outcome into a general-purpose register, so classical and
quantum instructions can be freely mixed.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from riscv_emulator import TinyRISCVEmulator

from quantum_riscv.quantum_core import QuantumState

QUANTUM_OPS = {
    "qinit", "h", "x", "z", "s", "sdg", "cx", "meas", "rz", "ry", "swap", "ccx",
}


class QuantumRISCVEmulator(TinyRISCVEmulator):
    def __init__(self, seed: int = None):
        super().__init__()
        self.quantum = QuantumState(rng=random.Random(seed))
        self._quantum_register: Dict[int, int] = {}  # general reg -> qubit index

    # -- loading -----------------------------------------------------------

    def load_program(self, asm_code: str):
        """Parse text; accepts official mnemonics plus the quantum extension."""
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.quantum = QuantumState(rng=random.Random())
        self._quantum_register = {}

        temp_instructions = []
        for line in asm_code.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "#" in line:
                line = line.split("#")[0].strip()
            if line.endswith(":"):
                label_name = line[:-1].strip()
                self.labels[label_name] = len(temp_instructions)
                continue
            elif ":" in line:
                parts = line.split(":", 1)
                self.labels[parts[0].strip()] = len(temp_instructions)
                line = parts[1].strip()
            tokens = line.replace(",", " ").split()
            op = tokens[0].lower()
            args = tokens[1:]
            temp_instructions.append((op, args))
        self.instructions = temp_instructions

    def load_words(self, words: List[int]):
        """Load raw 32-bit encoded words (quantum extension only)."""
        from quantum_riscv.encoding import disassemble

        text = "\n".join(disassemble(words))
        self.load_program(text)

    # -- execution ---------------------------------------------------------

    def _qubit(self, reg: str) -> int:
        """Quantum ops address qubits by register *value* (set by qinit)."""
        return self.get_register(reg)

    def _execute_quantum(self, op: str, args: List[str]) -> bool:
        """Handle a quantum op. Returns True when handled."""
        if op not in QUANTUM_OPS:
            return False
        if op == "qinit":
            q = self.quantum.allocate()
            self.set_register(args[0], q)
            return True
        if op in ("h", "x", "z", "s", "sdg"):
            q = self._qubit(args[0])
            self.quantum.apply_gate(op, q)
            return True
        if op in ("rz", "ry"):
            q = self._qubit(args[0])
            angle = float(args[1])
            self.quantum.apply_gate(op, q, params=(angle,))
            return True
        if op == "cx":
            ctrl, tgt = self._qubit(args[0]), self._qubit(args[1])
            self.quantum.apply_gate("cx", ctrl, tgt)
            return True
        if op == "swap":
            a, b = self._qubit(args[0]), self._qubit(args[1])
            self.quantum.apply_gate("swap", a, b)
            return True
        if op == "ccx":
            a, b, c = self._qubit(args[0]), self._qubit(args[1]), self._qubit(args[2])
            self.quantum.apply_gate("ccx", a, b, c)
            return True
        if op == "meas":
            q = self._qubit(args[0])
            outcome = self.quantum.measure(q)
            self.set_register(args[1], outcome)
            return True
        return True

    def execute(self) -> Dict[str, int]:
        """Execute until the program ends; returns non-zero register state."""
        steps = 0
        num_instr = len(self.instructions)
        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1
            if self._execute_quantum(op, args):
                self.pc = next_pc
                continue
            # ---- official instruction subset (verbatim from the official file) ----
            if op == "li":
                rd, imm = args[0], int(args[1])
                self.set_register(rd, imm)
            elif op == "add":
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) + self.get_register(rs2))
            elif op == "sub":
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) - self.get_register(rs2))
            elif op == "addi":
                rd, rs1, imm = args[0], args[1], int(args[2])
                self.set_register(rd, self.get_register(rs1) + imm)
            elif op == "beq":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) == self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
            elif op == "bne":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) != self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
            elif op == "j":
                label = args[0]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]
            else:
                raise ValueError(f"不支持的指令操作: {op}")
            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    # -- introspection -----------------------------------------------------

    def quantum_probabilities(self) -> Dict[str, float]:
        return self.quantum.probabilities()
