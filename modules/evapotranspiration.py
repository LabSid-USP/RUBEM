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

"""Rainfall rUnoff Balance Enhanced Model Evapotranspiration."""

########## Evapotranspiration Module ##########


def ksCalc(self, pcr, TUr, TUw, TUcc):
    """Return Water Stress Coefficient (Ks) for evapotranspiration of vegetated area.

    :param pcr: PCRaster Library
    :pcr  type: str

    :param TUr: Actual Soil Moisture Content [mm]
    :TUr  type: float

    :param TUw: Wilting Point of soil class [mm]
    :TUw  type: float

    :param TUcc: Field Capacity of soil class [mm]
    :TUcc  type: float

    :returns: Water Stress Coefficient (Ks) [-]
    :rtype: float
    """
    ks_cond = pcr.scalar(TUr > TUw)  # caso TUr < TUw, (false, ks = 0)
    # Multiply (TUr - TUw) to avoid negative ln
    Ks = (pcr.ln((TUr - TUw) * ks_cond + 1)) / (pcr.ln(TUcc - TUw + 1))
    return Ks


def etavCalc(self, pcr, ETp, Kc, Ks):
    """Return evapotranspiration of vegetated area.

    :param pcr: PCRaster Library
    :pcr  type: str

    :param ETp: Potential Evapotranspiration [mm]
    :ETp  type: float

    :param Kc: Crop Coefficient [-]
    :Kc  type: float

    :param Ks: Water Stress Coefficient [-]
    :Ks  type: float

    :returns: Actual Evapotranspiration
    :rtype: float
    """
    ETav = ETp * Kc * Ks
    return ETav


def kpCalc(self, pcr, B, U_2, UR):
    """Return pan coefficient (Kp) for evapotranspiration of open water area.

    :param pcr: PCRaster Library
    :pcr  type: str

    :param B: Fetch
    :B  type: int

    :param U_2: Wind speed at 2 meters [m/s-1]
    :U_2  type: float

    :param UR: Relative humidity [%]
    :UR  type: float

    :returns: pan coefficient (Kp) []
    :rtype:float
    """
    Kp = 0.482 + 0.024 * pcr.ln(B) - 0.000376 * U_2 + 0.0045 * UR
    return Kp


def etaoCalc(self, pcr, ETp, Kp, prec, Ao):
    """Return actual evapotranspiration of open water area.

    :param pcr: PCRaster Library
    :pcr  type: str

    :param ETp: Monthly Potential Evapotranspiration [mm]
    :ETp  type: float

    :param Kp: pan coefficient (Kp) []
    :Kp  type: float

    :param prec: Monthly Precipitation [mm]
    :prec  type: float

    :param Ao: Open water Area Fraction
    :Ao  type: float

    :returns: Actual evapotranspiration of open water area
    :rtype: float
    """
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)

    etaoCalc = ETp / Kp

    # conditions for max value for etaoCalc,
    # if ETao_calc > Prec in Pixel with Ao = 1, then ETao = Prec
    cond2 = pcr.scalar((etaoCalc) > prec)

    # ET for open water is ET_calc for
    # open water + prec (if ET_calc>prec, for Aio = 1) + ET_calc for Ao = 1,
    # if ET_calc < prec
    ETao = (
        (etaoCalc) * (1 - cond1)
        + prec * cond1 * cond2
        + (etaoCalc) * cond1 * (1 - cond2)
    )
    return ETao


def etasCalc(self, pcr, ETp, kc_min, Ks):
    """Return Ks for evapotranspiration of bare soil area.

    :param pcr: PCRaster Library
    :pcr  type: str

    :param ETp: Monthly Potential Evapotranspiration [mm]
    :ETp  type: float

    :param kc_min: Minimum crop Coefficient [-]
    :kc_min  type: float

    :param Ks: Water Stress Coefficient [-]
    :Ks  type: float

    :returns: Actual Evapotranspiration of bare soil area
    :rtype: float
    """
    cond = 1 * pcr.scalar(Ks != 0)  # caso ks seja diferente de 0
    ETas = ETp * kc_min * Ks * cond
    return ETas
