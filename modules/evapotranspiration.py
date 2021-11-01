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

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

########## Evapotranspiration Module ##########

def Ks_calc(self, pcr, TUr, TUw, TUcc):
    """Return Water Stress Coefficient (Ks) for evapotranspiration of vegetated area.

    :param pcr: PCRaster Library
    :pcr  type:

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


def ETav_calc(self, pcr, ETp, Kc, Ks):
    """Return evapotranspiration of vegetated area.

    :param pcr:
    :pcr  type:

    :param ETp:
    :ETp  type:

    :param Kc:
    :Kc  type:

    :param Ks:
    :Ks  type:

    :returns:
    :rtype:
    """
    ETav = ETp * Kc * Ks
    return ETav


def Kp_calc(self, pcr, B, U_2, UR):
    """Return Kp for evapotranspiration of open water area.

    :param pcr:
    :pcr  type:

    :param B:
    :B  type:

    :param U_2:
    :U_2  type:

    :param UR:
    :UR  type:

    :returns:
    :rtype:
    """
    Kp = 0.482 + 0.024 * pcr.ln(B) - 0.000376 * U_2 + 0.0045 * UR
    return Kp


def ETao_calc(self, pcr, ETp, Kp, prec, Ao):
    """Return Ks for evapotranspiration of water area.
    
    :param pcr:
    :pcr  type:

    :param ETp:
    :ETp  type:

    :param Kp:
    :Kp  type:

    :param prec:
    :prec  type:

    :param Ao:
    :Ao  type:

    :returns:
    :rtype:
    """
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)

    ETao_calc = ETp / Kp

    # conditions for max value for ETao_calc, 
    # if ETao_calc > Prec in Pixel with Ao = 1, then ETao = Prec
    cond2 = pcr.scalar((ETao_calc) > prec)

    # ET for open water is ET_calc for 
    # open water + prec (if ET_calc>prec, for Aio = 1) + ET_calc for Ao = 1, 
    # if ET_calc < prec
    ETao = (
        (ETao_calc) * (1 - cond1)
        + prec * cond1 * cond2
        + (ETao_calc) * cond1 * (1 - cond2)
    )
    return ETao


def ETas_calc(self, pcr, ETp, kc_min, Ks):
    """Return Ks for evapotranspiration of bare soil area.
    
    :param pcr:
    :pcr  type:

    :param ETp:
    :ETp  type:

    :param kc_min:
    :kc_min  type:

    :param Ks:
    :Ks  type:

    :returns:
    :rtype:
    """
    cond = 1 * pcr.scalar(Ks != 0)  # caso ks seja diferente de 0
    ETas = ETp * kc_min * Ks * cond
    return ETas
