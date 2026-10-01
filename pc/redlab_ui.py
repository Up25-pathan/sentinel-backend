"""SENTINEL REDLAB — offensive operations console.

The offensive half of SENTINEL: reconnaissance, web inspection, privilege
escalation posture, wireless inventory, asset tracking, attack-path campaigns,
network scanning and exploitability assessment. Everything here runs locally on
this machine; no offensive action is performed by the server.

Everything REDLAB reports is measured. Where a check cannot run, the tool says
so rather than substituting a plausible value.

Run it with any of:

    python redlab_ui.py
    python -m redlab

This file previously launched CIC despite its name, which is why the offensive
tooling appeared to be missing: you ran redlab_ui.py and got the reporting app.
The CIC entrypoint is now cic_ui.py.
"""

import sys

from redlab.app import main

if __name__ == "__main__":
    sys.exit(main())