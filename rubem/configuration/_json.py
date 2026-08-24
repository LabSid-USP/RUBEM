"""JSON reading that notices duplicate keys instead of silently keeping the last one."""

import json
import logging
from pathlib import Path

from .._paths import PathInput, as_path

logger = logging.getLogger(__name__)


class DuplicateKeyWarning:
    """Collects the duplicate keys seen while parsing, as ``"section.key"`` paths."""

    def __init__(self) -> None:
        self.duplicates: list[str] = []

    def hook(self, pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                self.duplicates.append(key)
            seen[key] = value
        return seen


def read_json(path: PathInput, *, on_duplicate=None) -> dict:
    """Read a JSON document, reporting duplicate object keys.

    Python's ``json`` keeps the last value of a duplicated key silently; the
    legacy configuration files in circulation carry duplicated sections, so the
    duplicates are logged (or handed to ``on_duplicate``) and the last value
    still wins, as before.

    :param path: The JSON file.
    :param on_duplicate: Optional callable receiving the list of duplicated keys.
    :raises FileNotFoundError: If the file does not exist.
    :raises json.JSONDecodeError: If the document is not valid JSON.
    """
    file = as_path(path)
    if not file.is_file():
        raise FileNotFoundError(f"Config file not found: {file}")
    collector = DuplicateKeyWarning()
    with Path(file).open(encoding="utf-8") as handle:
        data = json.load(handle, object_pairs_hook=collector.hook)
    if collector.duplicates:
        if on_duplicate is not None:
            on_duplicate(collector.duplicates)
        else:
            logger.warning(
                "Duplicated key(s) in %s: %s; the last value of each wins.",
                file,
                sorted(set(collector.duplicates)),
            )
    return data
