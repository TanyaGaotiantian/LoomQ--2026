#!/usr/bin/env python3
"""LoomQ 交互式智能体 CLI —— 让零基础用户 5 分钟内跑通第一个量子程序。

功能：
  * 自然语言对话（复用 `agent_chat`，LLM 配置存在时走模型，否则离线演示模式）
  * 生成 QASM 后自动在三个后端运行并可视化 counts（ASCII 柱状图）
  * 新手引导：`--guide` 首次运行引导、内置帮助、错误恢复提示
  * 后端选型：给出规范后端标识与解释

用法：
    python3 cli.py                     # 交互式对话
    python3 cli.py --guide             # 先看 5 分钟新手引导
    python3 cli.py "生成一个 3 比特 GHZ 态"   # 单次提问
    python3 cli.py --shots 4096        # 设定运行采样数
"""

from __future__ import annotations

import argparse
import os
import re
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from agent.core import agent_chat, classify_task, model_service_available
from agent.verifier import extract_qasm_block
from backends.runner import run_on_backend

GUIDE = """\
┌──────────────────────────────────────────────────────────────┐
│  🧭 LoomQ 5 分钟新手引导（写给完全没接触过量子的人）            │
├──────────────────────────────────────────────────────────────┤
│  1. 量子比特（qubit）≈ 一枚"会同时正反旋转的硬币"。           │
│  2. 量子门（gate）≈ 操作这枚硬币的指令，比如 H 让它进入        │
│     50/50 叠加，CX 让两枚硬币"永远同面"（纠缠）。             │
│  3. 你不需要懂数学 —— 只需要用大白话告诉助手你想做什么。       │
│  4. 助手会生成 OpenQASM 2.0 电路，并自动在三家云平台后端      │
│     模拟运行，把结果画成直方图给你看。                        │
│                                                              │
│  试试输入：                                                   │
│    · "生成一个 3 比特 GHZ 态并进行全测量"                     │
│    · "帮我修复这段代码：H q[0]; CX q[0] q[1]"                 │
│    · "我需要运行一个 15 比特电路，且零排队等待，选哪个平台？"  │
│    · 输入 help 查看命令，输入 exit 退出                       │
└──────────────────────────────────────────────────────────────┘
"""


def visualize_counts(counts: dict, title: str = "") -> str:
    """ASCII 柱状图可视化测量结果（little-endian 位序）。"""
    if not counts:
        return "（无测量结果）"
    total = sum(counts.values())
    width = max(len(k) for k in counts)
    max_val = max(counts.values())
    bar_max = 24
    lines = []
    if title:
        lines.append(title)
    lines.append(f"总采样 {total} 次")
    for key in sorted(counts, key=lambda k: (-counts[k], k)):
        value = counts[key]
        pct = 100.0 * value / total
        bar = "█" * max(1, round(bar_max * value / max_val))
        lines.append(f"  |{key:>{width}}⟩ {bar} {value:6d} ({pct:5.1f}%)")
    return "\n".join(lines)


def run_circuit_for_user(qasm: str, shots: int) -> str:
    """在三个后端运行用户电路并输出可视化结果。"""
    circuit = extract_qasm_block(qasm) or qasm
    out = ["\n⚛️  正在三平台模拟运行（spinq / originq / braket）...\n"]
    for target in ("spinq", "originq", "braket"):
        try:
            result = run_on_backend(circuit, target, shots)
            out.append(f"【{result['backend']}】engine={result['meta']['engine']}")
            out.append(visualize_counts(result["counts"]))
            out.append("")
        except Exception as exc:
            out.append(f"【{target}】运行失败：{exc}\n")
    return "\n".join(out)


def single_shot(prompt: str, shots: int) -> int:
    reply = agent_chat(prompt)
    print(reply)
    qasm = extract_qasm_block(reply)
    if qasm:
        print(run_circuit_for_user(qasm, shots))
    return 0


def interactive(shots: int) -> int:
    print(GUIDE)
    print("提示：当前为%s模式。输入 help / exit。\n" % (
        "LLM 在线" if model_service_available() else "离线演示"
    ))
    while True:
        try:
            prompt = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not prompt:
            continue
        low = prompt.lower()
        if low in ("exit", "quit", "退出"):
            print("再见！")
            break
        if low in ("help", "帮助"):
            print(
                "命令：exit 退出 · guide 查看新手引导 · clear 清屏\n"
                "其他任意输入都会作为量子计算需求交给智能体。"
            )
            continue
        if low in ("guide", "引导"):
            print(GUIDE)
            continue
        if low == "clear":
            os.system("clear" if os.name == "posix" else "cls")
            continue
        try:
            reply = agent_chat(prompt)
            print(reply)
            qasm = extract_qasm_block(reply)
            if qasm:
                print(run_circuit_for_user(qasm, shots))
        except Exception as exc:
            print(f"⚠️  出错了，但别慌：{exc}\n你可以换个说法再试一次，或输入 help。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ 交互式智能体 CLI")
    parser.add_argument("prompt", nargs="?", help="单次提问（不填则进入交互模式）")
    parser.add_argument("--guide", action="store_true", help="显示新手引导后进入交互")
    parser.add_argument("--shots", type=int, default=8192, help="模拟采样次数")
    args = parser.parse_args()

    if args.prompt:
        return single_shot(args.prompt, args.shots)
    if args.guide:
        print(GUIDE)
    return interactive(args.shots)


if __name__ == "__main__":
    sys.exit(main())
