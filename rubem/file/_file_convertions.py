import csv
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def _remove(file_path: str) -> None:
    """Remove ``file_path`` if it exists, logging instead of raising on failure.

    Existence is checked with ``os.path.lexists`` so that a symlink is removed
    as the entry it is, even when it points nowhere.
    """
    try:
        if os.path.lexists(file_path):
            os.remove(file_path)
    except OSError as e:
        logger.error("Error while deleting file %s. %s", file_path, e)


def _stage_path(dst_file_path: str, suffix: str) -> str:
    """Reserve a unique path next to ``dst_file_path`` and return it.

    Staging and backup names are allocated instead of derived from the
    destination, so a file the user keeps as ``<destination>.tmp`` or
    ``<destination>.bak`` is never overwritten by a conversion, nor deleted by
    its cleanup.
    """
    directory, name = os.path.split(dst_file_path)
    handle, path = tempfile.mkstemp(dir=directory or ".", prefix=f".{name}.", suffix=suffix)
    os.close(handle)
    return path


def _backup_destination(dst_file_path: str) -> str | None:
    """Move an existing destination aside and return its backup path.

    ``os.path.lexists`` is deliberate: a dangling symlink is invisible to
    ``os.path.isfile``, so it would be replaced without a backup and lost when
    the transaction rolled back.

    :raises IsADirectoryError: If the destination is a directory, which cannot
        be replaced by the converted file.
    """
    if not os.path.lexists(dst_file_path):
        return None
    if os.path.isdir(dst_file_path) and not os.path.islink(dst_file_path):
        raise IsADirectoryError(
            f"The destination {dst_file_path} is a directory and cannot be replaced."
        )
    backup_file_path = _stage_path(dst_file_path, ".bak")
    os.replace(dst_file_path, backup_file_path)
    return backup_file_path


def _undo_installs(installs: list[tuple[str, str | None]]) -> None:
    """Put the destinations back the way they were, in reverse installation order.

    A destination that had no previous file is removed; one that had is
    restored from its backup. Failures are logged rather than raised so that
    they never mask the error that triggered the rollback.

    :param installs: Pairs of destination path and backup path (``None`` when
        the destination did not exist before the conversion).
    :type installs: list[tuple[str, str | None]]
    """
    for dst_file_path, backup_file_path in reversed(installs):
        if backup_file_path is None:
            _remove(dst_file_path)
            continue
        try:
            os.replace(backup_file_path, dst_file_path)
        except OSError as e:
            logger.error("Error while restoring file %s. %s", dst_file_path, e)


def tss2csv(tss_files, cols_names: list[str], should_delete_src_tss: bool = True) -> None:
    """Convert the given PCRaster Time Series (``*.tss``) files to ``*.csv``.

    The conversion is transactional: every CSV is first written to a
    temporary name, the temporary files are renamed only after all of them
    were produced, any destination being overwritten is kept as a backup
    until every rename succeeded, and the sources are removed last. A failure
    therefore leaves the sources and the previous CSV files untouched. Only
    the files passed in are read; nothing else in their directories is, and
    the staging and backup names are allocated so that unrelated files next to
    a destination are never overwritten.

    :raises IsADirectoryError: If a destination path is an existing directory.

    :param tss_files: Paths of the ``.tss`` files to convert.
    :type tss_files: list

    :param cols_names: List of strings of aliases for the column names.
    :type cols_names: list[str]

    :param should_delete_src_tss: Remove the source files after conversion, defaults to ``True``.
    :type should_delete_src_tss: bool, optional
    """
    if not cols_names:
        raise ValueError("The list of column names is empty.")

    tss_files = [os.path.abspath(str(tss_file)) for tss_file in tss_files]
    for tss_file in tss_files:
        if not os.path.isfile(tss_file):
            raise FileNotFoundError(f"The time series file {tss_file} does not exist.")

    header = ["0"]
    header.extend(cols_names)

    pending: list[tuple[str, str]] = []
    installs: list[tuple[str, str | None]] = []
    try:
        for tss_file in tss_files:
            dst_file_path = f"{os.path.splitext(tss_file)[0]}.csv"

            with open(file=tss_file, mode="r", encoding="utf8") as f:
                lines = f.readlines()

            data = [line.split() for line in lines]
            if data and len(data[0]) != len(header):
                logger.error(
                    "Number of columns in the file %s is different from the number of column names.",
                    tss_file,
                )
                raise ValueError(
                    f"The number of columns in the file {tss_file} is different "
                    "from the number of column names."
                )

            tmp_file_path = _stage_path(dst_file_path, ".tmp")
            pending.append((tmp_file_path, dst_file_path))
            with open(file=tmp_file_path, mode="w", encoding="utf8", newline="") as csvfile:
                writer = csv.writer(csvfile, delimiter=";")
                writer.writerow(header)
                writer.writerows(data)

        for tmp_file_path, dst_file_path in pending:
            backup_file_path = _backup_destination(dst_file_path)
            # Recorded before the install so that a failure in it is undone too.
            installs.append((dst_file_path, backup_file_path))
            os.replace(tmp_file_path, dst_file_path)
    except Exception:
        _undo_installs(installs)
        for tmp_file_path, _ in pending:
            _remove(tmp_file_path)
        raise

    for _, backup_file_path in installs:
        if backup_file_path:
            _remove(backup_file_path)

    if should_delete_src_tss:
        for tss_file in tss_files:
            _remove(tss_file)
