# core/logger.py

import logging
import os

logger = logging.getLogger("arch_install")
logger.setLevel(logging.INFO)

# Stream handler added immediately so output works before setup() is called
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(_stream_handler)


def setup(log_path):
    """Call once after config is loaded to add a file handler."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    file_handler = logging.FileHandler(log_path, mode="a")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    logger.addHandler(file_handler)
    logger.info(f"Logging to {log_path}")
