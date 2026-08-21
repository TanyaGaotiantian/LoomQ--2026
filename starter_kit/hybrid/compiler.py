"""Hybrid-QASM -> RISC-V assembly compiler.

Takes the classical AST from :mod:`hybrid.parser` and emits assembly for the
official `TinyRISCVEmulator` instruction subset: `li, add, sub, addi, beq,
bne, j`.  Register mapping (contest rules):

    r1..r9  -> x1..x9
    c[k]    -> x10 + k        (measurement values injected by the evaluator)

Scratch registers are allocated dynamically from the *highest* free registers
so they never collide with r1..r9 or with any injected measurement register
x10..x10+creg_size-1.  Assignments whose right-hand side reads the target
register are evaluated into a scratch first, avoiding read-before-write
hazards.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

from hybrid.parser import (
    Assign,
    BinOp,
    IfStmt,
    Lit,
    RegRef,
    parse_classical_block,
    split_hybrid,
)

_FALLBACK_SCRATCH = ("x30", "x31")


class ScratchAllocator:
    """LIFO pool of scratch registers above the measurement range."""

    def __init__(self, quantum_ops: List[str]):
        nbits = 1
        for line in quantum_ops:
            m = re.match(r"creg\s+\w+\s*\[\s*(\d+)\s*\]\s*;", line)
            if m:
                nbits = int(m.group(1))
                break
        lowest = 10 + nbits
        if lowest > 31:
            lowest = 29  # fallback window (creg so large that x30/x31 may clash)
        self._pool = [f"x{i}" for i in range(31, lowest - 1, -1)]

    def acquire(self, exclude: Set[str]) -> str:
        for reg in self._pool:
            if reg not in exclude:
                self._pool.remove(reg)
                return reg
        raise RuntimeError("expression nesting too deep (no scratch register left)")

    def release(self, reg: str) -> None:
        if reg not in self._pool:
            self._pool.append(reg)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM text -> (quantum_ops, riscv_assembly)."""
    quantum, classical = split_hybrid(hybrid_qasm_str)
    if classical is None:
        return quantum, ""
    ast = parse_classical_block(classical)
    asm: List[str] = []
    alloc = ScratchAllocator(quantum)
    _emit_block(ast, asm, alloc)
    if not asm:
        return quantum, ""
    return quantum, "\n".join(asm) + "\n"


# ---------------------------------------------------------------------------
# expression helpers
# ---------------------------------------------------------------------------


def _reads_reg(expr, reg: int) -> bool:
    """True when the expression reads r-register `reg` (x{reg})."""
    if isinstance(expr, RegRef):
        return expr.reg == reg
    if isinstance(expr, BinOp):
        return _reads_reg(expr.left, reg) or _reads_reg(expr.right, reg)
    return False


def _load_expr(
    expr, target: str, asm: List[str], alloc: ScratchAllocator, exclude: Set[str]
) -> None:
    """Load the value of `expr` into register `target`."""
    if isinstance(expr, Lit):
        asm.append(f"li {target}, {expr.value}")
        return
    if isinstance(expr, RegRef):
        if target != f"x{expr.reg}":
            asm.append(f"add {target}, x{expr.reg}, x0")
        return
    if not isinstance(expr, BinOp):
        raise ValueError("unknown expression node")

    op = expr.op
    left, right = expr.left, expr.right
    left_simple = isinstance(left, (Lit, RegRef))
    right_simple = isinstance(right, (Lit, RegRef))

    if right_simple and isinstance(right, Lit):
        _load_expr(left, target, asm, alloc, exclude)
        asm.append(f"addi {target}, {target}, {right.value if op == '+' else -right.value}")
        return
    if left_simple and isinstance(left, Lit):
        if op == "+":
            _load_expr(right, target, asm, alloc, exclude)
            asm.append(f"addi {target}, {target}, {left.value}")
            return
        temp = alloc.acquire(exclude | {target})
        _load_expr(right, temp, asm, alloc, exclude | {target})
        asm.append(f"li {target}, {left.value}")
        asm.append(f"sub {target}, {target}, {temp}")
        alloc.release(temp)
        return
    if left_simple and right_simple:
        _load_expr(left, target, asm, alloc, exclude)
        if isinstance(right, RegRef):
            asm.append(f"{'add' if op == '+' else 'sub'} {target}, {target}, x{right.reg}")
        return
    if left_simple:
        # register op compound: evaluate compound into target, combine with register
        _load_expr(right, target, asm, alloc, exclude)
        if op == "+":
            asm.append(f"add {target}, {target}, x{left.reg}")
        else:
            asm.append(f"sub {target}, x{left.reg}, {target}")
        return
    if right_simple:
        _load_expr(left, target, asm, alloc, exclude)
        if isinstance(right, RegRef):
            asm.append(f"{'add' if op == '+' else 'sub'} {target}, {target}, x{right.reg}")
        return
    # both compound: temp for the right side
    temp = alloc.acquire(exclude | {target})
    _load_expr(left, target, asm, alloc, exclude | {temp})
    _load_expr(right, temp, asm, alloc, exclude | {target})
    asm.append(f"{'add' if op == '+' else 'sub'} {target}, {target}, {temp}")
    alloc.release(temp)


def _emit_assignment(stmt: Assign, asm: List[str], alloc: ScratchAllocator) -> None:
    target_reg = stmt.target
    if _reads_reg(stmt.expr, target_reg):
        # evaluate into a scratch first to preserve the old value
        temp = alloc.acquire(set())
        _load_expr(stmt.expr, temp, asm, alloc, {temp})
        asm.append(f"add x{target_reg}, {temp}, x0")
        alloc.release(temp)
    else:
        _load_expr(stmt.expr, f"x{target_reg}", asm, alloc, set())


def _emit_condition(
    op: str, left, right, else_label: str, asm: List[str], alloc: ScratchAllocator
) -> None:
    """Emit branch to else_label when the condition is FALSE."""
    if isinstance(left, Lit) and isinstance(right, Lit):
        equal = left.value == right.value
        want_then = (op == "==" and equal) or (op == "!=" and not equal)
        if not want_then:
            asm.append(f"j {else_label}")
        return

    def reg_of(expr, exclude: Set[str]) -> str:
        if isinstance(expr, Lit):
            reg = alloc.acquire(exclude)
            asm.append(f"li {reg}, {expr.value}")
            return reg
        if isinstance(expr, RegRef):
            return f"x{expr.reg}"
        reg = alloc.acquire(exclude)
        _load_expr(expr, reg, asm, alloc, exclude | {reg})
        return reg

    a = reg_of(left, set())
    b = reg_of(right, {a})
    if isinstance(left, (Lit, BinOp)):
        alloc.release(a)
    if isinstance(right, (Lit, BinOp)):
        alloc.release(b)
    if op == "==":
        asm.append(f"bne {a}, {b}, {else_label}")
    else:  # '!='
        asm.append(f"beq {a}, {b}, {else_label}")


def _emit_if(stmt: IfStmt, asm: List[str], alloc: ScratchAllocator) -> None:
    else_label = _label("ELSE")
    end_label = _label("ENDIF")
    _emit_condition(stmt.op, stmt.left, stmt.right, else_label, asm, alloc)
    _emit_block(stmt.then_body, asm, alloc)
    if stmt.else_body:
        asm.append(f"j {end_label}")
        asm.append(f"{else_label}:")
        _emit_block(stmt.else_body, asm, alloc)
        asm.append(f"{end_label}:")
    else:
        asm.append(f"{else_label}:")


def _emit_block(stmts: List[object], asm: List[str], alloc: ScratchAllocator) -> None:
    for stmt in stmts:
        if isinstance(stmt, Assign):
            _emit_assignment(stmt, asm, alloc)
        elif isinstance(stmt, IfStmt):
            _emit_if(stmt, asm, alloc)
        else:
            raise ValueError(f"unknown statement node: {stmt!r}")


_COUNTER = [0]


def _label(prefix: str) -> str:
    _COUNTER[0] += 1
    return f"{prefix}_{_COUNTER[0]}"
