"""Central logging setup -- every CLI entry point (bstools.cli.*:main) calls
setup_logging() once, near the top of main(), instead of each module
hand-rolling its own print(..., file=sys.stderr) calls. After that, any
module just does `logger = logging.getLogger(__name__)` and logs normally;
level filtering (see setup_logging's `debug` param) replaces the old
one-off `if self.debug:` checks.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(*, debug: bool = False) -> None:
    """Root logger -> stderr only, no log file. INFO and up by default;
    DEBUG (e.g. raw API payloads dumped by LexwareClient.get()) when a
    --debug CLI flag asks for it.
    """
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,  # explicit, even though it's logging's own default
    )
