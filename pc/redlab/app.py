"""Compatibility shim for the old REDLAB entrypoint.

REDLAB is no longer a separate application: the offensive tooling sits in the
ENGAGE and OPERATE sections of the single SENTINEL rail, in sentinel_ui.py.
This module forwards to it so anything importing `redlab.app.main` still gets
the unified window rather than a second shell.

The REDLAB panels themselves live alongside this file and are still built by
sentinel_ui.SentinelWindow.
"""

from sentinel_ui import main

__all__ = ["main"]

if __name__ == "__main__":
    import sys

    sys.exit(main())