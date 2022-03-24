# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2022 LabSid PHA EPUSP

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
# Contact: rubem.hydrological@labsid.eng.br

"""Common date functionality used by RUBEM."""

from calendar import monthrange
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Calculation of number of months (steps) based on the start
# and end dates of simulation
def totalSteps(startDate, endDate):
    """Get the number of months between start and end dates.

    :param startDate: Start date.
    :startDate type: str

    :param startDate: End date.
    :startDate type: str

    :return: First step, Last step and Number of months between start\
        and end dates
    :rtype: tuple(int, int ,int)
    """
    start = datetime.strptime(startDate, "%d/%m/%Y")
    end = datetime.strptime(endDate, "%d/%m/%Y")
    assert end > start, "End date must be greater than start date"
    nTimeSteps = (end.year - start.year) * 12 + (end.month - start.month) + 1
    lastTimeStep = nTimeSteps
    # PCRaster: first timestep argument of DynamicFramework must be > 0
    firstTimestep = 1
    return (firstTimestep, lastTimeStep, nTimeSteps)


def daysOfMonth(startDate, timestep):
    """Get the number of days in the month from timestep (for flow\
        conversion from mm to m3/s).

    :param startDate: Start date.
    :startDate  type: str

    :param timestep: Timestep for evaluate actual month
    :timestep  type: int

    :returns: Days of month.
    :rtype: int
    """
    sourcedate = datetime.strptime(startDate, "%d/%m/%Y")
    month = sourcedate.month - 2 + timestep
    year = sourcedate.year + month // 12
    month = (month % 12) + 1
    days = monthrange(year, month)[1]
    return days
