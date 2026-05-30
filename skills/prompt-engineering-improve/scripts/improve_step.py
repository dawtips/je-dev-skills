"""Deterministic loop logic for prompt-engineering-improve.

Reads a round's evals/runs/<label>/output.json + a loop-state JSON and emits the
per-round delta, the running best version id (argmax), a continue|stop verdict, a
diagnosis tally, and an EXTRA_CRITERIA freeze-guard. NO model calls; NO float math,
argmax, tally, freeze-check, or serialization is done by the SKILL prose - only here.

CLI:
    python3 improve_step.py --output-json <path> --loop-state <path> \
        [--delta-out <path>] [--check-freeze]

Exit codes: 0 = continue; 1 = stop (a stopping rule fired); 2 = bad input /
freeze violation. Mirrors workflow-design-validate/scripts/validate_blueprint.py.
"""
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict


PASS_THRESHOLD = 7  # mirrors config.PASS_THRESHOLD; mandatory-fail per grading.md is score <= 3.
MANDATORY_FAIL_MAX = 3
