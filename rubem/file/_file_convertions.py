import csv
import logging
import os

logger = logging.getLogger(__name__)


def tss2csv(tss_files, cols_names: list[str], should_delete_src_tss: bool = True) -> None:
    """Convert the given PCRaster Time Series (``*.tss``) files to ``*.csv``.

    The conversion is transactional: every CSV is first written to a
    temporary name, the temporary files are renamed only after all of them
    were produced, and the sources are removed only after every rename
    succeeded. A failure therefore leaves the source files untouched. Only
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

    renames = []
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
            renames.append((tmp_file_path, dst_file_path))

        for tmp_file_path, dst_file_path in renames:
            os.replace(tmp_file_path, dst_file_path)
    except Exception:
        for tmp_file_path, _ in renames:
            if os.path.isfile(tmp_file_path):
                os.remove(tmp_file_path)
        raise

    if should_delete_src_tss:
        for tss_file in tss_files:
            try:
                os.remove(tss_file)
            except OSError as e:
                logger.error("Error while deleting file %s. %s", tss_file, e)
