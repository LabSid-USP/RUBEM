"""Generator of a minimal synthetic 3x3 dataset for in-process model tests.

The dataset is physically plausible (values mirror one land-use and one soil
class of the regression fixtures) but tiny, so a full model run takes
milliseconds. It exists for behavior tests; the regression oracle remains the
fixture dataset under ``tests/fixtures/base``.
"""

import os

import numpy as np

ROWS = 3
COLS = 3
CELL_SIZE = 500.0
WEST = 0.0
NORTH = 1500.0
MISSING = -9999.0

_LULC_CLASS = 3
_SOIL_CLASS = 1

_LULC_TABLES = {
    "a_i": 0.0,
    "a_o": 0.0,
    "a_s": 0.0,
    "a_v": 1.0,
    "manning": 0.16,
    "kcmin": 1.14,
    "kcmax": 1.8,
}
_SOIL_TABLES = {
    "dg": 1.54,
    "Kr": 38.29,
    "Tcc": 0.26,
    "Tsat": 0.46,
    "Tw": 0.12,
    "Zr": 150.39,
}


def write_synthetic_dataset(base_dir, timesteps=2):
    """Write the dataset under ``base_dir`` and return its configuration dict.

    :param base_dir: Directory that receives ``maps/``, ``txt/`` and ``out/``.
    :param timesteps: Number of monthly steps starting at 01/01/2000.
    """
    import pcraster as pcr

    base_dir = str(base_dir)
    pcr.setclone(ROWS, COLS, CELL_SIZE, WEST, NORTH)

    def write_map(rel_path, values, scale, dtype):
        path = os.path.join(base_dir, "maps", rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        array = np.asarray(values, dtype=dtype).reshape(ROWS, COLS)
        pcr.report(pcr.numpy2pcr(scale, array, MISSING), path)
        return path

    dem = np.linspace(100.0, 140.0, ROWS * COLS)
    write_map("dem/dem.map", dem, pcr.Scalar, np.float32)
    write_map("clone/clone.map", np.ones(ROWS * COLS), pcr.Boolean, np.uint8)
    ldd_field = pcr.lddcreate(
        pcr.numpy2pcr(pcr.Scalar, dem.reshape(ROWS, COLS).astype(np.float32), MISSING),
        1e31,
        1e31,
        1e31,
        1e31,
    )
    ldd_path = os.path.join(base_dir, "maps", "ldd", "ldd.map")
    os.makedirs(os.path.dirname(ldd_path), exist_ok=True)
    pcr.report(ldd_field, ldd_path)
    write_map("soil/soil.map", np.full(ROWS * COLS, _SOIL_CLASS), pcr.Nominal, np.int32)
    samples = np.full(ROWS * COLS, MISSING)
    samples[0] = 1
    samples[ROWS * COLS - 1] = 2
    write_map("samples/samples.map", samples, pcr.Nominal, np.float64)
    write_map("ndvi/ndvi_min.map", np.full(ROWS * COLS, 0.2), pcr.Scalar, np.float32)
    write_map("ndvi/ndvi_max.map", np.full(ROWS * COLS, 0.9), pcr.Scalar, np.float32)

    def series_name(prefix, step):
        return f"{prefix}{'0' * (8 - len(prefix))}.{step:03d}"

    for step in range(1, timesteps + 1):
        write_map(
            f"ndvi/{series_name('ndvi', step)}",
            np.full(ROWS * COLS, 0.5 + 0.05 * step),
            pcr.Scalar,
            np.float32,
        )
        write_map(
            f"etp/{series_name('etp', step)}",
            np.full(ROWS * COLS, 80.0 + 5.0 * step),
            pcr.Scalar,
            np.float32,
        )
        write_map(
            f"rain/{series_name('prec', step)}",
            np.full(ROWS * COLS, 120.0 - 10.0 * step),
            pcr.Scalar,
            np.float32,
        )
        write_map(
            f"kp/{series_name('kp', step)}",
            np.full(ROWS * COLS, 0.8),
            pcr.Scalar,
            np.float32,
        )
        write_map(
            f"lulc/{series_name('cob', step)}",
            np.full(ROWS * COLS, _LULC_CLASS),
            pcr.Nominal,
            np.int32,
        )

    txt_dir = os.path.join(base_dir, "txt")
    os.makedirs(os.path.join(txt_dir, "lulc"), exist_ok=True)
    os.makedirs(os.path.join(txt_dir, "soil"), exist_ok=True)
    for name, value in _LULC_TABLES.items():
        with open(os.path.join(txt_dir, "lulc", f"{name}.txt"), "w", encoding="utf8") as f:
            f.write(f"{_LULC_CLASS} {value}\n")
    for name, value in _SOIL_TABLES.items():
        with open(os.path.join(txt_dir, "soil", f"{name}.txt"), "w", encoding="utf8") as f:
            f.write(f"{_SOIL_CLASS} {value}\n")
    with open(os.path.join(txt_dir, "rainydays.txt"), "w", encoding="utf8") as f:
        for month in range(1, 13):
            f.write(f"{month}\t{10 + month % 3}\n")

    output_dir = os.path.join(base_dir, "out")
    os.makedirs(output_dir, exist_ok=True)
    maps = os.path.join(base_dir, "maps")
    return {
        "SIM_TIME": {"start": "01/01/2000", "end": f"01/{timesteps:02d}/2000"},
        "DIRECTORIES": {
            "output": output_dir,
            "etp": os.path.join(maps, "etp/"),
            "prec": os.path.join(maps, "rain/"),
            "ndvi": os.path.join(maps, "ndvi/"),
            "kp": os.path.join(maps, "kp/"),
            "landuse": os.path.join(maps, "lulc/"),
        },
        "FILENAME_PREFIXES": {
            "etp_prefix": "etp",
            "prec_prefix": "prec",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob",
        },
        "RASTERS": {
            "dem": os.path.join(maps, "dem/dem.map"),
            "clone": os.path.join(maps, "clone/clone.map"),
            "ldd": os.path.join(maps, "ldd/ldd.map"),
            "ndvi_max": os.path.join(maps, "ndvi/ndvi_max.map"),
            "ndvi_min": os.path.join(maps, "ndvi/ndvi_min.map"),
            "soil": os.path.join(maps, "soil/soil.map"),
            "samples": os.path.join(maps, "samples/samples.map"),
        },
        "TABLES": {
            "rainydays": os.path.join(txt_dir, "rainydays.txt"),
            "a_i": os.path.join(txt_dir, "lulc/a_i.txt"),
            "a_o": os.path.join(txt_dir, "lulc/a_o.txt"),
            "a_s": os.path.join(txt_dir, "lulc/a_s.txt"),
            "a_v": os.path.join(txt_dir, "lulc/a_v.txt"),
            "manning": os.path.join(txt_dir, "lulc/manning.txt"),
            "bulk_density": os.path.join(txt_dir, "soil/dg.txt"),
            "k_sat": os.path.join(txt_dir, "soil/Kr.txt"),
            "t_fcap": os.path.join(txt_dir, "soil/Tcc.txt"),
            "t_sat": os.path.join(txt_dir, "soil/Tsat.txt"),
            "t_wp": os.path.join(txt_dir, "soil/Tw.txt"),
            "rootzone_depth": os.path.join(txt_dir, "soil/Zr.txt"),
            "k_c_min": os.path.join(txt_dir, "lulc/kcmin.txt"),
            "k_c_max": os.path.join(txt_dir, "lulc/kcmax.txt"),
        },
        "GRID": {"grid": CELL_SIZE},
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
