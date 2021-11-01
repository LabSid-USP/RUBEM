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

"""Rainfall rUnoff Balance Enhanced Model Soil."""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

########## Lateral Flow ##########
def LF_calc(self, pcr, f, Kr, TUr, TUsat):
    """Function to calculate Lateral Flow in the pixel [mm].
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param f: preferred flow direction parameter [-]
    :f  type: float

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: float

    :param TUsat: Soil moisture content at saturation point []
    :TUsat  type: float

    :returns: Lateral Flow [mm]
    :rtype: float
    """
    LF = f * Kr * ((TUr / TUsat) ** 2)
    return LF


########## Recharge ##########
def REC_calc(self, pcr, f, Kr, TUr, TUsat):
    """Function to calculate Recharge in the pixel [mm].
    
    :param pcr: PCRaster Library
    :pcr  type: STR

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: float

    :param Kr: Hydraulic Conductivity of soil class [mm/month]
    :Kr  type: float

    :param TUr: Actual soil moisture content non-saturated zone [mm]
    :TUr  type: float

    :param TUsat: Soil moisture content at saturation point [-]
    :TUsat  type: float

    :returns: Monthly Recharge [mm]
    :rtype: float
    """
    REC = (1 - f) * Kr * ((TUr / TUsat) ** 2)
    return REC


########## Base Flow ##########
def EB_calc(self, pcr, EB_prev, alfaS, REC, TUs, EB_lim):
    """Function to calculate Baseflow in the pixel [mm]..
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param EB_prev: Baseflow at timestep t-1 [mm]
    :EB_prev  type: float

    :param alfaS: Baseflow recession coefficient (Calibrated) [-]
    :alfaS  type: float

    :param REC: Monthly Recharge at timestep t
    :REC  type: float

    :param TUs: Water contect at saturated zone [mm]
    :TUs  type: float

    :param EB_lim: Threshold for baseflow ocurrence [mm]
    :EB_lim  type: float

    :returns: Monthly Baseflow [mm]
    :rtype: float
    """
    # limit condition for base flow
    cond = pcr.scalar(TUs > EB_lim)
    EB = ((EB_prev * ((pcr.exp(1)) ** -alfaS)) + (1 - ((pcr.exp(1)) ** -alfaS)) * REC) * cond
    return EB


########## Soil Balance ##########
# First soil layer
def TUr_calc(self, pcr, TUrprev, P, I, ES, LF, REC, ETr, Ao, Tsat):
    """Function to calculate Actual Soil Moisture Content at non-saturated zone in the pixel [mm].
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param TUrprev: Soil moisture content at timestep t-1 [mm]
    :TUrprev  type: float

    :param P: Monthly precipitation [mm]
    :P  type: float

    :param I: Monthly Interception [mm]
    :I  type: float

    :param ES: Monthly Surface Runoff [mm]
    :ES  type: float

    :param LF: Monthly Lateral Flow [mm]
    :LF  type: float

    :param REC: Monthly Recharge [mm]
    :REC  type: float

    :param ETr: Monthly Actual Evapotranspiration [mm]
    :ETr  type: float

    :param Ao: Open Water Area Fraction [-]
    :Ao  type: float

    :param Tsat: Soil moisture content at saturation point []
    :Tsat  type: float

    :returns: Soil Moisture Content [mm]
    :rtype: float
    """

    # condition for pixel of water, if Ao different of 1 (not water)
    condw1 = pcr.scalar(Ao != 1)
    # soil balance
    balance = TUrprev + P - I - ES - LF - REC - ETr
    # condition for positivie balance
    cond = pcr.scalar(balance > 0)
    # if balance is negative TUR = 0, + if pixel is water, TUR = TUsat
    TUrin = (balance * cond) * condw1 + Tsat * (1 - condw1)
    #condition for tur >tursat
    cond3=pcr.scalar(TUrin<Tsat)
    #If Tur>tsat, TUR=TUsat
    TUr=(TUrin*cond3)+Tsat*(1-cond3)
  
    return TUr




# Second soil layer
def TUs_calc(self, pcr, TUsprev, REC, EB):
    """Function to calculate Actual Water Content at saturated zone in the pixel [mm].
    
    :param pcr: PCRaster Library
    :pcr  type: str

    :param TUsprev: Water content at saturated zone at timestep t-1 [mm]
    :TUrprev  type: float

    :param REC: Monthly Recharge [mm]
    :REC  type: float

    :param EB: Monthly Baseflow[mm]
    :EB  type: float

    :returns: Water content at saturated zone [mm]
    :rtype: float
    """
    # soil balance
    balance = TUsprev + REC - EB
    TUs = balance
    return TUs
