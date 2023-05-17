# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2023 LabSid PHA EPUSP

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

"""Rainfall rUnoff Balance Enhanced Model Surface Runoff"""


import logging

import pcraster as pcr

logger = logging.getLogger(__name__)


def chCalc(
    TUr: pcr._pcraster.Field,
    dg: pcr._pcraster.Field,
    Zr: pcr._pcraster.Field,
    Tsat: pcr._pcraster.Field,
    b: float,
) -> pcr._pcraster.Field:
    """Return coefficient representing soil moisture conditions (Ch).

    :param TUr: Actual Soil moisture content [mm]
    :TUr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param dg: Soil Bulk Density [g/cm3]
    :dg  type:pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Zr: Depth Rootzone [cm]
    :Zr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param tpor: Soil Porosity [%]
    :tpor  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param b: Ch parameter (calibrated)
    :b  type: float

    :returns: coefficient representing soil moisture conditions [-]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    tur = TUr / (dg * Zr * 10)  # [%] soil moisture
    Ch = (tur / Tsat) ** b
    return Ch


def cperCalc(
    TUw: pcr._pcraster.Field,
    dg: pcr._pcraster.Field,
    Zr: pcr._pcraster.Field,
    S: pcr._pcraster.Field,
    manning: pcr._pcraster.Field,
    w1: float,
    w2: float,
    w3: float,
) -> pcr._pcraster.Field:
    """Return the runoff coefficient for permeable areas (Cper).

    :param TUw:  soil water content at wilting point
    :TUw  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param dg: Soil Bulk Density [g/cm3]
    :dg  type:pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Zr: Depth Rootzone [cm]
    :Zr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param S: Land surfafe slope [%]
    :S  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param manning: Manning's roughness coefficient [-]
    :manning  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param w1: weight for landuse component [-]
    :w1  type: float

    :param w2: weight for soil component [-]
    :w2  type: float

    :param w3: weight for slope component [-]
    :w3  type: float

    :returns: Runoff coefficient for permeable areas (Cper).
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    tuw = TUw / (dg * Zr * 10)  # [%] soil wilting point
    Cper = (
        w1 * (0.02 / manning) + w2 * (tuw / (1 - tuw)) + w3 * ((S / (10 + S)))
    )
    return Cper


def cimpCalc(
    ao: pcr._pcraster.Field, ai: pcr._pcraster.Field
) -> pcr._pcraster.Field:
    """Return percentage of impervious surface per grid cell and\
        the runoff coefficient of the impervious area (Cimp).

    :param Ao: Open Water Area Fraction [-]
    :ao  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param ai: Impervious Area Fraction [-]
    :ai  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: percentage of impervious surface per grid cell and\
        the runoff coefficient of the impervious area [-]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    Aimp = ao + ai
    Cimp = 0.09 * pcr.exp((2.4 * Aimp))
    return Aimp, Cimp


def cwpCalc(
    Aimp: pcr._pcraster.Field,
    Cper: pcr._pcraster.Field,
    Cimp: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return weighted potential runoff coefficient (Cwp).

    :param Aimp: percentage of impervious surface per grid cell
    :Aimp  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Cper: Runoff coefficient for permeable areas (Cper)
    :Cper  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Cimp: the runoff coefficient of the impervious area [-]
    :Cimp  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: weighted potential runoff coefficient (Cwp)
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    Cwp = (1 - Aimp) * Cper + Aimp * Cimp
    return Cwp


def csrCalc(
    Cwp: pcr._pcraster.Field,
    P_24: pcr._pcraster.Field,
    RCD: float,
) -> pcr._pcraster.Field:
    """Return actual runoff coefficient (Csr).

    :param Cwp: weighted potential runoff coefficient (Cwp)
    :Cwp  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param P_24: average daily rainfall in rainy days (mm/day per month)
    :P_24  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param RCD: Regional consecutive dryness level (mm)
    :RCD  type: float

    :returns: actual runoff coefficient (Csr) [-]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    Csr = (Cwp * P_24) / (Cwp * P_24 - RCD * Cwp + RCD)
    return Csr


def sRunoffCalc(
    Csr: pcr._pcraster.Field,
    Ch: pcr._pcraster.Field,
    prec: pcr._pcraster.Field,
    Itp: pcr._pcraster.Field,
    Ao: pcr._pcraster.Field,
    ETao: pcr._pcraster.Field,
    TUr: pcr._pcraster.Field,
    Tsat: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return surface runoff [mm].

    :param Csr: actual runoff coefficient (Csr) [-]
    :Csr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Ch: coefficient representing soil moisture conditions (Ch)
    :Ch  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param prec: Monthly precipitation [mm]
    :prec  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param I: Monthly Interception [mm]
    :Itp  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Ao: Open Water Area Fraction [-]
    :Ao  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param ETao: Evaporation of  Open Water Area [mm]
    :ETao  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param Tsat: Soil moisture content at saturation point [-]
    :TUsat  type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Monthly surface runoff [mm]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)
    # condition for positive value for (prec - ETao)
    cond2 = pcr.scalar((prec - ETao) > 0)
    ESin = (Csr * Ch * (prec - Itp)) * (1 - cond1) + (
        prec - ETao
    ) * cond2 * cond1

    # condition for tur >tursat
    cond3 = pcr.scalar(TUr == Tsat)
    ES = (
        (ESin * (1 - cond3))
        + (prec - Itp) * (cond3) * (1 - cond1)
        + ESin * (cond1)
    )
    return ES
