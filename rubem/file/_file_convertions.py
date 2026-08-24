import csv
import logging
import os

logger = logging.getLogger(__name__)


def _remove(file_path: str) -> None:
    """Remove ``file_path`` if it exists, logging instead of raising on failure."""
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
    except OSError as e:
        logger.error("Error while deleting file %s. %s", file_path, e)


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
    the files passed in are read; nothing else in their directories is.

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
            tmp_file_path = f"{dst_file_path}.tmp"

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

            with open(file=tmp_file_path, mode="w", encoding="utf8", newline="") as csvfile:
                writer = csv.writer(csvfile, delimiter=";")
                writer.writerow(header)
                writer.writerows(data)
            pending.append((tmp_file_path, dst_file_path))

        for tmp_file_path, dst_file_path in pending:
            backup_file_path = f"{dst_file_path}.bak" if os.path.isfile(dst_file_path) else None
            if backup_file_path:
                os.replace(dst_file_path, backup_file_path)
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
