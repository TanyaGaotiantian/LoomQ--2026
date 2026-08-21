#!/usr/bin/env python3
"""Run the whole LoomQ unit test suite:  python3 tests/run_all.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

loader = unittest.TestLoader()
suite = loader.discover(os.path.dirname(os.path.abspath(__file__)), pattern="test_*.py")
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
