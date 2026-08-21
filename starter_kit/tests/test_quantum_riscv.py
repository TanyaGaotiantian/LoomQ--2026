"""Bonus tests: custom quantum RISC-V extension."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum_riscv.encoding import assemble, disassemble
from quantum_riscv.riscv_quantum_emulator import QuantumRISCVEmulator


class TestEncoding(unittest.TestCase):
    def test_roundtrip(self):
        src = "qinit x1\nh x1\ncx x1, x2\nmeas x1, x3\nrz x4, 1.5708\nry x5, -0.5\nswap x1, x2\nccx x1, x2, x6\nsdg x7\n"
        words = assemble(src)
        self.assertEqual(assemble("\n".join(disassemble(words))), words)

    def test_opcodes(self):
        words = assemble("qinit x1\nmeas x1, x3")
        self.assertEqual(words[0] & 0x7F, 0x0B)
        self.assertEqual(words[1] & 0x7F, 0x2B)


class TestEmulator(unittest.TestCase):
    def test_bell(self):
        emu = QuantumRISCVEmulator(seed=1)
        emu.load_program("""
        qinit x1
        qinit x2
        h x1
        cx x1, x2
        meas x1, x3
        meas x2, x4
        """)
        st = emu.execute()
        self.assertEqual(st.get("x3"), st.get("x4"))

    def test_ghz3(self):
        for seed in range(3):
            emu = QuantumRISCVEmulator(seed=seed)
            emu.load_program("""
            qinit x1
            qinit x2
            qinit x3
            h x1
            cx x1, x2
            cx x2, x3
            meas x1, x4
            meas x2, x5
            meas x3, x6
            """)
            st = emu.execute()
            self.assertEqual(len({st.get(f"x{i}") for i in (4, 5, 6)}), 1)

    def test_classical_still_works(self):
        emu = QuantumRISCVEmulator()
        emu.load_program("li x1, 5\naddi x1, x1, 3\nli x2, 2\nbeq x1, x2, SKIP\nsub x1, x1, x2\nSKIP:")
        st = emu.execute()
        self.assertEqual(st.get("x1"), 6)


if __name__ == "__main__":
    unittest.main()
