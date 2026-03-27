"""Background cleanup for generated notebook files (SEC-007)."""
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_SECONDS = 3600  # 1 hour


def cleanup_generated_files(
    directory: Path,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> int:
    """Delete .ipynb files older than max_age_seconds from the directory.

    Returns the number of files removed.
    """
    if not directory.exists():
        return 0

    now = time.time()
    removed = 0

    for file_path in directory.glob("*.ipynb"):
        try:
            age = now - file_path.stat().st_mtime
            if age > max_age_seconds:
                file_path.unlink()
                removed += 1
                logger.info("Cleaned up old notebook: %s (age: %.0fs)", file_path.name, age)
        except OSError as exc:
            logger.warning("Failed to clean up %s: %s", file_path.name, exc)

    if removed > 0:
        logger.info("Cleaned up %d expired notebook(s)", removed)

    return removed
