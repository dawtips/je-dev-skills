"""Run a generated bash hook/step script in tests, cross-platform.

The scaffolded artifacts are bash scripts. On Windows they cannot be executed
directly (subprocess sees a non-PE file -> WinError 193), so invoke them through an
explicit bash interpreter. When no bash is on PATH (e.g. Windows without Git Bash),
skip the test rather than fail it.
"""

import shutil
import subprocess
import unittest

_BASH = shutil.which("bash")


def run_bash_script(script_path, **kwargs):
    """``subprocess.run`` the script via bash; ``SkipTest`` if bash is unavailable."""
    if _BASH is None:
        raise unittest.SkipTest("bash is not available to run generated shell scripts")
    return subprocess.run([_BASH, script_path], **kwargs)
