"""Canopy terminal workspace. All inference routes through Mubit."""

import os

if os.environ.get("CANOPY_APP") == "policy":
    from canopy_app.canopy import main
else:
    from canopy_runtime import main

if __name__ == "__main__":
    main()
