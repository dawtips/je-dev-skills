"""Offline command-adapter fixture: read a case from stdin, echo a derived output.

Mirrors the command-adapter contract — case JSON on stdin, output text on stdout —
without any network. Used by test_artifact_runner.py.
"""

import json
import sys

case = json.load(sys.stdin)
sys.stdout.write("adapter saw " + case["prompt_inputs"]["goal"])
