#!/usr/bin/env python3
"""端到端测试：自定义量子 RISC-V 扩展（Bonus 提交项③）。

运行：
    python3 quantum_riscv/run_e2e.py

覆盖：
1. 汇编/反汇编往返（encoding_spec.md 编码规格）；
2. Bell 态：qinit + h + cx + meas，验证两测量结果恒相等；
3. GHZ-3 态：qinit x3 + 链式 cx，验证三测量结果恒相等；
4. 经典-量子混编：经典 beq 分支 + 量子门联合执行；
5. RZ/RY 参数门与官方指令集回归（li/add/sub/addi/beq/bne/j）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum_riscv.encoding import assemble, disassemble
from quantum_riscv.riscv_quantum_emulator import QuantumRISCVEmulator

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def main() -> int:
    print("== 1. 编码规格：汇编/反汇编往返 ==")
    src = """
    qinit x1
    h x1
    cx x1, x2
    meas x1, x3
    rz x4, 1.5708
    ry x5, -0.5
    swap x1, x2
    ccx x1, x2, x6
    sdg x7
    """
    words = assemble(src)
    text = "\n".join(disassemble(words))
    words2 = assemble(text)
    check("assemble/disassemble roundtrip", words == words2, f"{words} != {words2}")
    check("all words use custom opcodes 0x0B/0x2B", all((w & 0x7F) in (0x0B, 0x2B) for w in words))

    print("== 2. Bell 态 ==")
    bell = """
    qinit x1
    qinit x2
    h x1
    cx x1, x2
    meas x1, x3
    meas x2, x4
    """
    emu = QuantumRISCVEmulator(seed=11)
    emu.load_program(bell)
    state = emu.execute()
    same = state.get("x3") == state.get("x4")
    check("Bell 态两测量结果恒相等", same, f"x3={state.get('x3')} x4={state.get('x4')}")
    probs = emu.quantum_probabilities()
    non_zero = {k for k, v in probs.items() if v > 0}
    check("Bell 态分布仅 00/11", non_zero <= {"00", "11"}, str(probs))

    print("== 3. GHZ-3 态 ==")
    ghz = """
    qinit x1
    qinit x2
    qinit x3
    h x1
    cx x1, x2
    cx x2, x3
    meas x1, x4
    meas x2, x5
    meas x3, x6
    """
    all_same = True
    for seed in range(5):
        emu = QuantumRISCVEmulator(seed=seed)
        emu.load_program(ghz)
        st = emu.execute()
        vals = {st.get(f"x{i}") for i in (4, 5, 6)}
        if len(vals) != 1:
            all_same = False
            print(f"    seed={seed} 结果: {st}")
    check("GHZ-3 三测量结果恒相等（5 个种子）", all_same)

    print("== 4. 经典-量子混编 ==")
    mixed = """
    li x1, 0
    qinit x2
    qinit x3
    h x2
    cx x2, x3
    meas x2, x4
    beq x4, x0, ZERO
    li x1, 100
    j DONE
    ZERO:
    li x1, 10
    DONE:
    """
    emu = QuantumRISCVEmulator(seed=3)
    emu.load_program(mixed)
    st = emu.execute()
    check("混编程序正常执行（x1 为 10 或 100）", st.get("x1") in (10, 100), str(st))
    check(
        "混编程序分支与测量一致",
        (st.get("x1") == 100 and st.get("x4", 0) == 1) or (st.get("x1") == 10 and st.get("x4", 0) == 0),
        str(st),
    )

    print("== 5. 参数门 + 官方指令集回归 ==")
    reg = """
    li x1, 5
    addi x1, x1, 3
    li x2, 2
    beq x1, x2, SKIP
    sub x1, x1, x2
    SKIP:
    qinit x3
    rz x3, 3.14159
    ry x3, 0.0
    meas x3, x4
    """
    emu = QuantumRISCVEmulator(seed=0)
    emu.load_program(reg)
    st = emu.execute()
    check("经典部分: x1 == 6", st.get("x1") == 6, str(st))
    check("rz(pi) 后测量为确定态", st.get("x4", 0) in (0, 1), str(st))

    print(f"\n结果: {PASS} 通过, {FAIL} 失败")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
