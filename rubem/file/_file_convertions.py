import csv
import glob
import logging
import os

logger = logging.getLogger(__name__)


def tss2csv(tss_dir_path: str, cols_names: list[str], should_delete_src_tss: bool = True) -> None:
    """Convert all PCRaster Time Series (*.tss) files present in the specified directory to (*.csv).

    :param tss_dir_path: Directory containing the files.
    :type tss_dir_path: str

    :param cols_names: List of strings of aliases for the column names.
    :type cols_names: list[str]

    :param should_delete_src_tss: Remove PCRaster Time Series (*.tss) files after conversion, default to ``True``s
    :type should_delete_src_tss: bool, optional
    """

    if not tss_dir_path:
        raise ValueError("The directory path is empty.")

    if not os.path.isdir(tss_dir_path):
        raise ValueError("The directory path does not exist.")

    if not cols_names:
        raise ValueError("The list of column names is empty.")

    header = ["0"]
    header.extend(cols_names)

    for tss_file in glob.glob(os.path.abspath(os.path.join(tss_dir_path, "*.tss"))):
        dst_file_path = os.path.abspath(
            os.path.join(os.path.dirname(tss_file), f"{os.path.splitext(tss_file)[0]}.csv")
        )
        with open(file=tss_file, mode="r", encoding="utf8") as f:
            lines = f.readlines()

        data = [line.split() for line in lines]
        if len(data[0]) != len(header):
            logger.error(
                "Number of columns in the file %s is different from the number of column names.",
                tss_file,
            )
            raise ValueError(
                f"The number of columns in the file {tss_file} is different from the number of column names."
            )

        with open(file=dst_file_path, mode="w", encoding="utf8", newline="") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            writer.writerow(header)
            writer.writerows(data)

        if should_delete_src_tss:
            try:
                os.remove(tss_file)
            except Exception as e:
                logger.error("Error while deleting file %s. %s", tss_file, e)
