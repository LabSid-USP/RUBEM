"""Conversions between GeoTIFF files and PCRaster maps and map series."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path
from ..file._naming import get_raster_series_filepath, output_raster_filename, raster_series_pattern
from ._io import (
    MANIFEST_NAME,
    AllNoDataPolicy,
    PreprocessingError,
    RasterData,
    ValueScale,
    apply_all_nodata_policy,
    check_no_collisions,
    check_nodata_collision,
    check_same_geometry,
    natural_sorted,
    read_raster,
    write_geotiff,
    write_manifest,
    write_pcraster_map,
)

logger = logging.getLogger(__name__)

TIFF_SUFFIXES = (".tif", ".tiff")


def _dtype_for_nodata(dtype: np.dtype, nodata: float) -> np.dtype:
    """The smallest dtype no narrower than ``dtype`` that can also hold ``nodata``.

    :raises PreprocessingError: If ``nodata`` has a fractional part and
        ``dtype`` is an integer dtype (a Boolean, Nominal, Ordinal or LDD
        value scale cannot represent it).
    """
    if dtype.kind in "iu":
        if float(nodata) != int(nodata):
            raise PreprocessingError(
                f"No-data value {nodata} is fractional; {dtype} is an integer value scale."
            )
        return np.promote_types(dtype, np.min_scalar_type(int(nodata)))
    # A floating value scale: min_scalar_type is not used here, as it favors
    # float16 for any value inside its exponent range regardless of whether
    # the mantissa can represent it exactly (-9999.0 would round to -10000.0).
    # The round trip is compared as plain Python floats, not as a numpy array
    # against a Python scalar: NEP 50 casts the scalar down to the array's
    # dtype for that comparison, which would call an overflowed inf "equal"
    # to the finite value that produced it.
    if float(dtype.type(nodata)) == float(nodata):
        return dtype
    return np.promote_types(dtype, np.float64)


def _remove_stale_manifest(directory: Path) -> None:
    """Delete a leftover ``manifest.csv`` so its presence implies a completed run."""
    manifest = directory / MANIFEST_NAME
    manifest.unlink(missing_ok=True)


def _tiff_files(inputs: Sequence[PathInput]) -> list[Path]:
    """Expand directories into their GeoTIFF files, in natural order, and check the rest."""
    files: list[Path] = []
    for item in inputs:
        path = as_path(item)
        if path.is_dir():
            files.extend(
                natural_sorted(p for p in path.iterdir() if p.suffix.lower() in TIFF_SUFFIXES)
            )
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"Input not found: {path}")
    if not files:
        raise PreprocessingError("No GeoTIFF file to convert.")
    return files


def tif2map(
    inputs: Sequence[PathInput],
    output_dir: PathInput | None = None,
    value_scale: ValueScale = ValueScale.SCALAR,
    all_nodata: AllNoDataPolicy = AllNoDataPolicy.ERROR,
) -> list[Path]:
    """Convert GeoTIFF files (or directories of them) to PCRaster maps.

    Each output is named after its input with the ``.map`` suffix, in
    ``output_dir`` (default: next to the input). The value scale decides the
    PCRaster type; the source no-data cells become missing values.

    :return: The maps written, in order.
    """
    files = _tiff_files(inputs)
    targets = [
        (
            file,
            (as_path(output_dir) if output_dir is not None else file.parent) / f"{file.stem}.map",
        )
        for file in files
    ]
    check_no_collisions(targets)
    written: list[Path] = []
    for source, target in targets:
        data = read_raster(source)
        if not apply_all_nodata_policy(data, all_nodata, "tif2map"):
            continue
        write_pcraster_map(target, data.array, value_scale, data.geotransform, data.nodata)
        logger.info("Wrote %s", target)
        written.append(target)
    return written


def tif2mapseries(
    input_dir: PathInput,
    prefix: str,
    output_dir: PathInput | None = None,
    clone: PathInput | None = None,
    value_scale: ValueScale = ValueScale.SCALAR,
    all_nodata: AllNoDataPolicy = AllNoDataPolicy.ERROR,
    first_step: int = 1,
) -> list[Path]:
    """Convert a directory of GeoTIFF files to a PCRaster map series.

    The files are taken in natural order and written as ``<prefix>`` plus the
    PCRaster 8.3 step suffix, starting at ``first_step``. Every file must share
    the geometry of the first one (or of ``clone`` when given). A skipped
    all-no-data raster still consumes its step, so the numbering follows the
    file order, but no map is left at its target. ``manifest.csv`` is written
    last, after removing any leftover from an earlier run, so its presence
    means the run completed.

    :return: The maps written, in order.
    """
    files = _tiff_files([input_dir])
    destination = as_path(output_dir) if output_dir is not None else as_path(input_dir)
    reference = read_raster(clone) if clone is not None else None
    targets = [
        (file, Path(get_raster_series_filepath(destination, prefix, first_step + index)))
        for index, file in enumerate(files)
    ]
    check_no_collisions(targets)
    _remove_stale_manifest(destination)
    written: list[Path] = []
    manifest: list[tuple[str, str]] = []
    for source, target in targets:
        data = read_raster(source)
        if reference is None:
            reference = data
        else:
            check_same_geometry(reference, data, "tif2mapseries")
        if not apply_all_nodata_policy(data, all_nodata, "tif2mapseries"):
            target.unlink(missing_ok=True)
            continue
        write_pcraster_map(target, data.array, value_scale, data.geotransform, data.nodata)
        logger.info("Wrote %s", target)
        written.append(target)
        manifest.append((str(source), str(target)))
    write_manifest(destination, manifest)
    return written


def mapseries2tif(
    input_dir: PathInput,
    prefix: str,
    output_dir: PathInput | None = None,
    georeference: PathInput | None = None,
    nodata: float = -9999.0,
) -> list[Path]:
    """Convert a PCRaster map series to GeoTIFF files.

    The members of the series (``<prefix>`` plus the 8.3 step suffix) become
    ``<prefix><step>.tif`` files, named like the model outputs, in
    ``output_dir`` (default: the input directory). ``georeference`` lends its
    coordinate reference system; it must share the series geometry. Without a
    ``georeference``, every member must still share the geometry of the first
    one, but the GeoTIFF files carry no projection. A source value that the
    GeoTIFF band cannot represent (an integer type too narrow for ``nodata``,
    or a fractional ``nodata`` on an integer value scale) promotes the band
    to a type that can. A member is rejected if a valid cell already equals
    ``nodata``, which would make it unreadable as data. ``manifest.csv`` is
    written last, after removing any leftover from an earlier run, so its
    presence means the run completed.

    :return: The GeoTIFF files written, in order.
    """
    directory = as_path(input_dir)
    if not directory.is_dir():
        raise NotADirectoryError(f"Input directory not found: {directory}")
    pattern = raster_series_pattern(prefix)
    members = natural_sorted(
        p for p in directory.iterdir() if p.is_file() and pattern.match(p.name)
    )
    if not members:
        raise PreprocessingError(f"No member of the series '{prefix}' in {directory}.")
    destination = as_path(output_dir) if output_dir is not None else directory
    reference: RasterData | None = read_raster(georeference) if georeference is not None else None
    projection = reference.projection if reference is not None else ""
    targets = []
    for member in members:
        digits = member.name[len(prefix) :].replace(".", "")
        targets.append((member, destination / output_raster_filename(prefix, int(digits), "tif")))
    check_no_collisions(targets)
    _remove_stale_manifest(destination)
    written: list[Path] = []
    manifest: list[tuple[str, str]] = []
    for source, target in targets:
        data = read_raster(source)
        if reference is None:
            reference = data
        else:
            check_same_geometry(reference, data, "mapseries2tif")
        array = data.array
        target_dtype = _dtype_for_nodata(array.dtype, nodata)
        valid = data.mask()
        check_nodata_collision(array, valid, nodata, "mapseries2tif")
        remap = data.nodata is not None and data.nodata != nodata
        if target_dtype != array.dtype:
            array = array.astype(target_dtype)
        elif remap:
            array = array.copy()
        if remap:
            array[~valid] = nodata
        write_geotiff(target, array, data.geotransform, projection, nodata)
        logger.info("Wrote %s", target)
        written.append(target)
        manifest.append((str(source), str(target)))
    write_manifest(destination, manifest)
    return written
