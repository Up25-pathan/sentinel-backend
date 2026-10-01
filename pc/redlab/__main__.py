"""`python -m redlab` now opens the same single SENTINEL window.

The offensive tooling is no longer a separate application, so this forwards to
the unified entrypoint rather than maintaining a second shell.
"""

import sys

from sentinel_ui import main

if __name__ == "__main__":
    sys.exit(main())