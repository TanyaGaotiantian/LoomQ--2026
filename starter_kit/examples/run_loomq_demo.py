#!/usr/bin/env python3
"""端到端演示：L1 + L2 + L3 一条命令看完本队伍全部能力。

运行：python3 examples/run_loomq_demo.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import adapter


def main() -> int:
    bell = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

    print("=" * 62)
    print("L1 · 三平台转译（同一电路 → 三种原生方言）")
    print("=" * 62)
    for target in ("spinq", "originq", "braket"):
        print(f"\n--- {target} ---")
        print(adapter.transpile(bell, target).strip())

    print("\n" + "=" * 62)
    print("L1 · 三平台运行（统一 Schema）")
    print("=" * 62)
    for target in ("spinq", "originq", "braket"):
        result = adapter.run(bell, target, 8192)
        print(f"\n{result['backend']}  engine={result['meta']['engine']}")
        print(f"  counts = {result['counts']}")

    print("\n" + "=" * 62)
    print("L2 · 智能体（离线演示模式；配置 LOOMQ_LLM_* 后自动走模型）")
    print("=" * 62)
    reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并进行全测量")
    print(reply)

    print("\n" + "=" * 62)
    print("L3 · Hybrid-QASM → RISC-V")
    print("=" * 62)
    hybrid = """OPENQASM 2.0;
qreg q[2];
creg c[2];
measure q[0] -> c[0];
classical { if (c[0] == 1) { r1 = 100; } else { r1 = 10; } r1 = r1 + 5; }
"""
    quantum, asm = adapter.compile_hybrid(hybrid)
    print("量子操作序列:", quantum[-3:])
    print("RISC-V 汇编:")
    print(asm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
