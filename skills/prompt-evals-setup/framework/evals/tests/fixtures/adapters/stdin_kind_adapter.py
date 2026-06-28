"""Offline adapter fixture that reports the *kind* of its stdin fd (fd 0).

The framework decides how it feeds an adapter its payload. ``subprocess.run(input=...)``
gives the child a PIPE on fd 0; feeding it from a real temp file gives a REGULAR FILE.
Some project adapters read fd 0 synchronously (e.g. Node ``readFileSync(0)``), which
fails with ``EAGAIN`` on a large pipe payload but never on a regular file. This fixture
consumes the payload like a real adapter, then prints which fd kind it received so a
test can assert the framework hands adapters a regular-file stdin.
"""

import json
import os
import stat
import sys

json.load(sys.stdin)  # consume the payload exactly like a real adapter
mode = os.fstat(0).st_mode
if stat.S_ISFIFO(mode):
    kind = "fifo"
elif stat.S_ISREG(mode):
    kind = "regular"
else:
    kind = "other"
sys.stdout.write(kind)
