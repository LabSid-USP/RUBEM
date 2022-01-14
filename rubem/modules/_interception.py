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

"""Rainfall rUnoff Balance Enhanced Model Interception"""

########## Interception Module ##########

import logging
from pcraster import scalar, min, log10, exp

from validation._exception_validation import ValidationException

logger = logging.getLogger(__name__)


def srCalc(NDVI):
    """Return Simple Ratio (SR).

    :param NDVI: Normalized Difference Vegetation Index (NDVI) at the pixel
    :NDVI type: float

    :returns: Reflectances Simple Ratio (SR) [-]
    :rtype: float
    """
    if not -1.0 <= NDVI <= 1.0:
        raise ValidationException(f"NDVI must be in the value range [-1.0, 1.0], value was {NDVI}")
        
    SR = (1 + NDVI) / (1 - NDVI)
    return SR


def kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max):
    """Return Crop Coefficient (Kc).

    :param NDVI: Normalized Difference Vegetation Index (NDVI) at the pixel
    :NDVI type: float

    :param ndvi_min: Minimum Normalized Difference Vegetation Index (NDVI) at the pixel
    :ndvi_min type: float

    :param ndvi_max: Maximum Normalized Difference Vegetation Index (NDVI) at the pixel
    :ndvi_max type: float

    :param kc_min: Minimum Crop Coefficient landuse class [-]
    :kc_min type: float

    :param kc_max: Maximum Crop Coefficient landuse class [-]
    :kc_max type: float

    :returns: Crop Coefficient (Kc) [-]
    :rtype: float
    """
    Kc = kc_min + (
        (kc_max - kc_min)
        * ((NDVI - scalar(ndvi_min)) / (scalar(ndvi_max) - scalar(ndvi_min)))
    )
    return Kc


def fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max):
    """Return Fraction of Photosynthetically Active Radiation (FPAR).

    :param fpar_min: Minimum Fraction of Photosynthetically Active Radiation [-]
    :fpar_min type: float

    :param fpar_max: Maximum Fraction of Photosynthetically Active Radiation [-]
    :fpar_max type: float

    :param SR: Reflectances Simple Ratio [-]
    :SR type: float

    :param sr_min: Mimimum Reflectances Simple Ratio [-]
    :sr_min type: float

    :param sr_max: Maximum Reflectances Simple Ratio [-]
    :sr_max type: float

    :returns: Fraction of Photosynthetically Active Radiation (FPAR) [-]
    :rtype: float
    """
    fpar_comp = ((SR - sr_min) * (fpar_max - fpar_min) / (sr_max - sr_min)) + fpar_min
    FPAR = min(fpar_comp, fpar_max)
    return FPAR


def laiCalc(FPAR, fpar_max, lai_max):
    """Return Leaf Area Index (LAI).

    :param FPAR: Fraction of Photosynthetically Active Radiation (FPAR) [-]
    :FPAR type: float

    :param fpar_max: Maximum Fraction of Photosynthetically Active Radiation (FPAR) [-]
    :fpar_max type: float

    :param lai_max: Maximum Leaf Area Index [-]
    :lai_max type: float

    :returns: Leaf Area Index (LAI) [-]
    :rtype:float
    """
    LAI = lai_max * ((log10(1 - FPAR)) / (log10(1 - fpar_max)))
    return LAI


def interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v):
    """Return Interception [mm].

    :param alfa: Interception Parameter [-]
    :alfa type: float

    :param LAI: Leaf Area Index (LAI) [-]
    :LAI type: float

    :param precipitation: Monthly Precipitation [mm]
    :precipitation type: float

    :param rainy_days: Number of rainy days for month
    :rainy_days type: int

    :param a_v: Vegetated Area Fraction
    :a_v type: float

    :returns: Monthly Interception [mm]
    :rtype: float
    """
    # condition of precipitation, to divide by non zero number (missing value)
    cond1 = scalar((precipitation != 0))
    cond2 = scalar((precipitation == 0))
    prec = precipitation * cond1 + (precipitation * cond2 + 0.00001)

    Id = (
        alfa
        * LAI
        * (1 - (1 / (1 + (precipitation * ((1 - (exp(-0.463 * LAI))) / (alfa * LAI))))))
    )
    Ir = 1 - exp(-Id * rainy_days / prec)
    # Interception of the vegetated area
    Iv = precipitation * Ir
    # Total interception
    I = a_v * Iv
    return Id, Ir, Iv, I
