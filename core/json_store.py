"""Shared safe helpers for JSON-backed application state."""
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def load_json(path, default, expected_type=dict):
    """Load JSON without modifying missing or malformed source files."""
    target = Path(path)
    try:
        with target.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if expected_type is not None and not isinstance(data, expected_type):
            raise ValueError(
                f"Expected {expected_type.__name__}, got {type(data).__name__}"
            )
        return data
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        logger.exception("Could not load JSON data from %s; preserving file", target)
        return default


def atomic_write_json(path, data, *, indent=None, ensure_ascii=False, default=None):
    """Atomically save JSON and retain the previous file as a .bak file."""
    target = Path(path)
    temporary = None
    backup_temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(target.parent),
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(
                data, handle, ensure_ascii=ensure_ascii, indent=indent,
                default=default,
            )
            handle.flush()
            os.fsync(handle.fileno())

        if target.exists():
            backup = target.with_name(target.name + ".bak")
            with tempfile.NamedTemporaryFile(
                "wb", dir=str(target.parent),
                prefix=f".{backup.name}.", suffix=".tmp", delete=False,
            ) as handle:
                backup_temporary = handle.name
            shutil.copy2(target, backup_temporary)
            with open(backup_temporary, "rb") as handle:
                os.fsync(handle.fileno())
            os.replace(backup_temporary, backup)
            backup_temporary = None

        os.replace(temporary, target)
        temporary = None
        return True
    except (OSError, TypeError, ValueError):
        logger.exception("Could not atomically save JSON data to %s", target)
        return False
    finally:
        for leftover in (temporary, backup_temporary):
            if leftover:
                try:
                    os.unlink(leftover)
                except OSError:
                    pass
