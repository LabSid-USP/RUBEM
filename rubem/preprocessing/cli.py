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
