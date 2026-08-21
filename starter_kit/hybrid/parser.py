"""Hybrid-QASM parsing: OpenQASM 2.0 extended with a `classical { ... }` block.

The classical block grammar (from the contest rules):

    statement  := assignment ';' | if_stmt
    if_stmt    := 'if' '(' condition ')' '{' stmt* '}' [ 'else' '{' stmt* '}' ]
    condition  := expr ( '==' | '!=' ) expr
    expr       := term ( ( '+' | '-' ) term )*
    term       := integer | register
    register   := 'r' [1-9] | 'c' '[' digit+ ']'

Registers r1..r9 map to RISC-V x1..x9; measurement bit c[k] maps to x10+k.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


class HybridSyntaxError(ValueError):
    pass


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------


@dataclass
class Assign:
    target: int  # r1..r9 -> 1..9
    expr: "Expr"
    line: int = 0


@dataclass
class IfStmt:
    op: str  # '==' or '!='
    left: "Expr"
    right: "Expr"
    then_body: List[object] = field(default_factory=list)
    else_body: List[object] = field(default_factory=list)
    line: int = 0


@dataclass
class Lit:
    value: int


@dataclass
class RegRef:
    reg: int  # 1..9 for rN, 10+ for c[k]


@dataclass
class BinOp:
    op: str  # '+' | '-'
    left: "Expr"
    right: "Expr"


Expr = Union[Lit, RegRef, BinOp]


# ---------------------------------------------------------------------------
# tokenizer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<num>\d+)
  | (?P<word>if|else)
  | (?P<reg>r[1-9])
  | (?P<cbit>c\[\d+\])
  | (?P<eq>==)
  | (?P<ne>!=)
  | (?P<sym>[{}();,+\-=\[\]])
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    kind: str
    value: str
    line: int


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    line = 1
    for raw in text.splitlines():
        line_text = raw
        # strip line comments
        if "//" in line_text:
            line_text = line_text.split("//", 1)[0]
        pos = 0
        while pos < len(line_text):
            ch = line_text[pos]
            if ch.isspace():
                pos += 1
                continue
            m = _TOKEN_RE.match(line_text, pos)
            if not m:
                raise HybridSyntaxError(f"classical 块第 {line} 行出现无法解析的字符: {ch!r}")
            kind = m.lastgroup
            value = m.group()
            tokens.append(Token(kind, value, line))
            pos = m.end()
        line += 1
    tokens.append(Token("eof", "", line))
    return tokens


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


class ClassicalParser:
    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def next(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind: str, value: Optional[str] = None) -> Token:
        tok = self.next()
        if tok.kind != kind or (value is not None and tok.value != value):
            raise HybridSyntaxError(
                f"classical 块第 {tok.line} 行：期望 {value or kind}，实际为 {tok.value!r}"
            )
        return tok

    def parse_program(self) -> List[object]:
        stmts = self.parse_block_body()
        if self.peek().kind != "eof":
            raise HybridSyntaxError(
                f"classical 块第 {self.peek().line} 行：多余的 token {self.peek().value!r}"
            )
        return stmts

    def parse_block_body(self) -> List[object]:
        stmts: List[object] = []
        while self.peek().kind != "eof" and self.peek().value != "}":
            stmts.append(self.parse_statement())
        return stmts

    def parse_statement(self) -> object:
        tok = self.peek()
        if tok.kind == "reg":
            return self.parse_assignment()
        if tok.kind == "word" and tok.value == "if":
            return self.parse_if()
        raise HybridSyntaxError(
            f"classical 块第 {tok.line} 行：意外的语句开头 {tok.value!r}"
        )

    def parse_assignment(self) -> Assign:
        target_tok = self.expect("reg")
        target = int(target_tok.value[1:])
        self.expect("sym", "=")
        expr = self.parse_expr()
        self.expect("sym", ";")
        return Assign(target=target, expr=expr, line=target_tok.line)

    def parse_if(self) -> IfStmt:
        if_tok = self.expect("word", "if")
        self.expect("sym", "(")
        left = self.parse_expr()
        op_tok = self.next()
        if op_tok.kind not in ("eq", "ne"):
            raise HybridSyntaxError(
                f"classical 块第 {op_tok.line} 行：条件运算符必须为 == 或 !="
            )
        right = self.parse_expr()
        self.expect("sym", ")")
        then_body = self.parse_braced_block()
        else_body: List[object] = []
        if self.peek().kind == "word" and self.peek().value == "else":
            self.next()
            else_body = self.parse_braced_block()
        return IfStmt(
            op=op_tok.value, left=left, right=right,
            then_body=then_body, else_body=else_body, line=if_tok.line,
        )

    def parse_braced_block(self) -> List[object]:
        self.expect("sym", "{")
        body: List[object] = []
        while True:
            tok = self.peek()
            if tok.kind == "eof":
                raise HybridSyntaxError("classical 块：缺少右花括号 }")
            if tok.kind == "sym" and tok.value == "}":
                self.next()
                break
            body.append(self.parse_statement())
        return body

    # expressions: expr := term (('+'|'-') term)*
    def parse_expr(self) -> Expr:
        left = self.parse_term()
        while True:
            tok = self.peek()
            if tok.kind == "sym" and tok.value in ("+", "-"):
                self.next()
                right = self.parse_term()
                left = BinOp(op=tok.value, left=left, right=right)
            else:
                break
        return left

    def parse_term(self) -> Expr:
        tok = self.next()
        if tok.kind == "num":
            return Lit(value=int(tok.value))
        if tok.kind == "reg":
            return RegRef(reg=int(tok.value[1:]))
        if tok.kind == "cbit":
            idx = int(tok.value[2:-1])
            return RegRef(reg=10 + idx)
        if tok.kind == "sym" and tok.value == "(":
            expr = self.parse_expr()
            self.expect("sym", ")")
            return expr
        if tok.kind == "sym" and tok.value in ("+", "-"):
            # unary sign on a literal, e.g. (-5 + r1)
            nxt = self.peek()
            if nxt.kind == "num":
                self.next()
                val = int(nxt.value)
                return Lit(value=-val if tok.value == "-" else val)
        raise HybridSyntaxError(
            f"classical 块第 {tok.line} 行：期望数字或寄存器，实际为 {tok.value!r}"
        )


def parse_classical_block(text: str) -> List[object]:
    """Parse the body of a `classical { ... }` block into an AST."""
    return ClassicalParser(text).parse_program()


# ---------------------------------------------------------------------------
# hybrid source splitting: quantum ops + classical block
# ---------------------------------------------------------------------------


def split_hybrid(source: str) -> Tuple[List[str], Optional[str]]:
    """Split Hybrid-QASM into (quantum_op_lines, classical_block_text).

    quantum_op_lines keeps every OpenQASM statement in order (gates, measures,
    declarations); classical_block_text is the raw body of the `classical {}`
    block (or None when absent).
    """
    if not isinstance(source, str):
        raise HybridSyntaxError("input must be text")
    m = re.search(r"\bclassical\b", source)
    if not m:
        quantum = [
            ln.strip()
            for ln in source.splitlines()
            if ln.strip() and not ln.strip().startswith("//")
        ]
        return quantum, None

    open_brace = source.find("{", m.start())
    if open_brace == -1:
        raise HybridSyntaxError("classical 块缺少 {")
    depth = 1
    pos = open_brace + 1
    while pos < len(source) and depth > 0:
        ch = source[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        pos += 1
    if depth != 0:
        raise HybridSyntaxError("classical 块缺少 }")

    classical_body = source[open_brace + 1 : pos - 1]
    quantum_text = source[: m.start()] + source[pos:]
    quantum = [
        ln.strip()
        for ln in quantum_text.splitlines()
        if ln.strip() and not ln.strip().startswith("//")
    ]
    return quantum, (classical_body.strip() or None)
