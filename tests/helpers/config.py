"""Shared configuration for the synthetic regression fixture dataset.

The dictionary produced by :func:`base_model_config` is the single source of
truth for the regression runs: the integration tests, the exact golden test
and ``tests/fixtures/regenerate_golden.py`` all build their configuration
through it, so the goldens are always produced and checked with the same
inputs.
"""

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
FIXTURES_DIR = os.path.join(REPO_ROOT, "tests", "fixtures")
BASE_DATA_DIR = os.path.join(FIXTURES_DIR, "base")
GOLDEN_DIR = os.path.join(BASE_DATA_DIR, "out")
SHA256SUMS_PATH = os.path.join(GOLDEN_DIR, "SHA256SUMS")

OUTPUT_VARIABLES = ("itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf", "arn")
TIMESTEPS = (1, 2)

RASTER_GOLDENS = [
    f"{variable}00000.{timestep:03d}" for variable in OUTPUT_VARIABLES for timestep in TIMESTEPS
]
TIFF_GOLDENS = [
    f"{variable}{timestep:07d}.tif"
    for variable in OUTPUT_VARIABLES
    for timestep in TIMESTEPS
]
CSV_GOLDENS = [f"tss_{variable}.csv" for variable in OUTPUT_VARIABLES]
GOLDEN_FILES = RASTER_GOLDENS + TIFF_GOLDENS + CSV_GOLDENS


def base_model_config(output_dir):
    """Return a fresh configuration dictionary for the synthetic dataset.

    :param output_dir: Directory that receives the simulation outputs.
    :type output_dir: str
    """
    base = BASE_DATA_DIR
    return {
        "SIM_TIME": {"start": "01/01/2000", "end": "01/02/2000"},
        "DIRECTORIES": {
            "output": output_dir,
            "etp": f"{base}/maps/etp/",
            "prec": f"{base}/maps/rain/",
            "ndvi": f"{base}/maps/ndvi/",
            "kp": f"{base}/maps/kp/",
            "landuse": f"{base}/maps/lulc/",
        },
        "FILENAME_PREFIXES": {
            "etp_prefix": "etp",
            "prec_prefix": "prec",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob",
        },
        "RASTERS": {
            "dem": f"{base}/maps/dem/dem.map",
            "clone": f"{base}/maps/clone/clone.map",
            "ldd": f"{base}/maps/ldd/ldd.map",
            "ndvi_max": f"{base}/maps/ndvi/ndvi_max.map",
            "ndvi_min": f"{base}/maps/ndvi/ndvi_min.map",
            "soil": f"{base}/maps/soil/soil.map",
            "samples": f"{base}/maps/samples/samples.map",
        },
        "TABLES": {
            "rainydays": f"{base}/txt/rainydays.txt",
            "a_i": f"{base}/txt/lulc/a_i.txt",
            "a_o": f"{base}/txt/lulc/a_o.txt",
            "a_s": f"{base}/txt/lulc/a_s.txt",
            "a_v": f"{base}/txt/lulc/a_v.txt",
            "manning": f"{base}/txt/lulc/manning.txt",
            "bulk_density": f"{base}/txt/soil/dg.txt",
            "k_sat": f"{base}/txt/soil/Kr.txt",
            "t_fcap": f"{base}/txt/soil/Tcc.txt",
            "t_sat": f"{base}/txt/soil/Tsat.txt",
            "t_wp": f"{base}/txt/soil/Tw.txt",
            "rootzone_depth": f"{base}/txt/soil/Zr.txt",
            "k_c_min": f"{base}/txt/lulc/kcmin.txt",
            "k_c_max": f"{base}/txt/lulc/kcmax.txt",
        },
        "GRID": {"grid": 500.0},
        "CALIBRATION": {
            "alpha": 4.5,
            "b": 0.5,
            "w_1": 0.333,
            "w_2": 0.333,
            "w_3": 0.334,
            "rcd": 5.0,
            "f": 0.5,
            "alpha_gw": 0.5,
            "x": 0.5,
        },
        "INITIAL_SOIL_CONDITIONS": {
            "t_ini": 1.0,
            "bfw_ini": 0.1,
            "bfw_lim": 1.0,
            "s_sat_ini": 1.1,
        },
        "CONSTANTS": {
            "fpar_max": 0.95,
            "fpar_min": 0.001,
            "lai_max": 12.0,
            "i_imp": 2.5,
        },
        "GENERATE_FILE": {
            "itp": True,
            "bfw": True,
            "srn": True,
            "eta": True,
            "lfw": True,
            "rec": True,
            "smc": True,
            "rnf": True,
            "arn": True,
            "tss": True,
        },
        "RASTER_FILE_FORMAT": {"map_raster_series": True, "tiff_raster_series": True},
    }


def read_sha256sums(path=SHA256SUMS_PATH):
    """Parse a ``SHA256SUMS`` file into a ``{filename: digest}`` dictionary."""
    sums = {}
    with open(path, encoding="utf-8") as checksum_file:
        for line in checksum_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            digest, _, name = line.partition("  ")
            sums[name] = digest
    return sums
