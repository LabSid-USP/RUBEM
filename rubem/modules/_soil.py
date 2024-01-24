# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2024 LabSid PHA EPUSP

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

"""Rainfall rUnoff Balance Enhanced Model Soil"""


import logging

import pcraster as pcr

logger = logging.getLogger(__name__)


def lfCalc(
    f: float,
    Kr: pcr._pcraster.Field,
    TUr: pcr._pcraster.Field,
    TUsat: pcr._pcraster.Field,
):
    """Return Lateral Flow in the pixel [mm].

    :param f: preferred flow direction parameter [-]
    :f  type: float

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param TUsat: Soil moisture content at saturation point []
    :TUsat  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Lateral Flow [mm]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    LF = f * Kr * ((TUr / TUsat) ** 2)
    return LF


def recCalc(
    f: float,
    Kr: pcr._pcraster.Field,
    TUr: pcr._pcraster.Field,
    TUsat: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return Recharge in the pixel [mm].

    :param f: preferred flow direction parameter [-]
    :f  type: float

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Kr: Hydraulic Conductivity of soil class [mm/month]
    :Kr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param TUsat: Soil moisture content at saturation point [-]
    :TUsat  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Monthly Recharge [mm]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    REC = (1 - f) * Kr * ((TUr / TUsat) ** 2)
    return REC


def baseflowCalc(
    EB_prev: pcr._pcraster.Field,
    alfaS: float,
    REC: pcr._pcraster.Field,
    TUs: pcr._pcraster.Field,
    EB_lim: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return Baseflow in the pixel [mm].

    :param EB_prev: Baseflow at timestep t-1 [mm]
    :EB_prev  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param alfaS: Baseflow recession coefficient (Calibrated) [-]
    :alfaS  type: float

    :param REC: Monthly Recharge at timestep t
    :REC  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param TUs: Water contect at saturated zone [mm]
    :TUs  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param EB_lim: Threshold for baseflow ocurrence [mm]
    :EB_lim  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Monthly Baseflow [mm]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    # limit condition for base flow
    cond = pcr.scalar(TUs > EB_lim)
    EB = (
        (EB_prev * ((pcr.exp(1)) ** -alfaS))
        + (1 - ((pcr.exp(1)) ** -alfaS)) * REC
    ) * cond
    return EB


# First soil layer
def turCalc(
    TUrprev: pcr._pcraster.Field,
    P: pcr._pcraster.Field,
    Itp: pcr._pcraster.Field,
    ES: pcr._pcraster.Field,
    LF: pcr._pcraster.Field,
    REC: pcr._pcraster.Field,
    ETr: pcr._pcraster.Field,
    Ao: pcr._pcraster.Field,
    Tsat: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return Actual Soil Moisture Content at non-saturated zone in\
        the pixel [mm].

    :param TUrprev: Soil moisture content at timestep t-1 [mm]
    :TUrprev  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param P: Monthly precipitation [mm]
    :P  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param I: Monthly Interception [mm]
    :Itp type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param ES: Monthly Surface Runoff [mm]
    :ES  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param LF: Monthly Lateral Flow [mm]
    :LF  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param REC: Monthly Recharge [mm]
    :REC  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param ETr: Monthly Actual Evapotranspiration [mm]
    :ETr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Ao: Open Water Area Fraction [-]
    :Ao  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Tsat: Soil moisture content at saturation point []
    :Tsat  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Soil Moisture Content [mm]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """

    # condition for pixel of water, if Ao different of 1 (not water)
    condw1 = pcr.scalar(Ao != 1)
    # soil balance
    balance = TUrprev + P - Itp - ES - LF - REC - ETr
    # condition for positivie balance
    cond = pcr.scalar(balance > 0)
    # if balance is negative TUR = 0, + if pixel is water, TUR = TUsat
    TUrin = (balance * cond) * condw1 + Tsat * (1 - condw1)
    # condition for tur >tursat
    cond3 = pcr.scalar(TUrin < Tsat)
    # If Tur>tsat, TUR=TUsat
    TUr = (TUrin * cond3) + Tsat * (1 - cond3)

    return TUr


# Second soil layer
def tusCalc(
    TUsprev: pcr._pcraster.Field,
    REC: pcr._pcraster.Field,
    EB: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return Actual Water Content at saturated zone in the pixel [mm].

    :param TUsprev: Water content at saturated zone at timestep t-1 [mm]
    :TUsprev  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param REC: Monthly Recharge [mm]
    :REC  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param EB: Monthly Baseflow[mm]
    :EB  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Water content at saturated zone [mm]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    # soil balance
    balance = TUsprev + REC - EB
    TUs = balance
    return TUs
