import csv
import logging
import os
import stat
import uuid
from pathlib import Path

from .._paths import as_path

logger = logging.getLogger(__name__)

_STAGE_ATTEMPTS = 100


def _remove(file_path: str) -> bool:
    """Remove ``file_path`` if it exists, logging instead of raising on failure.

    Existence is checked with ``os.path.lexists`` so that a symlink is removed
    as the entry it is, even when it points nowhere.

    :return: ``True`` when the path is gone afterwards.
    :rtype: bool
    """
    try:
        path = Path(file_path)
        if path.is_symlink() or path.exists():
            path.unlink()
        return True
    except OSError as e:
        logger.error("Error while deleting file %s. %s", file_path, e)
        return False


def _reserve_stage(dst_file_path: str, suffix: str) -> tuple[int, str]:
    """Reserve a unique path next to ``dst_file_path`` and return ``(fd, path)``.

    Staging and backup names are allocated instead of derived from the
    destination, so a file the user keeps as ``<destination>.tmp`` or
    ``<destination>.bak`` is never overwritten by a conversion, nor deleted by
    its cleanup. The file is created like any other output, with ``0o666``
    left to the process umask: ``mkstemp`` would make it private to the owner,
    and reading the umask back to correct that would have to change it
    process-wide first, which races with everything else running.

    The descriptor is returned open so that the caller can write through the
    entry it created. Reopening the reserved name would give away that
    exclusivity: in a directory writable by someone else, the name can be
    replaced by a symlink between the two calls and the write would follow it.

    :raises OSError: If no free name is found next to the destination.
    """
    directory, name = os.path.split(dst_file_path)
    for _ in range(_STAGE_ATTEMPTS):
        path = str(Path(directory or ".") / f".{name}.{uuid.uuid4().hex[:8]}{suffix}")
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
        except FileExistsError:
            continue
        return handle, path
    raise OSError(f"Could not reserve a staging path next to {dst_file_path}.")


def _reserve_path(dst_file_path: str, suffix: str) -> str:
    """Reserve a unique path and close its descriptor, for a plain rename target."""
    handle, path = _reserve_stage(dst_file_path, suffix)
    os.close(handle)
    return path


def _apply_mode(handle: int, path: str, mode: int | None) -> None:
    """Give the open staging file *mode*, without going through its name.

    ``os.fchmod`` acts on the descriptor reserved with ``O_EXCL``, so the mode
    of the previous CSV cannot land on something else that took over the name
    in the meantime. Windows has no ``fchmod``; there the path is used, which
    is what the platform offers.
    """
    if mode is None:
        return
    if hasattr(os, "fchmod"):
        os.fchmod(handle, mode)
    else:  # pragma: no cover - exercised only on Windows
        Path(path).chmod(mode)


def _install_path(dst_file_path: str) -> str:
    """Return the path a destination writes to, with symlinks resolved.

    A symlinked destination is part of the layout the user chose, so the
    conversion updates what the link points at, as the previous in-place write
    did, instead of replacing the link with a regular file. A link that points
    nowhere yet has its target created, and in both cases the link itself is
    never moved, replaced or removed.
    """
    return os.path.realpath(dst_file_path)


def _destination_mode(dst_file_path: str) -> int | None:
    """Return the permissions of an existing destination, if any.

    A conversion installs a freshly created file, so the permissions the user
    gave the previous CSV would be replaced by whatever the umask allows; they
    are carried onto the staged file instead. A destination that does not
    exist yet has none to carry.
    """
    try:
        return stat.S_IMODE(Path(dst_file_path).stat().st_mode)
    except OSError:
        return None


def _backup_destination(dst_file_path: str) -> str | None:
    """Move an existing destination aside and return its backup path.

    The path handed in is the resolved destination, so what moves aside is the
    file itself and never a symlink pointing at it. ``os.path.lexists`` keeps
    the check honest for any entry ``os.path.isfile`` would report as absent.

    :raises IsADirectoryError: If the destination is a directory, which cannot
        be replaced by the converted file.
    """
    dst_path = Path(dst_file_path)
    if not (dst_path.is_symlink() or dst_path.exists()):
        return None
    if dst_path.is_dir():
        raise IsADirectoryError(
            f"The destination {dst_file_path} is a directory and cannot be replaced."
        )
    backup_file_path = _reserve_path(dst_file_path, ".bak")
    try:
        Path(dst_file_path).replace(backup_file_path)
    except OSError:
        # The reserved path is not recorded anywhere yet, so the rollback in
        # ``tss2csv`` cannot know about it: it is released here instead of
        # being left behind on every failed conversion.
        _remove(backup_file_path)
        raise
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
            Path(backup_file_path).replace(dst_file_path)
        except OSError as e:
            logger.error("Error while restoring file %s. %s", dst_file_path, e)


def _is_numeric(token: str) -> bool:
    """Whether ``token`` reads as a number, which a title line never does."""
    try:
        float(token)
    except ValueError:
        return False
    return True


def _split_header(lines: list[str], tss_file: str, cols_names: list[str]) -> list[str]:
    """Return the data rows of ``lines``, after checking the PCRaster header.

    The header the model writes is the one :class:`TimeoutputTimeseries`
    produces: a title line (``timeseries scalar``), the number of columns (the
    time step column included), a ``timestep`` line and one line per station
    id. The ids are checked against ``cols_names`` so that a file written for
    other stations is never converted under the wrong column names.

    :raises ValueError: If the file carries no header, or if its header does
        not describe the given column names.
    """
    stripped = [line.strip() for line in lines]
    headerless = (
        f"The time series file {tss_file} has no PCRaster header; the model writes "
        "headed time series files."
    )
    if not stripped or not stripped[0] or _is_numeric(stripped[0].split()[0]):
        logger.error("The time series file %s has no PCRaster header.", tss_file)
        raise ValueError(headerless)
    try:
        number_of_columns = int(stripped[1])
    except (IndexError, ValueError):
        logger.error("The time series file %s has no PCRaster header.", tss_file)
        raise ValueError(headerless) from None
    # A header always announces at least the time step column, so a count
    # below one is not a column count and the second line is not a header one.
    if number_of_columns < 1:
        logger.error("The time series file %s has no PCRaster header.", tss_file)
        raise ValueError(headerless)

    ids = stripped[3 : 3 + number_of_columns - 1]
    # A data row where an id line is expected means the header stops short of
    # the announced column count.
    if len(stripped) < 3 or len(ids) != number_of_columns - 1 or any(" " in id_ for id_ in ids):
        logger.error("The time series file %s has a truncated PCRaster header.", tss_file)
        raise ValueError(
            f"The PCRaster header of the time series file {tss_file} is truncated: it "
            f"announces {number_of_columns} column(s) but does not list "
            f"{number_of_columns - 1} station id(s)."
        )
    if number_of_columns - 1 != len(cols_names):
        logger.error(
            "The number of columns in the header of %s is different from the number of "
            "column names.",
            tss_file,
        )
        raise ValueError(
            f"The PCRaster header of the time series file {tss_file} announces "
            f"{number_of_columns} column(s), the column names give {len(cols_names) + 1}."
        )
    if ids != list(cols_names):
        logger.error("The station ids in the header of %s are not the configured ones.", tss_file)
        raise ValueError(
            f"The station ids in the PCRaster header of the time series file {tss_file} "
            f"are {ids}, the column names give {list(cols_names)}."
        )
    return lines[3 + number_of_columns - 1 :]


def tss2csv(tss_files, cols_names: list[str], should_delete_src_tss: bool = True) -> None:
    """Convert the given PCRaster Time Series (``*.tss``) files to ``*.csv``.

    The conversion is transactional: every CSV is first written to a
    temporary name, the temporary files are renamed only after all of them
    were produced, and any destination being overwritten is kept as a backup
    until every rename succeeded. A failure up to that point leaves the
    sources and the previous CSV files untouched. A destination that is a
    symlink is followed: the conversion updates its target and leaves the link
    itself alone. Installing the last CSV
    commits the conversion; the sources are deleted afterwards, so a source
    that cannot be deleted is reported and converted again on the next run
    instead of undoing CSV files that are already valid. Only the files passed
    in are read; nothing else in their directories is, and the staging and
    backup names are allocated so that unrelated files next to a destination
    are never overwritten.

    Every source must carry the PCRaster header the model writes (a title
    line, the number of columns, the ``timestep`` line and one line per
    station id): the header is checked against the column names given here and
    only the data rows below it are converted, so the CSV keeps its ``0;<id>``
    header and one row per time step.

    :raises ValueError: If the column names are empty, if a source carries no
        PCRaster header, if its header does not describe the given column
        names, if a source has no data rows, or if a source has a different
        number of columns.
    :raises IsADirectoryError: If a destination path is an existing directory.

    :param tss_files: Paths of the ``.tss`` files to convert. Each item accepts
        anything :func:`rubem._paths.as_path` does, ``bytes`` included.
    :type tss_files: list

    :param cols_names: Station ids of the columns, in the order the time
        series holds them. They name the columns of the CSV and are checked
        against the station ids the PCRaster header of each source lists, so
        they are those ids and not free aliases.
    :type cols_names: list[str]

    :param should_delete_src_tss: Remove the source files after conversion, defaults to ``True``.
    :type should_delete_src_tss: bool, optional
    """
    if not cols_names:
        raise ValueError("The list of column names is empty.")

    tss_files = [str(as_path(tss_file).absolute()) for tss_file in tss_files]
    for tss_file in tss_files:
        if not Path(tss_file).is_file():
            raise FileNotFoundError(f"The time series file {tss_file} does not exist.")

    header = ["0"]
    header.extend(cols_names)

    pending: list[tuple[str, str]] = []
    installs: list[tuple[str, str | None]] = []
    try:
        for tss_file in tss_files:
            dst_file_path = _install_path(str(Path(tss_file).with_suffix(".csv")))

            with Path(tss_file).open(encoding="utf8") as f:
                lines = f.readlines()

            rows = _split_header(lines, tss_file, cols_names)
            data = [line.split() for line in rows if line.strip()]
            if not data:
                logger.error("The time series file %s has no data rows.", tss_file)
                raise ValueError(
                    f"The time series file {tss_file} is empty; refusing to replace "
                    "its CSV with a header-only file."
                )
            divergent = next(
                ((number, row) for number, row in enumerate(data, 1) if len(row) != len(header)),
                None,
            )
            if divergent is not None:
                number, row = divergent
                logger.error(
                    "Number of columns in the file %s is different from the number of column names.",
                    tss_file,
                )
                raise ValueError(
                    f"The number of columns in the file {tss_file} is different "
                    f"from the number of column names: data row {number} has {len(row)} "
                    f"column(s), the column names give {len(header)}."
                )

            previous_mode = _destination_mode(dst_file_path)
            handle, tmp_file_path = _reserve_stage(dst_file_path, ".tmp")
            pending.append((tmp_file_path, dst_file_path))
            # While the descriptor is still the one that was reserved.
            _apply_mode(handle, tmp_file_path, previous_mode)
            with os.fdopen(handle, mode="w", encoding="utf8", newline="") as csvfile:
                writer = csv.writer(csvfile, delimiter=";")
                writer.writerow(header)
                writer.writerows(data)

        for tmp_file_path, dst_file_path in pending:
            backup_file_path = _backup_destination(dst_file_path)
            # Recorded before the install so that a failure in it is undone too.
            installs.append((dst_file_path, backup_file_path))
            Path(tmp_file_path).replace(dst_file_path)
    except Exception:
        _undo_installs(installs)
        for tmp_file_path, _ in pending:
            _remove(tmp_file_path)
        raise

    for _, backup_file_path in installs:
        if backup_file_path:
            _remove(backup_file_path)

    if should_delete_src_tss:
        undeleted = [tss_file for tss_file in tss_files if not _remove(tss_file)]
        if undeleted:
            logger.warning(
                "The conversion is complete, but %d source file(s) could not be deleted and "
                "will be converted again on the next run: %s",
                len(undeleted),
                ", ".join(undeleted),
            )
