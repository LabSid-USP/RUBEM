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
# Contact: rubem.hydrological@labsid.eng.br

"""Rainfall rUnoff Balance Enhanced Model Surface Runoff."""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

########## Surface runoff ##########

def Ch_calc(self, pcr, TUr, dg, Zr, Tsat, b):
    """ Function to calculate coefficient representing soil moisture conditions (Ch).
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param TUr: Actual Soil moisture content [mm]
    :TUr  type: float

    :param dg: Soil Bulk Density [g/cm3] 
    :dg  type:float

    :param Zr: Depth Rootzone [cm]
    :Zr  type: float

    :param tpor: Soil Porosity [%]
    :tpor  type: float

    :param b: Ch parameter (calibrated)
    :b  type: float

    :returns: coefficient representing soil moisture conditions [-]
    :rtype: float
    """
    tur = TUr / (dg * Zr * 10)  # [%] soil moisture
    Ch = (tur / Tsat) ** b
    return Ch


def Cper_calc(self, pcr, TUw, dg, Zr, S, manning, w1, w2, w3):
    """Function to calculate runoff coefficient for permeable areas (Cper).
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param TUw:  soil water content at wilting point
    :TUw  type: float

    :param dg: Soil Bulk Density [g/cm3] 
    :dg  type:float

    :param Zr: Depth Rootzone [cm]
    :Zr  type: float

    :param S: Land surfafe slope [%]
    :S  type: float

    :param manning: Manning’s roughness coefficient [-]
    :manning  type: float

    :param w1: weight for landuse component [-]
    :w1  type: float

    :param w2: weight for soil component [-]
    :w2  type: float

    :param w3: weight for slope component [-]
    :w3  type: float

    :returns: Runoff coefficient for permeable areas (Cper).
    :rtype: float
    """
    tuw = TUw / (dg * Zr * 10)  # [%] soil wilting point
    Cper = w1 * (0.02 / manning) + w2 * (tuw / (1 - tuw)) + w3 * ((S / (10 + S)))
    return Cper


def Cimp_calc(self, pcr, ao, ai):
    """Function to calculate percentage of impervious surface per grid cell and the runoff coefficient of the impervious area (Cimp).
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param Ao: Open Water Area Fraction [-]
    :Ao  type: float

    :param ai: Impervious Area Fraction [-]
    :ai  type: float

    :returns: percentage of impervious surface per grid cell and the runoff coefficient of the impervious area [-]
    :rtype: float
    """
    Aimp = ao + ai
    Cimp = 0.09 * pcr.exp((2.4 * Aimp))
    return Aimp, Cimp


def Cwp_calc(self, pcr, Aimp, Cper, Cimp):
    """Function to calculate The weighted potential runoff coefficient (Cwp).
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param Aimp: percentage of impervious surface per grid cell 
    :Aimp  type: float

    :param Cper: Runoff coefficient for permeable areas (Cper)
    :Cper  type: float

    :param Cimp: the runoff coefficient of the impervious area [-]
    :Cimp  type: float

    :returns: weighted potential runoff coefficient (Cwp)
    :rtype: float
    """
    Cwp = (1 - Aimp) * Cper + Aimp * Cimp
    return Cwp


def Csr_calc(self, pcr, Cwp, P_24, RCD):
    """ Function to calculate the actual runoff coefficient (Csr).
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param Cwp: weighted potential runoff coefficient (Cwp)
    :Cwp  type: float

    :param P_24: average daily rainfall in rainy days (mm/day per month)
    :P_24  type:

    :param RCD: Regional consecutive dryness level (mm)
    :RCD  type: float

    :returns: actual runoff coefficient (Csr) [-]
    :rtype: float
    """
    Csr = (Cwp * P_24) / (Cwp * P_24 - RCD * Cwp + RCD)
    return Csr


def ES_calc(self, pcr, Csr, Ch, prec, I, Ao, ETao,TUr,Tsat):
    """Return surface runoff.
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param Csr: actual runoff coefficient (Csr) [-]
    :Csr  type: float

    :param Ch: coefficient representing soil moisture conditions (Ch)
    :Ch  type: float

    :param prec: Monthly precipitation [mm]
    :prec  type: float

    :param I: Monthly Interception [mm]
    :I  type: float

    :param Ao: Open Water Area Fraction [-]
    :Ao  type: float

    :param ETao: Evaporation of  Open Water Area [mm]
    :ETao  type: float

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: float

    :param Tsat: Soil moisture content at saturation point [-]
    :TUsat  type: float

    :returns: Monthly surface runoff [mm]
    :rtype: float
    """
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)
    # condition for positive value for (prec - ETao)
    cond2 = pcr.scalar((prec - ETao) > 0)

    ESin = (Csr * Ch * (prec - I)) * (1 - cond1) + (prec - ETao) * cond2 * cond1

    #condition for tur >tursat
    cond3=pcr.scalar(TUr == Tsat)

    ES=(ESin*(1 - cond3))+(prec - I)*(cond3)*(1-cond1)+ESin*(cond1)

    return ES
