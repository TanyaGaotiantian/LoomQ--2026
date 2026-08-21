"""Encoder/decoder for the custom quantum RISC-V extension.

Two opcode families, matching standard RV32I practice (different formats get
different opcodes):

* custom-0 (0x0B), R-type:  qinit h x z s sdg cx swap ccx
* custom-1 (0x2B), I-type:  meas rz ry

See `encoding_spec.md` for the full encoding table.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

OPCODE_R = 0b0001011  # custom-0
OPCODE_I = 0b0101011  # custom-1

# funct3 within opcode 0x0B (R-type)
F_QINIT = 0b000
F_H = 0b001
F_X = 0b010
F_Z = 0b011
F_S = 0b100
F_CX = 0b101
F_SWAP = 0b110
F_CCX = 0b111

# funct3 within opcode 0x2B (I-type)
F_MEAS = 0b000
F_RZ = 0b001
F_RY = 0b010

F7_SDG = 0b0000001  # funct7 selector within F_S

# mnemonic -> (format, opcode, funct3, funct7)
MNEMONICS = {
    "qinit": ("r", OPCODE_R, F_QINIT, 0),
    "h": ("r", OPCODE_R, F_H, 0),
    "x": ("r", OPCODE_R, F_X, 0),
    "z": ("r", OPCODE_R, F_Z, 0),
    "s": ("r", OPCODE_R, F_S, 0),
    "sdg": ("r", OPCODE_R, F_S, F7_SDG),
    "cx": ("rr", OPCODE_R, F_CX, 0),
    "swap": ("rr", OPCODE_R, F_SWAP, 0),
    "ccx": ("rrr", OPCODE_R, F_CCX, 0),
    "meas": ("rr", OPCODE_I, F_MEAS, 0),
    "rz": ("ri", OPCODE_I, F_RZ, 0),
    "ry": ("ri", OPCODE_I, F_RY, 0),
}


class QuantumAsmError(ValueError):
    pass


_REG_RE = re.compile(r"x(\d+)", re.IGNORECASE)


def _parse_reg(tok: str) -> int:
    m = _REG_RE.fullmatch(tok.strip())
    if not m:
        raise QuantumAsmError(f"期望寄存器 x0..x31，实际为 {tok!r}")
    idx = int(m.group(1))
    if idx > 31:
        raise QuantumAsmError(f"寄存器超出范围: x{idx}")
    return idx


def _scale_angle(angle: float) -> int:
    """Scale an angle to a signed 12-bit fixed-point field (1/1024 rad)."""
    scaled = int(round(angle * 1024))
    if scaled < -2048 or scaled > 2047:
        raise QuantumAsmError(f"角度超出 12 位定点范围: {angle}")
    return scaled & 0xFFF


def _unscale_angle(scaled: int) -> float:
    value = scaled if scaled < 0x800 else scaled - 0x1000
    return value / 1024.0


def encode(op: str, args: List[str]) -> int:
    if op not in MNEMONICS:
        raise QuantumAsmError(f"未知指令: {op}")
    kind, opcode, funct3, funct7 = MNEMONICS[op]
    base = opcode | (funct3 << 12)
    if kind == "r":
        rd = _parse_reg(args[0])
        return base | (funct7 << 25) | (rd << 7)
    if kind == "rr":
        rs1, rd = _parse_reg(args[0]), _parse_reg(args[1])
        return base | (rs1 << 15) | (rd << 7)
    if kind == "rrr":
        rs1, rs2, rd = _parse_reg(args[0]), _parse_reg(args[1]), _parse_reg(args[2])
        return base | (rs2 << 20) | (rs1 << 15) | (rd << 7)
    if kind == "ri":
        rd = _parse_reg(args[0])
        imm = _scale_angle(float(args[1]))
        return base | (imm << 20) | (rd << 7)
    raise QuantumAsmError(f"未知指令格式: {op}")


def assemble(text: str) -> List[int]:
    """Assemble quantum-extension assembly text into 32-bit words."""
    words: List[int] = []
    labels: Dict[str, int] = {}
    lines: List[Tuple[int, str, List[str]]] = []
    pc = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if ";" in line:
            line = line.split(";")[0].strip()
        if ":" in line:
            label, _, rest = line.partition(":")
            labels[label.strip()] = pc
            line = rest.strip()
            if not line:
                continue
        parts = line.replace(",", " ").split()
        if not parts:
            continue
        lines.append((pc, parts[0].lower(), parts[1:]))
        pc += 1
    for _pc, op, args in lines:
        words.append(encode(op, args))
    return words


def disassemble(words: List[int]) -> List[str]:
    out = []
    for w in words:
        opcode = w & 0x7F
        funct3 = (w >> 12) & 0x7
        rd = (w >> 7) & 0x1F
        rs1 = (w >> 15) & 0x1F
        rs2 = (w >> 20) & 0x1F
        imm = (w >> 20) & 0xFFF
        if opcode == OPCODE_R:
            funct7 = (w >> 25) & 0x7F
            if funct3 == F_QINIT:
                out.append(f"qinit x{rd}")
            elif funct3 == F_H:
                out.append(f"h x{rd}")
            elif funct3 == F_X:
                out.append(f"x x{rd}")
            elif funct3 == F_Z:
                out.append(f"z x{rd}")
            elif funct3 == F_S:
                out.append(f"sdg x{rd}" if funct7 == F7_SDG else f"s x{rd}")
            elif funct3 == F_CX:
                out.append(f"cx x{rs1}, x{rd}")
            elif funct3 == F_SWAP:
                out.append(f"swap x{rs1}, x{rd}")
            elif funct3 == F_CCX:
                out.append(f"ccx x{rs1}, x{rs2}, x{rd}")
            else:
                out.append(f".word 0x{w:08x}")
        elif opcode == OPCODE_I:
            if funct3 == F_MEAS:
                out.append(f"meas x{rs1}, x{rd}")
            elif funct3 == F_RZ:
                out.append(f"rz x{rd}, {_unscale_angle(imm)}")
            elif funct3 == F_RY:
                out.append(f"ry x{rd}, {_unscale_angle(imm)}")
            else:
                out.append(f".word 0x{w:08x}")
        else:
            out.append(f".word 0x{w:08x}")
    return out
