"""Transpiler package: unified middle layer producing native IR per platform."""

from transpiler.emitters import transpile_to_ir, SUPPORTED_TARGETS

__all__ = ["transpile_to_ir", "SUPPORTED_TARGETS"]
