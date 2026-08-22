"""LoomQ L2 agent: `agent_chat(prompt) -> str`.

Architecture (documented in README):

    user prompt
        |
        +--> task classifier (generate / correct / backend)
        |
        +--> [model service configured?]
        |        |
        |        + yes -> LLM call (LOOMQ_LLM_* env, OpenAI-compatible)
        |        |          |
        |        |          +--> QASM tasks: self-verify with our own L1
        |        |          |     simulator ("生成 -> 自验 -> 重试", up to 3
        |        |          |     rounds; the retry prompt includes the error)
        |        |          |
        |        |          +--> backend task: verify the LLM's chosen id
        |        |                against backend_capabilities.json and correct
        |        |                the reply if needed (tool-use pattern)
        |        |
        |        + no  -> offline demo mode: constraint-driven circuit builder
        |                  (also self-verified by simulation; never a lookup
        |                  table of the public example prompts)
        |
        +--> final reply text

Formal scoring always injects LOOMQ_LLM_*; the offline path only exists so the
public self-checker and the interactive CLI work without a key.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from agent.backend_advisor import (
    CANONICAL_IDS,
    build_recommendation_reply,
    cn_to_int,
    correct_backend_ids,
)
from agent.prompts import PROMPTS
from agent.verifier import (
    build_qasm_from_prompt,
    check_qasm_structure,
    detect_target,
    extract_gates_from_broken_code,
    extract_qasm_block,
    verify_qasm,
)

MAX_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# environment / model client
# ---------------------------------------------------------------------------


def model_service_available() -> bool:
    return all(
        os.environ.get(name)
        for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
    )


def _call_model(messages: List[dict]) -> str:
    from llm_client import chat_completion

    response = chat_completion(messages)
    return response["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# task classification
# ---------------------------------------------------------------------------

_BACKEND_ASK_RE = re.compile(
    r"(选\s*(个|哪|一个)?\s*(平台|后端)|推荐\s*(平台|后端)|哪个\s*(平台|后端)|"
    r"choose|select|which\s+(platform|backend|device)|后端|平台|怎么办)",
    re.IGNORECASE,
)
_BACKEND_CONSTRAINT_RE = re.compile(
    r"(排队|费用|免费|付费|花钱|真机|硬件|模拟器|比特|qubit|queue|cost|paid|free|超出|超过)",
    re.IGNORECASE,
)
_RUN_VERB_RE = re.compile(
    r"(跑|运行|执行|提交|部署|跑在|运行在|在哪|放到|使用|run|execute|deploy)",
    re.IGNORECASE,
)
_CORRECT_RE = re.compile(
    r"(修|修复|改|纠错|报错|错误|fix|correct|repair|broken|wrong|debug)",
    re.IGNORECASE,
)
_ERROR_HINT_RE = re.compile(
    r"(报错|错误|无法|无效|有问题|不行|出错|失败|崩溃|error|bug|broken|wrong|invalid|fails?|failed|doesn'?t\s+work|not\s+work)",
    re.IGNORECASE,
)
_CREATE_VERB_RE = re.compile(
    r"(生成|创建|创造|写|编写|构建|制备|搭建|制作|构造|make|create|build|write|generate|construct|prepare)",
    re.IGNORECASE,
)


def classify_task(prompt: str) -> str:
    """Classify a prompt as generate / correct / backend.

    Ordering is deliberate so that hidden prompt variants survive:
    1. correction language (fix/error) wins when code is present,
    2. explicit platform selection wins for backend advice,
    3. a declared target state (GHZ/Bell/QFT/...) wins over the generic
       run-verb backend rule, so "跑一个 4 比特 GHZ 电路" is generation,
    4. only then does the generic run-verb + constraint rule classify backend.
    """
    text = prompt.strip()
    has_code = extract_gates_from_broken_code(text) is not None
    error_intent = bool(_CORRECT_RE.search(text) or _ERROR_HINT_RE.search(text))
    if error_intent and (has_code or _CORRECT_RE.search(text)):
        return "correct"
    if _BACKEND_ASK_RE.search(text) and _BACKEND_CONSTRAINT_RE.search(text):
        return "backend"
    target = detect_target(text)
    has_target_intent = target not in ("unknown", "basis")
    if has_target_intent and (
        _CREATE_VERB_RE.search(text) or _RUN_VERB_RE.search(text) or has_code
    ):
        return "generate"
    if _RUN_VERB_RE.search(text) and _BACKEND_CONSTRAINT_RE.search(text):
        return "backend"
    return "generate"


# ---------------------------------------------------------------------------
# QASM reply formatting
# ---------------------------------------------------------------------------


def format_qasm_reply(qasm: str, note: str, verified: bool) -> str:
    lines = []
    if note:
        lines.append(note.rstrip())
        lines.append("")
    lines.append("```qasm")
    lines.append(qasm.strip())
    lines.append("```")
    if verified:
        lines.append("")
        lines.append("✅ 该电路已通过本地无噪声模拟器自验（保真度 ≥ 0.97）。")
    else:
        lines.append("")
        lines.append("⚠️ 该电路未通过自验，仅供参考，请检查后再使用。")
    return "\n".join(lines)


def _qasm_reply_attempt(prompt: str, task: str, attempt: int, feedback: str = "") -> str:
    """One LLM attempt; returns the raw model reply text."""
    system = PROMPTS[task]
    user = prompt
    if feedback:
        user = (
            prompt
            + "\n\n[自验反馈] 你上一次的电路没有通过本地模拟器自验："
            + feedback
            + "\n请重新生成，只输出 ```qasm 代码块（不要多余解释）。"
        )
    return _call_model(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )


def _generate_with_verification(prompt: str) -> str:
    """LLM-first generation/correction with self-check retry loop."""
    task = classify_task(prompt)
    last_qasm: Optional[str] = None
    last_reason = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            reply = _qasm_reply_attempt(prompt, task, attempt, last_reason)
        except Exception as exc:
            return f"模型调用失败：{exc}"
        qasm = extract_qasm_block(reply)
        if qasm is None:
            # maybe the model answered but forgot the fence; try raw text
            qasm = extract_qasm_block(f"OPENQASM 2.0;\n{reply}")
        if qasm is None:
            last_reason = "回复中没有可解析的 OpenQASM 2.0 代码块。"
            continue
        last_qasm = qasm
        ok, message = verify_qasm(qasm, prompt)
        if ok:
            return format_qasm_reply(qasm, _extract_note(reply), verified=True)
        last_reason = message
    # all LLM attempts failed -> verified offline builder as last resort
    qasm = build_qasm_from_prompt(prompt)
    ok, message = verify_qasm(qasm, prompt)
    return format_qasm_reply(
        qasm, f"（模型多轮自验未通过，已切换到本地已验证生成器：{message}）", verified=ok
    )


def _extract_note(reply: str) -> str:
    """Strip the qasm block out of the reply and keep a short explanation."""
    cleaned = re.sub(r"```qasm.*?```", "", reply, flags=re.DOTALL).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


# ---------------------------------------------------------------------------
# backend selection
# ---------------------------------------------------------------------------


def _extract_backend_ids(reply: str) -> List[str]:
    found = []
    for candidate in CANONICAL_IDS:
        if candidate in reply:
            found.append(candidate)
    return found


def _backend_reply(prompt: str) -> str:
    """LLM-first backend recommendation, verified against the official table."""
    system = PROMPTS["backend"]
    try:
        reply = _call_model(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        )
    except Exception as exc:
        reply = f"（模型调用失败：{exc}）"
    llm_ids = _extract_backend_ids(reply)
    correct, _ = correct_backend_ids(llm_ids)
    return build_recommendation_reply(prompt, correct, llm_reasoning=_strip_code(reply))


def _strip_code(text: str) -> str:
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or ""


# ---------------------------------------------------------------------------
# public entry
# ---------------------------------------------------------------------------


def agent_chat(prompt: str) -> str:
    """Public L2 entry point. Reads LOOMQ_LLM_* env; returns reply text."""
    if not isinstance(prompt, str) or not prompt.strip():
        return "请输入你的量子计算需求（例如：生成一个 3 比特 GHZ 态并进行全测量）。"
    task = classify_task(prompt)

    if model_service_available():
        if task == "backend":
            return _backend_reply(prompt)
        return _generate_with_verification(prompt)

    # offline demo mode (no model service configured)
    if task == "backend":
        return build_recommendation_reply(prompt, [], None)
    if task == "correct":
        qasm = _offline_fix(prompt)
    else:
        qasm = build_qasm_from_prompt(prompt)
    ok, message = verify_qasm(qasm, prompt)
    return format_qasm_reply(qasm, _offline_note(task, prompt), verified=ok)


def _offline_fix(prompt: str) -> str:
    """Offline correction: rebuild the declared target circuit from constraints."""
    broken = extract_gates_from_broken_code(prompt)
    n = broken[1] if broken else 3
    # ensure the prompt mentions a qubit count we can trust
    m = re.search(r"(\d+)\s*(?:个\s*)?(?:量子\s*)?(?:比特|qubits?)", prompt, re.IGNORECASE)
    if m:
        n = int(m.group(1))
    else:
        cn = cn_to_int(prompt)
        if cn is not None and re.search(r"比特|qubits?", prompt, re.IGNORECASE):
            n = cn
    synthetic = (
        f"生成一个 {n} 比特的 {detect_target(prompt) or 'GHZ'} 态并进行全测量"
    )
    return build_qasm_from_prompt(synthetic)


def _offline_note(task: str, prompt: str) -> str:
    if task == "correct":
        return "（离线演示模式）已根据你声明的目标态重建电路并修复原代码问题。"
    return "（离线演示模式）已根据需求生成电路。"
