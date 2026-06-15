"""Offline render-only adapter fixture: read a case from stdin, print an assembled
PROMPT (model input, NOT an answer) on stdout. Mirrors the render_command contract."""

import json
import sys

case = json.load(sys.stdin)
sys.stdout.write("PROMPT for " + case["prompt_inputs"]["goal"])
