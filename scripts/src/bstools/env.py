"""Shared CLI helper for reading required environment variables, so every
script reports missing config the same way instead of hand-rolling it.
"""

from __future__ import annotations

import os
import sys


def require_env(*names: str) -> dict[str, str]:
    """Returns {name: value} for every name in `names`, read from the
    environment -- or prints an error listing whichever ones are unset and
    exits(1).
    """
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        print(f"ERROR: Missing environment variable(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return {n: os.environ[n] for n in names}


def require_env_var(name: str) -> str:
    return require_env(name)[name]
