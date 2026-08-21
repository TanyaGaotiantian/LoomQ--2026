#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0 —— 队伍实现。

统一入口，把 L1/L2/L3 全部接到公开契约：

    transpile(qasm_str, target)      -> 目标平台原生 IR（spinq/originq/braket）
    run(qasm_str, target, shots)     -> 统一结果 Schema（SDK 优先，内置模拟器兜底）
    agent_chat(prompt)               -> L2 智能体回复（LOOMQ_LLM_* 环境变量驱动）
    compile_hybrid(hybrid_qasm_str)  -> (量子操作序列, RISC-V 汇编文本)
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Tuple

# 让本目录下的内部包（qasm/transpiler/backends/agent/hybrid）可被
# 包式导入（from starter_kit import adapter）与单文件导入（import adapter）共用。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from qasm.parser import parse_qasm  # noqa: E402
from transpiler.emitters import transpile_to_ir  # noqa: E402
from backends.runner import run_on_backend  # noqa: E402
from agent.core import agent_chat as _agent_chat  # noqa: E402
from hybrid.compiler import compile_hybrid as _compile_hybrid  # noqa: E402

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target {target!r}")
    return transpile_to_ir(qasm_str, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    return run_on_backend(qasm_str, target, shots)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return _agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    return _compile_hybrid(hybrid_qasm_str)
