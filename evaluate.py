"""Backwards-compatible fixed-case evaluation entry point."""

from canopy_app.evaluate import main


if __name__ == "__main__":
    raise SystemExit(main())
