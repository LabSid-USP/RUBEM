"""Migration of legacy configuration files to format 1.0."""

import json
import logging
import os
import tempfile
from pathlib import Path

from .._paths import PathInput, as_path
from ._json import read_json
from .model_configuration_file import ModelConfigurationFile
from .model_configuration_file_v1 import ModelConfigurationFileV1

logger = logging.getLogger(__name__)


def migrate_legacy_file(
    source: PathInput,
    destination: PathInput | None = None,
    *,
    force: bool = False,
    metadata: dict | None = None,
) -> Path:
    """Write the format 1.0 equivalent of a legacy configuration file.

    Relative paths of the legacy file are anchored on its directory and
    rebased onto the directory of the destination, so the migrated file keeps
    pointing at the same data wherever it is written. The file is written
    atomically (temporary file plus rename) and an existing destination is not
    overwritten unless ``force`` is set.

    :param source: The legacy JSON file.
    :param destination: The 1.0 file to write; defaults to ``<source stem>-v1.json``
        next to the source.
    :param force: Overwrite an existing destination.
    :param metadata: Optional ``metadata`` section for the migrated file.
    :return: The path written.
    :raises FileExistsError: If the destination exists and ``force`` is false.
    """
    source_path = as_path(source).absolute()
    target = (
        as_path(destination).absolute()
        if destination is not None
        else source_path.with_name(f"{source_path.stem}-v1.json")
    )
    if target.exists() and not force:
        raise FileExistsError(f"{target} already exists; pass --force to overwrite it.")

    duplicates: list[str] = []
    data = read_json(source_path, on_duplicate=duplicates.extend)
    if duplicates:
        logger.warning(
            "Duplicated key(s) %s in %s; the last value of each was kept.",
            sorted(set(duplicates)),
            source_path,
        )
    legacy = ModelConfigurationFile.model_validate(data).resolve_paths(source_path.parent)
    migrated = ModelConfigurationFileV1.from_legacy(legacy, metadata)
    document = _rebase_paths(migrated.to_dict(), target.parent)

    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(document, file, indent=2)
            file.write("\n")
        Path(temporary).replace(target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return target


def _rebase_paths(document: dict, base: Path) -> dict:
    """Express the absolute paths of ``document`` relative to ``base`` when possible."""

    def rebase(value):
        if not value:
            return value
        path = Path(value)
        if not path.is_absolute():
            return value
        try:
            return os.path.relpath(path, base)
        except ValueError:  # Different drives on Windows: keep the absolute path.
            return value

    document["rasters"] = {k: rebase(v) for k, v in document["rasters"].items()}
    document["lookup_tables"] = {k: rebase(v) for k, v in document["lookup_tables"].items()}
    document["model_simulation_output"]["dir_path"] = rebase(
        document["model_simulation_output"]["dir_path"]
    )
    for spec in document["raster_series"].values():
        if isinstance(spec, list):
            for entry in spec:
                entry["file_path"] = rebase(entry["file_path"])
        elif "monthly" in spec:
            for entry in spec["monthly"]:
                entry["file_path"] = rebase(entry["file_path"])
            if spec.get("yearly_file_path"):
                spec["yearly_file_path"] = rebase(spec["yearly_file_path"])
        else:
            spec["dir_path"] = rebase(spec["dir_path"])
    return document
