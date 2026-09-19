"""One call at program start sets up logging for the whole package.

LOG_LEVEL=INFO (default) shows what happened: which check, which verdict, how
long. LOG_LEVEL=DEBUG adds values, quotes and reasoning -- on real calls those
are personal data, so they stay out of INFO."""

import logging
import os


def setup_logging(level: str | None = None) -> None:
    level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(level=level, force=True,
                        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    # Third-party libraries are noisy at DEBUG; keep them quiet unless asked.
    for noisy in ("httpx", "httpcore", "openai", "strands", "botocore"):
        logging.getLogger(noisy).setLevel(logging.WARNING if level != "DEBUG" else logging.INFO)
