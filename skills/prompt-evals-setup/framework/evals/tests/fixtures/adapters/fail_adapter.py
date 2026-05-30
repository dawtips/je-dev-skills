"""Offline command-adapter fixture that fails (non-zero exit) for error-path tests."""

import sys

sys.stderr.write("adapter boom")
sys.exit(1)
