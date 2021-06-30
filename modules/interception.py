# coding=utf-8
# RUBEM RUBEM is a distributed hydrological model to calculate monthly
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

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

########## Interception Module ##########

# - Function that returns srmin and srmax
def sr_calc(self, pcr, NDVI):
    """
    :param pcr:
    :pcr type:

    :param NDVI:
    :NDVI type:

    :returns:
    :rtype:
    """
    SR = (1 + NDVI) / (1 - NDVI)
    return SR


# - Function that returns Kc
def kc_calc(self, pcr, NDVI, ndvi_min, ndvi_max, kc_min, kc_max):
    """
    :param pcr:
    :pcr type:

    :param NDVI:
    :NDVI type:

    :param ndvi_min:
    :ndvi_min type:

    :param ndvi_max:
    :ndvi_max type:

    :param kc_min:
    :kc_min type:

    :param kc_max:
    :kc_max type:

    :returns:
    :rtype:
    """
    Kc = kc_min + ((kc_max - kc_min) * 
        ((NDVI - pcr.scalar(ndvi_min)) / (pcr.scalar(ndvi_max) - pcr.scalar(ndvi_min))))
    return Kc


# - Function that returns fpar
def fpar_calc(self, pcr, fpar_min, fpar_max, SR, sr_min, sr_max):
    """
    :param pcr:
    :pcr type:

    :param fpar_min:
    :fpar_min type:

    :param fpar_max:
    :fpar_max type:

    :param SR:
    :SR type:

    :param sr_min:
    :sr_min type:

    :param sr_max:
    :sr_max type:

    :returns:
    :rtype:
    """
    fpar_comp = ((SR - sr_min) * (fpar_max - fpar_min) / (sr_max - sr_min)) + fpar_min
    FPAR = pcr.min(fpar_comp, fpar_max)
    return FPAR


# - Function that returns LAI
def lai_function(self, pcr, FPAR, fpar_max, lai_max):
    """
    :param pcr:
    :pcr type:

    :param FPAR:
    :FPAR type:

    :param fpar_max:
    :fpar_max type:

    :param lai_max:
    :lai_max type:

    :returns:
    :rtype:
    """
    LAI = lai_max * ((pcr.log10(1 - FPAR)) / (pcr.log10(1 - fpar_max)))
    return LAI


# - Function that returns Interception
def Interception_function(self, pcr, alfa, LAI, precipitation, rainy_days, a_v):
    """
    :param pcr:
    :pcr type:

    :param alfa:
    :alfa type:

    :param LAI:
    :LAI type:

    :param precipitation:
    :precipitation type:

    :param rainy_days:
    :rainy_days type:

    :param a_v:
    :a_v type:

    :returns:
    :rtype:
    """
    # condition of precipitation, to divide by non zero number (missing value)
    cond1 = pcr.scalar((precipitation != 0))
    cond2 = pcr.scalar((precipitation == 0))
    prec = precipitation * cond1 + (precipitation * cond2 + 0.00001)

    Id = (alfa * LAI * 
        (1 - (1 / (1 + (precipitation * ((1 - (pcr.exp(-0.463 * LAI))) / (alfa * LAI)))))))
    Ir = 1 - pcr.exp(-Id * rainy_days / prec)
    # Interception of the vegetated area
    Iv = precipitation * Ir
    # Total interception
    I = a_v * Iv
    return Id, Ir, Iv, I
