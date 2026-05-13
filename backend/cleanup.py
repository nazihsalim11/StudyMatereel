#!/usr/bin/env python3
"""
Remove job artefacts from temporary_storage/ that are older than MAX_AGE_HOURS.
Run manually or via cron: 0 * * * * python /path/to/cleanup.py
"""
import logging
import os
import shutil
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "temporary_storage")
MAX_AGE_HOURS = 24
# Top-level names that are never removed
PROTECTED = {"uploads", "videos", ".gitkeep"}


def cleanup(max_age_hours: int = MAX_AGE_HOURS) -> int:
    cutoff = time.time() - max_age_hours * 3600
    removed = 0

    for entry in os.scandir(TEMP_DIR):
        if entry.name in PROTECTED:
            continue
        if entry.stat(follow_symlinks=False).st_mtime < cutoff:
            try:
                if entry.is_dir():
                    shutil.rmtree(entry.path)
                else:
                    os.remove(entry.path)
                logger.info("Removed: %s", entry.path)
                removed += 1
            except OSError as exc:
                logger.warning("Could not remove %s: %s", entry.path, exc)

    logger.info("Cleanup complete — %d item(s) removed.", removed)
    return removed


if __name__ == "__main__":
    cleanup()
