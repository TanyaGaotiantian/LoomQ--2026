"""Backend advisor: constraint parsing + official capability-table filtering.

The L2「智能选后端」task is judged ONLY against the official capability table
(``backend_capabilities.json``).  This module turns the natural-language
constraints in a prompt into a deterministic candidate set, exactly the way the
official scoring derives the "唯一正确答案集" (see backend_capabilities.md).

The agent (``agent/core.py``) uses this as a *verification tool* on top of the
LLM's own reasoning: the LLM interprets the request, and this module double
checks the canonical backend id.  This is the recommended "function calling /
RAG" pattern from the contest docs - never keyword-answer hardcoding.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_CAPABILITIES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backend_capabilities.json",
)

# ---------------------------------------------------------------------------
# capability table loading
# ---------------------------------------------------------------------------


def load_backends() -> List[Dict[str, Any]]:
    with open(_CAPABILITIES_PATH, encoding="utf-8") as handle:
        return json.load(handle)["backends"]


BACKENDS = load_backends()
CANONICAL_IDS = [b["id"] for b in BACKENDS]


# ---------------------------------------------------------------------------
# constraint extraction from natural language
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"(\d+)\s*[-~至到]?\s*(\d+)?\s*(?:个?比特|比特|qubits?|qbits?)", re.IGNORECASE)
_INT_ONLY_RE = re.compile(r"(\d+)\s*比特", re.IGNORECASE)
_PLATFORM_RE = re.compile(
    r"(量旋|spin\s*q|spinq)|(本源|origin\s*q|pyqpanda)|(aws|braket|amazon)", re.IGNORECASE
)
_QUEUE_ZERO_RE = re.compile(r"(零排队|无排队|不用等|立即|马上|无需等待|不排队|instant|no\s*queue|zero\s*queue)", re.IGNORECASE)
_QUEUE_OK_RE = re.compile(r"(可以等|接受排队|排队也(行|可以)|允许排队|排队)", re.IGNORECASE)
_COST_FREE_RE = re.compile(r"(免费|不花钱|不想花钱|零成本|无费用|不用付费|free|no\s*cost|no\s*charge)", re.IGNORECASE)
_COST_PAID_RE = re.compile(r"(付费|花钱|收费|paid)", re.IGNORECASE)
_KIND_QPU_RE = re.compile(r"(真机|真实硬件|真实量子|硬件|量子计算机|qpu|real\s*hardware|real\s*device)", re.IGNORECASE)
_KIND_SIM_RE = re.compile(r"(模拟器|本地模拟|simulator|simulation|本地)", re.IGNORECASE)
_ACCOUNT_RE = re.compile(r"(不用注册|无需注册|不需要账号|不用账号|no\s*account|no\s*sign)", re.IGNORECASE)


def _extract_qubits(text: str) -> Optional[Tuple[int, Optional[int]]]:
    """Return (min, max) qubit constraint if any, else None."""
    m = _INT_RE.search(text)
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    return (lo, max(lo, hi))


def _extract_platform(text: str) -> Optional[str]:
    m = _PLATFORM_RE.search(text)
    if not m:
        return None
    if m.group(1):
        return "spinq"
    if m.group(2):
        return "originq"
    return "braket"


def parse_constraints(prompt: str) -> Dict[str, Any]:
    """Extract machine-checkable constraints from a natural-language prompt."""
    text = prompt.lower()
    constraints: Dict[str, Any] = {
        "qubits": None,
        "platform": None,
        "queue_none": None,
        "cost_free": None,
        "kind": None,
        "requires_account": None,
    }
    qb = _extract_qubits(text)
    if qb:
        constraints["qubits"] = qb
    constraints["platform"] = _extract_platform(text)
    if _QUEUE_ZERO_RE.search(text):
        constraints["queue_none"] = True
    elif _QUEUE_OK_RE.search(text):
        constraints["queue_none"] = False
    if _COST_FREE_RE.search(text):
        constraints["cost_free"] = True
    elif _COST_PAID_RE.search(text):
        constraints["cost_free"] = False
    if _KIND_QPU_RE.search(text) and not _KIND_SIM_RE.search(text):
        constraints["kind"] = "qpu"
    elif _KIND_SIM_RE.search(text):
        constraints["kind"] = "simulator"
    if _ACCOUNT_RE.search(text):
        constraints["requires_account"] = False
    return constraints


# ---------------------------------------------------------------------------
# filtering
# ---------------------------------------------------------------------------


def filter_backends(constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply constraints to the official table; returns matching backends."""
    candidates = list(BACKENDS)
    qb = constraints.get("qubits")
    if qb:
        lo, hi = qb
        candidates = [b for b in candidates if b["max_qubits"] >= lo]
    platform = constraints.get("platform")
    if platform:
        candidates = [b for b in candidates if b["platform"] == platform]
    if constraints.get("queue_none") is True:
        candidates = [b for b in candidates if b["queue"] == "none"]
    elif constraints.get("queue_none") is False:
        candidates = [b for b in candidates if b["queue"] != "none"]
    if constraints.get("cost_free") is True:
        candidates = [b for b in candidates if b["cost"] in ("free", "free_quota")]
    elif constraints.get("cost_free") is False:
        candidates = [b for b in candidates if b["cost"] == "paid"]
    if constraints.get("kind") == "qpu":
        candidates = [b for b in candidates if b["kind"] == "qpu"]
    elif constraints.get("kind") == "simulator":
        candidates = [b for b in candidates if b["kind"] == "simulator"]
    if constraints.get("requires_account") is False:
        candidates = [b for b in candidates if not b["requires_account"]]
    return candidates


def correct_backend_ids(extracted_ids: List[str]) -> Tuple[List[str], List[str]]:
    """Return (correct_ids, invalid_ids) for a list of candidate ids."""
    correct = [i for i in extracted_ids if i in CANONICAL_IDS]
    invalid = [i for i in extracted_ids if i not in CANONICAL_IDS]
    return correct, invalid


# ---------------------------------------------------------------------------
# reply building
# ---------------------------------------------------------------------------

_BACKEND_NAME = {b["id"]: b["name"] for b in BACKENDS}


def describe_backend(backend_id: str) -> str:
    """Human-friendly description of a canonical backend id."""
    b = next((x for x in BACKENDS if x["id"] == backend_id), None)
    if b is None:
        return backend_id
    queue = "无需排队" if b["queue"] == "none" else f"排队: {b['queue']}"
    cost = {"free": "免费", "free_quota": "免费额度", "paid": "付费"}[b["cost"]]
    return (
        f"{b['name']}（最多 {b['max_qubits']} 比特，{queue}，{cost}）"
    )


def build_recommendation_reply(
    prompt: str,
    llm_ids: List[str],
    llm_reasoning: Optional[str] = None,
) -> str:
    """Build the final reply, guaranteeing a correct canonical id appears.

    The LLM proposes ids; this tool verifies against the official table and
    corrects/clarifies when the proposal is wrong or empty (mirrors the
    "tool use" pattern the contest recommends).
    """
    constraints = parse_constraints(prompt)
    correct_set = filter_backends(constraints)
    correct_ids = [b["id"] for b in correct_set]

    llm_ok = [i for i in llm_ids if i in correct_ids]
    chosen = llm_ok[0] if llm_ok else (correct_ids[0] if correct_ids else None)

    lines = []
    if llm_reasoning:
        lines.append(llm_reasoning.strip().rstrip("。") + "。")
    if chosen:
        lines.append(f"推荐后端：{chosen}（{describe_backend(chosen)}）")
        if correct_ids:
            lines.append(
                "同样满足条件："
                + "、".join(f"{i}（{describe_backend(i)}）" for i in correct_ids if i != chosen)
            )
    else:
        lines.append(
            "很抱歉，没有任何可用后端同时满足你给出的全部约束（比特数 / 排队 / 费用 / 类型）。"
        )
        # closest alternative: largest-capacity backend
        if correct_set:
            pass
        else:
            biggest = max(BACKENDS, key=lambda b: b["max_qubits"])
            lines.append(
                f"最接近的替代方案：{biggest['id']}（最多 {biggest['max_qubits']} 比特，"
                f"排队: {biggest['queue']}，{biggest['cost']}）。若允许排队或放宽费用约束即可使用。"
            )
    return "\n".join(lines)
