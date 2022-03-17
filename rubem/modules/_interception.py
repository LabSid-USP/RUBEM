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


from ctypes.wintypes import FLOAT
import typing
import logging

import pcraster as pcr
from pcraster.framework import generalfunctions


logger = logging.getLogger(__name__)


def srCalc(NDVI: pcr._pcraster.Field) -> pcr._pcraster.Field:
    """Return Simple Ratio (SR).

    :param NDVI: Normalized Difference Vegetation Index (NDVI) at the pixel
    :NDVI type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Reflectances Simple Ratio (SR) [-]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    SR = (1 + NDVI) / (1 - NDVI)
    return SR


def kcCalc(
    NDVI: pcr._pcraster.Field,
    ndvi_min: pcr._pcraster.Field,
    ndvi_max: pcr._pcraster.Field,
    kc_min: pcr._pcraster.Field,
    kc_max: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return Crop Coefficient (Kc).

    :param NDVI: Normalized Difference Vegetation Index (NDVI) at the pixel
    :NDVI type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param ndvi_min: Minimum Normalized Difference Vegetation Index (NDVI)\
        at the pixel
    :ndvi_min type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param ndvi_max: Maximum Normalized Difference Vegetation Index (NDVI)\
        at the pixel
    :ndvi_max type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param kc_min: Minimum Crop Coefficient landuse class [-]
    :kc_min type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param kc_max: Maximum Crop Coefficient landuse class [-]
    :kc_max type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Crop Coefficient (Kc) [-]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    Kc = kc_min + (
        (kc_max - kc_min)
        * (
            (NDVI - pcr.scalar(ndvi_min))
            / (pcr.scalar(ndvi_max) - pcr.scalar(ndvi_min))
        )
    )
    return Kc


def fparCalc(
    fpar_min: float,
    fpar_max: float,
    SR: pcr._pcraster.Field,
    sr_min: pcr._pcraster.Field,
    sr_max: pcr._pcraster.Field,
) -> pcr._pcraster.Field:
    """Return Fraction of Photosynthetically Active Radiation (FPAR).

    :param fpar_min: Minimum Fraction of Photosynthetically Active Radiation\
        [-]
    :fpar_min type: float

    :param fpar_max: Maximum Fraction of Photosynthetically Active Radiation\
        [-]
    :fpar_max type: float

    :param SR: Reflectances Simple Ratio [-]
    :SR type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param sr_min: Mimimum Reflectances Simple Ratio [-]
    :sr_min type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param sr_max: Maximum Reflectances Simple Ratio [-]
    :sr_max type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Fraction of Photosynthetically Active Radiation (FPAR) [-]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    fpar_comp = (
        (SR - sr_min) * (fpar_max - fpar_min) / (sr_max - sr_min)
    ) + fpar_min
    FPAR = pcr.min(fpar_comp, fpar_max)
    return FPAR


def laiCalc(
    FPAR: pcr._pcraster.Field,
    fpar_max: float,
    lai_max: float,
) -> pcr._pcraster.Field:
    """Return Leaf Area Index (LAI).

    :param FPAR: Fraction of Photosynthetically Active Radiation (FPAR) [-]
    :FPAR type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param fpar_max: Maximum Fraction of Photosynthetically Active Radiation\
        (FPAR) [-]
    :fpar_max type: float

    :param lai_max: Maximum Leaf Area Index [-]
    :lai_max type: float

    :returns: Leaf Area Index (LAI) [-]
    :rtype:pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    LAI = lai_max * ((pcr.log10(1 - FPAR)) / (pcr.log10(1 - fpar_max)))
    return LAI


def interceptionCalc(
    alfa: float,
    LAI: pcr._pcraster.Field,
    precipitation: pcr._pcraster.Field,
    rainy_days: pcr._pcraster.Field,
    a_v: pcr._pcraster.Field,
) -> typing.Tuple[
    pcr._pcraster.Field,
    pcr._pcraster.Field,
    pcr._pcraster.Field,
    pcr._pcraster.Field,
]:
    """Return Interception [mm].

    :param alfa: Interception Parameter [-]
    :alfa type: float

    :param LAI: Leaf Area Index (LAI) [-]
    :LAI type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param precipitation: Monthly Precipitation [mm]
    :precipitation type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param rainy_days: Number of rainy days for month
    :rainy_days type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :param a_v: Vegetated Area Fraction
    :a_v type: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR

    :returns: Monthly Interception [mm]
    :rtype: pcr._pcraster.Field PCRASTER_VALUESCALE=VS_SCALAR
    """
    # condition of precipitation, to divide by non zero number (missing value)
    cond1 = pcr.scalar((precipitation != 0))
    cond2 = pcr.scalar((precipitation == 0))
    prec = precipitation * cond1 + (precipitation * cond2 + 0.00001)

    Id = (
        alfa
        * LAI
        * (
            1
            - (
                1
                / (
                    1
                    + (
                        precipitation
                        * ((1 - (pcr.exp(-0.463 * LAI))) / (alfa * LAI))
                    )
                )
            )
        )
    )
    Ir = 1 - pcr.exp(-Id * rainy_days / prec)
    # Interception of the vegetated area
    Iv = precipitation * Ir
    # Total interception
    interception = a_v * Iv
    return Id, Ir, Iv, interception
