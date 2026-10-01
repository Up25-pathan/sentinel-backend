"""SENTINEL — one application for intelligence and offensive operations.

Kept so the older launch command still opens the app. Everything lives in
sentinel_ui.py now; this file only forwards to it.

Run it with any of:

    python sentinel_ui.py
    python redlab_ui.py
    python cic_ui.py
"""

import sys

from sentinel_ui import main

if __name__ == "__main__":
    sys.exit(main())