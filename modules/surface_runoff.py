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

def Ch_calc(self, pcr, TUr, dg, Zr, tpor, b):
    """Return Ch.
    
    :param pcr:
    :pcr  type:

    :param TUr:
    :TUr  type:

    :param dg:
    :dg  type:

    :param Zr:
    :Zr  type:

    :param tpor:
    :tpor  type:

    :param b:
    :b  type:

    :returns:
    :rtype:
    """
    tur = TUr / (dg * Zr * 10)  # [%] soil moisture
    Ch = (tur / tpor) ** b
    return Ch


def Cper_calc(self, pcr, TUw, dg, Zr, S, manning, w1, w2, w3):
    """Return Cper.
    
    :param pcr:
    :pcr  type:

    :param TUw:
    :TUw  type:

    :param dg:
    :dg  type:

    :param Zr:
    :Zr  type:

    :param S:
    :S  type:

    :param manning:
    :manning  type:

    :param w1:
    :w1  type:

    :param w2:
    :w2  type:

    :param w3:
    :w3  type:

    :returns:
    :rtype:
    """
    tuw = TUw / (dg * Zr * 10)  # [%] soil wilting point
    Cper = w1 * (0.02 / manning) + w2 * (tuw / (1 - tuw)) + w3 * ((S / (10 + S)))
    return Cper


def Cimp_calc(self, pcr, ao, ai):
    """Return Cimp.
    
    :param pcr:
    :pcr  type:

    :param ao:
    :ao  type:

    :param ai:
    :ai  type:

    :returns:
    :rtype:
    """
    Aimp = ao + ai
    Cimp = 0.09 * pcr.exp((2.4 * Aimp))
    return Aimp, Cimp


def Cwp_calc(self, pcr, Aimp, Cper, Cimp):
    """Return Cwp.
    
    :param pcr:
    :pcr  type:

    :param Aimp:
    :Aimp  type:

    :param Cper:
    :Cper  type:

    :param Cimp:
    :Cimp  type:

    :returns:
    :rtype:
    """
    Cwp = (1 - Aimp) * Cper + Aimp * Cimp
    return Cwp


def Csr_calc(self, pcr, Cwp, P_24, RCD):
    """Return Csr.
    
    :param pcr:
    :pcr  type:

    :param Cwp:
    :Cwp  type:

    :param P_24:
    :P_24  type:

    :param RCD:
    :RCD  type:

    :returns:
    :rtype:
    """
    Csr = (Cwp * P_24) / (Cwp * P_24 - RCD * Cwp + RCD)
    return Csr


def ES_calc(self, pcr, Csr, Ch, prec, I, Ao, ETao):
    """Return surface runoff.
    
    :param pcr:
    :pcr  type:

    :param Csr:
    :Csr  type:

    :param Ch:
    :Ch  type:

    :param prec:
    :prec  type:

    :param I:
    :I  type:

    :param Ao:
    :Ao  type:

    :param ETao:
    :ETao  type:

    :returns:
    :rtype:
    """
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)
    # condition for positive value for (prec - ETao)
    cond2 = pcr.scalar((prec - ETao) > 0)

    ES = (Csr * Ch * (prec - I)) * (1 - cond1) + (prec - ETao) * cond2 * cond1
    return ES
