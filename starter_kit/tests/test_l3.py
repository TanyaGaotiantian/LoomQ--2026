"""L3 tests: Hybrid-QASM -> RISC-V compiler (deterministic + randomized)."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hybrid.compiler import compile_hybrid
from hybrid.parser import split_hybrid
from riscv_emulator import TinyRISCVEmulator

PUBLIC = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }
"""


class TestPublic(unittest.TestCase):
    def test_public_case(self):
        quantum, asm = compile_hybrid(PUBLIC)
        self.assertIsInstance(quantum, list)
        self.assertIn("measure", "\n".join(quantum))
        emu = TinyRISCVEmulator()
        for measured, expected in ((0, 3), (1, 7)):
            emu.load_program(asm)
            emu.set_register("x10", measured)
            self.assertEqual(emu.execute().get("x1", 0), expected)

    def test_full_example(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 100; } else { r1 = 10; }
  r1 = r1 + 5;
}
cx q[0], q[1];
"""
        quantum, asm = compile_hybrid(source)
        self.assertEqual(quantum[-1], "cx q[0], q[1];")
        emu = TinyRISCVEmulator()
        for measured, expected in ((0, 15), (1, 105)):
            emu.load_program(asm)
            emu.set_register("x10", measured)
            self.assertEqual(emu.execute().get("x1", 0), expected)


# ---------------------------------------------------------------------------
# randomized stress vs a reference interpreter
# ---------------------------------------------------------------------------


def reference(ast, cbits):
    regs = {i: 0 for i in range(1, 10)}

    def ev(e):
        if isinstance(e, int):
            return e
        if isinstance(e, tuple):
            if e[0] == "reg":
                return regs[e[1]] if e[1] <= 9 else cbits[e[1] - 10]
            if e[0] == "lit":
                return e[1]
            if e[0] == "bin":
                _, op, l, r = e
                lv, rv = ev(l), ev(r)
                return lv + rv if op == "+" else lv - rv
        raise ValueError(e)

    def run(stmts):
        for s in stmts:
            if s[0] == "assign":
                _, reg, expr = s
                regs[reg] = ev(expr)
            elif s[0] == "if":
                _, op, l, r, thenb, elseb = s
                lv, rv = ev(l), ev(r)
                cond = (lv == rv) if op == "==" else (lv != rv)
                run(thenb if cond else elseb)

    run(ast)
    return dict(regs)


def to_source(ast):
    def es(e):
        if isinstance(e, int):
            return str(e)
        if isinstance(e, tuple):
            if e[0] == "reg":
                return f"r{e[1]}" if e[1] <= 9 else f"c[{e[1] - 10}]"
            if e[0] == "lit":
                return str(e[1])
            if e[0] == "bin":
                return f"({es(e[2])} {e[1]} {es(e[3])})"
        raise ValueError(e)

    def bs(stmts, ind="  "):
        out = []
        for s in stmts:
            if s[0] == "assign":
                out.append(f"{ind}r{s[1]} = {es(s[2])};")
            elif s[0] == "if":
                _, op, l, r, thenb, elseb = s
                out.append(f"{ind}if ({es(l)} {op} {es(r)}) {{")
                out += bs(thenb, ind + "  ")
                out.append(f"{ind}}} else {{")
                out += bs(elseb, ind + "  ")
                out.append(f"{ind}}}")
        return out

    return "\n".join(bs(ast))


def make_generator(seed):
    rng = random.Random(seed)

    def expr(depth, nbits):
        if depth <= 0 or rng.random() < 0.5:
            choice = rng.random()
            if choice < 0.4:
                return ("lit", rng.randint(-50, 50))
            if choice < 0.8:
                return ("reg", rng.randint(1, 9))
            return ("reg", 10 + rng.randrange(nbits))
        op = rng.choice(["+", "-"])
        return ("bin", op, expr(depth - 1, nbits), expr(depth - 1, nbits))

    def stmt(depth, nbits):
        if depth <= 0 or rng.random() < 0.6:
            return ("assign", rng.randint(1, 9), expr(2, nbits))
        op = rng.choice(["==", "!="])
        l = expr(1, nbits)
        r = expr(1, nbits)
        thenb = [stmt(depth - 1, nbits) for _ in range(rng.randint(1, 3))]
        elseb = [stmt(depth - 1, nbits) for _ in range(rng.randint(0, 3))]
        return ("if", op, l, r, thenb, elseb)

    def program():
        nbits = rng.randint(1, 3)
        ast = [stmt(2, nbits) for _ in range(rng.randint(1, 4))]
        return nbits, ast

    return program


class TestRandomized(unittest.TestCase):
    def test_150_programs_all_combos(self):
        gen = make_generator(2026)
        emu = TinyRISCVEmulator()
        for _ in range(150):
            nbits, ast = gen()
            src = to_source(ast)
            hybrid = (
                "OPENQASM 2.0;\nqreg q[2];\ncreg c[2];\nmeasure q[0] -> c[0];\n"
                "classical {\n" + src + "\n}\n"
            )
            quantum, asm = compile_hybrid(hybrid)
            for combo in range(1 << nbits):
                cbits = [(combo >> k) & 1 for k in range(nbits)]
                ref = reference(ast, cbits)
                emu.load_program(asm)
                for k, v in enumerate(cbits):
                    emu.set_register(f"x{10 + k}", v)
                state = emu.execute()
                for reg, val in ref.items():
                    self.assertEqual(state.get(f"x{reg}", 0), val,
                                     f"program:\n{src}\ncombo={combo:0{nbits}b} r{reg}")


if __name__ == "__main__":
    unittest.main()
