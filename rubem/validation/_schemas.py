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

"""RUBEM settings schemas."""

requiredConfigSchema = {
    "SIM_TIME": {"start": "None", "end": "None"},
    "DIRECTORIES": {
        "input": "None",
        "output": "None",
        "etp": "None",
        "prec": "None",
        "ndvi": "None",
        "Kp": "None",
        "landuse": "None",
    },
    "FILENAME_PREFIXES": {
        "etp_prefix": "None",
        "prec_prefix": "None",
        "ndvi_prefix": "None",
        "kp_prefix": "None",
        "landuse_prefix": "None",
    },
    "RASTERS": {
        "dem": "None",
        "demtif": "None",
        "clone": "None",
        "ndvi_max": "None",
        "ndvi_min": "None",
        "soil": "None",
        "samples": "None",
    },
    "TABLES": {
        "rainydays": "None",
        "a_i": "None",
        "a_o": "None",
        "a_s": "None",
        "a_v": "None",
        "manning": "None",
        "bulk_density": "None",
        "K_sat": "None",
        "T_fcap": "None",
        "T_sat": "None",
        "T_wp": "None",
        "rootzone_depth": "None",
        "K_c_min": "None",
        "K_c_max": "None",
    },
    "GRID": {"grid": "None"},
    "CALIBRATION": {
        "alpha": "None",
        "b": "None",
        "w_1": "None",
        "w_2": "None",
        "w_3": "None",
        "rcd": "None",
        "f": "None",
        "alpha_gw": "None",
        "x": "None",
    },
    "INITIAL_SOIL_CONDITIONS": {
        "T_ini": "None",
        "bfw_ini": "None",
        "bfw_lim": "None",
        "S_sat_ini": "None",
    },
    "CONSTANTS": {
        "fpar_max": "None",
        "fpar_min": "None",
        "lai_max": "None",
        "i_imp": "None",
    },
    "GENERATE_FILE": {
        "itp": "None",
        "bfw": "None",
        "srn": "None",
        "eta": "None",
        "lfw": "None",
        "rec": "None",
        "smc": "None",
        "rnf": "None",
        "tss": "None",
    },
    "RASTER_FILE_FORMAT": {"map_raster_series": "None", "tiff_raster_series": "None"},
}
