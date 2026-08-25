"""The ``rubem preprocess`` sub-application.

Only the standard library and Typer are imported at module level, so that
``rubem preprocess --help`` works in an environment without PCRaster and GDAL;
each command imports what it needs when it runs.
"""

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    help="Prepare model inputs: inspect and convert rasters, build series, interpolate stations.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def info(
    raster: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="A raster file.")],
) -> None:
    """Print the geometry, no-data value and type of a raster."""
    from .._deps import require_runtime_deps

    require_runtime_deps()
    from ._io import read_raster

    data = read_raster(raster)
    valid = data.mask()
    print(f"File: {data.source}")
    print(f"Size: {data.cols} columns x {data.rows} rows")
    print(f"Cell: {data.cell_size} (west {data.west}, north {data.north})")
    print(f"Rotated: {'yes' if data.is_rotated else 'no'}")
    print(f"Type: {data.array.dtype}")
    print(f"No-data value: {data.nodata}")
    print(f"Valid cells: {int(valid.sum())} of {valid.size}")
    if valid.any():
        values = data.array[valid]
        print(f"Range: {values.min()} to {values.max()}")
    print(f"Projection: {data.projection or 'none'}")


@app.command("tif2map")
def tif2map_command(
    inputs: Annotated[
        list[Path],
        typer.Argument(exists=True, help="GeoTIFF files or directories of GeoTIFF files."),
    ],
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "-o", "--output-dir", help="Where to write the maps (default: next to each input)."
        ),
    ] = None,
    value_scale: Annotated[
        str, typer.Option("--value-scale", help="PCRaster value scale of the maps.")
    ] = "scalar",
    all_nodata: Annotated[
        str,
        typer.Option(
            "--all-nodata", help="What to do with an all-no-data raster: error, warn or skip."
        ),
    ] = "error",
) -> None:
    """Convert GeoTIFF files to PCRaster maps."""
    from .._deps import require_runtime_deps

    require_runtime_deps()
    from ._io import AllNoDataPolicy, ValueScale
    from .conversions import tif2map

    for path in _run(
        lambda: tif2map(inputs, output_dir, ValueScale(value_scale), AllNoDataPolicy(all_nodata))
    ):
        print(path)


@app.command("tif2mapseries")
def tif2mapseries_command(
    input_dir: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, help="Directory of GeoTIFF files.")
    ],
    prefix: Annotated[str, typer.Option("--prefix", help="Series prefix (at most 7 characters).")],
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "-o", "--output-dir", help="Where to write the series (default: the input directory)."
        ),
    ] = None,
    clone: Annotated[
        Path | None,
        typer.Option(
            "--clone",
            exists=True,
            dir_okay=False,
            help="Raster whose geometry every file must share.",
        ),
    ] = None,
    value_scale: Annotated[
        str, typer.Option("--value-scale", help="PCRaster value scale of the maps.")
    ] = "scalar",
    all_nodata: Annotated[
        str,
        typer.Option(
            "--all-nodata", help="What to do with an all-no-data raster: error, warn or skip."
        ),
    ] = "error",
    first_step: Annotated[
        int, typer.Option("--first-step", min=1, help="Step number of the first file.")
    ] = 1,
) -> None:
    """Convert a directory of GeoTIFF files to a PCRaster map series."""
    from .._deps import require_runtime_deps

    require_runtime_deps()
    from ._io import AllNoDataPolicy, ValueScale
    from .conversions import tif2mapseries

    for path in _run(
        lambda: tif2mapseries(
            input_dir,
            prefix,
            output_dir,
            clone,
            ValueScale(value_scale),
            AllNoDataPolicy(all_nodata),
            first_step,
        )
    ):
        print(path)


@app.command("mapseries2tif")
def mapseries2tif_command(
    input_dir: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, help="Directory of the map series.")
    ],
    prefix: Annotated[str, typer.Option("--prefix", help="Series prefix.")],
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output-dir",
            help="Where to write the GeoTIFF files (default: the input directory).",
        ),
    ] = None,
    georeference: Annotated[
        Path | None,
        typer.Option(
            "--georeference",
            exists=True,
            dir_okay=False,
            help="Raster whose coordinate reference system is written.",
        ),
    ] = None,
    nodata: Annotated[
        float, typer.Option("--nodata", help="No-data value of the GeoTIFF files.")
    ] = -9999.0,
) -> None:
    """Convert a PCRaster map series to GeoTIFF files."""
    from .._deps import require_runtime_deps

    require_runtime_deps()
    from .conversions import mapseries2tif

    for path in _run(lambda: mapseries2tif(input_dir, prefix, output_dir, georeference, nodata)):
        print(path)


@app.command("minmax")
def minmax_command(
    inputs: Annotated[
        list[Path],
        typer.Argument(
            exists=True, help="GeoTIFF files or directories of GeoTIFF files (the series)."
        ),
    ],
    minimum: Annotated[Path, typer.Option("--min", help="Minimum GeoTIFF to write.")],
    maximum: Annotated[Path, typer.Option("--max", help="Maximum GeoTIFF to write.")],
    georeference: Annotated[
        Path | None,
        typer.Option(
            "--georeference",
            exists=True,
            dir_okay=False,
            help="Raster whose geometry and CRS the outputs follow.",
        ),
    ] = None,
    nodata: Annotated[
        float, typer.Option("--nodata", help="No-data value of the outputs.")
    ] = -9999.0,
) -> None:
    """Write the per-cell minimum and maximum of a raster series (for NDVI extremes)."""
    from .._deps import require_runtime_deps

    require_runtime_deps()
    from .minmax_series import minmax

    for path in _run(lambda: minmax(inputs, minimum, maximum, georeference, nodata)):
        print(path)


@app.command("krige")
def krige_command(
    stations: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="Station file (CSV).")
    ],
    clone: Annotated[
        Path,
        typer.Option(
            "--clone", exists=True, dir_okay=False, help="Raster whose grid the maps follow."
        ),
    ],
    output_dir: Annotated[
        Path, typer.Option("-o", "--output-dir", help="Where to write the map series.")
    ],
    prefix: Annotated[str, typer.Option("--prefix", help="Series prefix (at most 7 characters).")],
    stations_format: Annotated[
        str,
        typer.Option(
            "--stations-format", help="matrix (x;y;v1;v2;...) or long (step;id;x;y;value)."
        ),
    ] = "matrix",
    delimiter: Annotated[
        str, typer.Option("--delimiter", help="Column delimiter of the station file.")
    ] = ";",
    steps: Annotated[
        int | None, typer.Option("--steps", min=1, help="Steps to interpolate (default: all).")
    ] = None,
    first_step: Annotated[
        int, typer.Option("--first-step", min=1, help="Step number of the first map.")
    ] = 1,
    negative_policy: Annotated[
        str,
        typer.Option(
            "--negative-policy", help="Negative interpolated values: clamp, keep or error."
        ),
    ] = "clamp",
    coordinates_type: Annotated[
        str,
        typer.Option(
            "--coordinates-type",
            help="Kriging metric: auto (from the clone CRS), geographic or euclidean.",
        ),
    ] = "auto",
    variogram_model: Annotated[
        str, typer.Option("--variogram-model", help="PyKrige variogram model.")
    ] = "spherical",
    n_lags: Annotated[
        int, typer.Option("--n-lags", min=2, help="Number of lags of the empirical variogram.")
    ] = 25,
    seed: Annotated[
        int | None, typer.Option("--seed", help="Random seed for reproducible variogram fits.")
    ] = None,
    nodata: Annotated[
        float, typer.Option("--nodata", help="Missing value written to the maps.")
    ] = -9999.0,
) -> None:
    """Interpolate station series onto the clone grid with ordinary kriging."""
    from .._deps import require_preprocessing_deps, require_runtime_deps

    require_runtime_deps()
    require_preprocessing_deps()
    from .kriging_series import CoordinatesType, NegativePolicy, StationsFormat, krige_file

    def operation():
        return krige_file(
            stations,
            clone,
            output_dir,
            prefix,
            StationsFormat(stations_format),
            delimiter,
            steps=steps,
            first_step=first_step,
            negative_policy=NegativePolicy(negative_policy),
            coordinates_type=CoordinatesType(coordinates_type),
            variogram_model=variogram_model,
            n_lags=n_lags,
            seed=seed,
            nodata=nodata,
        )

    for path in _run(operation):
        print(path)


def _run(operation):
    """Run a tool, turning its input errors into a clean exit."""
    import logging

    from ._io import PreprocessingError

    try:
        return operation()
    except (PreprocessingError, FileNotFoundError, NotADirectoryError, ValueError) as e:
        logging.getLogger(__name__).critical("%s", e)
        raise typer.Exit(code=1) from e
