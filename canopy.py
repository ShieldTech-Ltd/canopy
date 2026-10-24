"""Canopy entry point. Hosted deployments opt into the isolated production API."""

import os
from urllib.parse import urlparse

runtime = os.getenv("CANOPY_RUNTIME", "legacy")
if runtime == "production":
    from canopy_app.production import create_app, main
    app = create_app()
elif runtime == "legacy":
    origin = urlparse(os.getenv("CANOPY_PUBLIC_ORIGIN", "http://127.0.0.1:8080"))
    if origin.hostname not in {"localhost", "127.0.0.1"} and os.getenv(
        "CANOPY_LEGACY_PILOT") != "1":
        raise RuntimeError("Public legacy mode requires explicit CANOPY_LEGACY_PILOT=1")
    from canopy_app.canopy import app, main
else:
    raise RuntimeError("CANOPY_RUNTIME must be legacy or production")


if __name__ == "__main__":
    main()
