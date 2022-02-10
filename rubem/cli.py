# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2021 LabSid PHA EPUSP

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Contact: hydrological@labsid.eng.br

"""RUBEM Command Line Interface (CLI)"""

import logging
import argparse

from __version__ import __release__
from core import Model
from validation._validators import filePathArgValidator

logger = logging.getLogger(__name__)


def main():
    """[summary]

    :raises SystemExit: [description]
    """
    # Configure CLI
    parser = argparse.ArgumentParser(
        prog="rubem",
        description="Rainfall rUnoff Balance Enhanced Model (RUBEM)",
        epilog=(
            f"RUBEM {__release__} Copyright (C) 2020-2021 - LabSid PHA EPUSP -"
            "        This program comes with ABSOLUTELY NO WARRANTY.       "
            " This is free software, and you are welcome to redistribute it  "
            "      under certain conditions."
        ),
    )
    parser.add_argument(
        "-c",
        "--configfile",
        type=filePathArgValidator,
        help="path to configuration file",
        required=True,
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=1, help="verbosity level"
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"RUBEM v{__release__}",
        help="show version and exit",
    )

    args = parser.parse_args()

    args.verbose = 30 - (10 * args.verbose) if args.verbose > 0 else 0
    logging.basicConfig(
        level=args.verbose,
        format="%(asctime)s %(name)s %(levelname)s:%(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.FileHandler("rubem.log"), logging.StreamHandler()],
    )

    try:
        model = Model.load(args.configfile)
    except Exception as e:
        raise SystemExit(1) from e
    else:
        model.run()
        logger.info("Done")
