"""Shared CLI helper for reading required environment variables, so every
script reports missing config the same way instead of hand-rolling it.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)


def require_env(*names: str) -> dict[str, str]:
    """Returns {name: value} for every name in `names`, read from the
    environment -- or logs an error listing whichever ones are unset and
    exits(1).
    """
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        logger.error("Missing environment variable(s): %s", ", ".join(missing))
        sys.exit(1)
    return {n: os.environ[n] for n in names}


def require_env_var(name: str) -> str:
    return require_env(name)[name]
