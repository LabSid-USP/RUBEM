"""Raster input and output shared by the preprocessing tools.

The contracts every tool follows:

* a raster is read once into a :class:`RasterData` (array, no-data value,
  geotransform, projection) and the GDAL dataset is closed immediately;
* outputs are written to a temporary file next to the destination and renamed
  into place, so a failed run never leaves a half-written raster behind;
* series are ordered naturally (``etp2`` before ``etp10``), two inputs may not
  map onto the same output name, and every raster of a series must share the
  geometry of the first one;
* an all-no-data raster is handled according to an explicit policy;
* a valid cell may never equal the chosen no-data value, or it would read
  back as missing;
* when a tool writes a directory of outputs, ``manifest.csv`` (source, target)
  is written last, so its presence means the run completed.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.csv"


class PreprocessingError(ValueError):
    """A preprocessing tool cannot proceed with the given inputs."""


class ValueScale(StrEnum):
    """PCRaster value scales the tools can write."""

    BOOLEAN = "boolean"
    NOMINAL = "nominal"
    ORDINAL = "ordinal"
    SCALAR = "scalar"
    DIRECTIONAL = "directional"
    LDD = "ldd"


class AllNoDataPolicy(StrEnum):
    """What to do with a raster whose cells are all missing."""

    ERROR = "error"
    WARN = "warn"
    SKIP = "skip"


@dataclass(frozen=True)
class RasterData:
    """The content and geometry of one single-band raster."""

    array: np.ndarray
    nodata: float | None
    geotransform: tuple[float, float, float, float, float, float]
    projection: str
    source: str = ""

    @property
    def rows(self) -> int:
        return int(self.array.shape[0])

    @property
    def cols(self) -> int:
        return int(self.array.shape[1])

    @property
    def cell_size(self) -> float:
        return float(self.geotransform[1])

    @property
    def west(self) -> float:
        return float(self.geotransform[0])

    @property
    def north(self) -> float:
        return float(self.geotransform[3])

    @property
    def is_rotated(self) -> bool:
        return self.geotransform[2] != 0 or self.geotransform[4] != 0

    def mask(self) -> np.ndarray:
        """Boolean array, ``True`` on the cells that carry data."""
        valid = (
            np.isfinite(self.array)
            if self.array.dtype.kind == "f"
            else np.ones(self.array.shape, bool)
        )
        if self.nodata is not None:
            valid &= self.array != self.nodata
        return valid

    def all_nodata(self) -> bool:
        return not self.mask().any()


def _gdal():
    from osgeo import gdal

    gdal.UseExceptions()
    gdal.AllRegister()
    return gdal


def read_raster(path: PathInput, band: int = 1) -> RasterData:
    """Read one band of a GDAL-readable raster and close it.

    :raises FileNotFoundError: If the file does not exist.
    :raises PreprocessingError: If the raster cannot be opened or has no such band.
    """
    file = as_path(path)
    if not file.is_file():
        raise FileNotFoundError(f"Raster not found: {file}")
    gdal = _gdal()
    try:
        dataset = gdal.OpenEx(str(file), gdal.GA_ReadOnly)
    except RuntimeError as e:
        raise PreprocessingError(f"{file} cannot be opened as a raster: {e}") from e
    try:
        if band < 1 or band > dataset.RasterCount:
            raise PreprocessingError(
                f"{file} has {dataset.RasterCount} band(s); band {band} does not exist."
            )
        raster_band = dataset.GetRasterBand(band)
        return RasterData(
            array=raster_band.ReadAsArray(),
            nodata=raster_band.GetNoDataValue(),
            geotransform=tuple(dataset.GetGeoTransform()),
            projection=dataset.GetProjection() or "",
            source=str(file),
        )
    finally:
        dataset = None


def check_same_geometry(reference: RasterData, other: RasterData, label: str) -> None:
    """Raise :class:`PreprocessingError` unless both rasters share size, transform and CRS.

    The coordinate reference system is only compared when both rasters carry
    one; a raster with no CRS at all never conflicts with one that has it.
    """
    same_size = reference.array.shape == other.array.shape
    same_transform = all(
        abs(a - b) <= 1e-9 * max(1.0, abs(a))
        for a, b in zip(reference.geotransform, other.geotransform)
    )
    if not (same_size and same_transform):
        raise PreprocessingError(
            f"{label}: {other.source or 'raster'} ({other.array.shape[1]}x{other.array.shape[0]}, "
            f"transform {other.geotransform}) does not share the geometry of "
            f"{reference.source or 'the reference'} ({reference.cols}x{reference.rows}, "
            f"transform {reference.geotransform})."
        )
    if reference.projection and other.projection:
        from ..configuration.output_raster_base import same_crs

        if not same_crs(reference.projection, other.projection):
            raise PreprocessingError(
                f"{label}: {other.source or 'raster'} and {reference.source or 'the reference'} "
                "have different coordinate reference systems."
            )


def check_nodata_collision(
    array: np.ndarray, valid_mask: np.ndarray, nodata: float | None, label: str
) -> None:
    """Raise :class:`PreprocessingError` if a valid cell already equals ``nodata``.

    Writing ``nodata`` as the missing-value sentinel while a valid cell holds
    that exact value would make the valid cell indistinguishable from a
    missing one on read, silently erasing it. Call this before writing.
    """
    if nodata is None:
        return
    colliding = int(np.count_nonzero(np.asarray(valid_mask) & (np.asarray(array) == nodata)))
    if colliding:
        raise PreprocessingError(
            f"{label}: {colliding} valid cell(s) already equal the no-data value {nodata}; "
            "they would be read back as missing. Choose a different no-data value."
        )


def apply_all_nodata_policy(raster: RasterData, policy: AllNoDataPolicy, label: str) -> bool:
    """Return whether ``raster`` should be processed.

    ``error`` raises, ``warn`` logs and processes, ``skip`` logs and returns ``False``.
    """
    if not raster.all_nodata():
        return True
    message = f"{label}: every cell of {raster.source or 'the raster'} is missing."
    if policy is AllNoDataPolicy.ERROR:
        raise PreprocessingError(message)
    logger.warning("%s%s", message, " Skipped." if policy is AllNoDataPolicy.SKIP else "")
    return policy is not AllNoDataPolicy.SKIP


_NUMBER_RUN = re.compile(r"(\d+)")


def natural_key(name: str) -> list:
    """Sort key that orders embedded numbers numerically (``etp2`` before ``etp10``)."""
    return [int(part) if part.isdigit() else part.lower() for part in _NUMBER_RUN.split(name)]


def natural_sorted(paths: Iterable[PathInput]) -> list[Path]:
    """The paths in natural order of their file names."""
    return sorted((as_path(p) for p in paths), key=lambda p: natural_key(p.name))


def check_no_collisions(targets: Sequence[tuple[PathInput, PathInput]]) -> None:
    """Raise :class:`PreprocessingError` when two sources map onto one target."""
    seen: dict[Path, Path] = {}
    for source, target in targets:
        target_path = as_path(target).absolute()
        source_path = as_path(source)
        if target_path in seen:
            raise PreprocessingError(
                f"{source_path} and {seen[target_path]} would both be written to {target_path}."
            )
        seen[target_path] = source_path


class AtomicOutput:
    """A destination written through a temporary file in the same directory.

    Use as a context manager: the body writes to ``temporary``; on success the
    temporary file replaces the destination, on failure it is removed.
    """

    def __init__(self, destination: PathInput) -> None:
        self.destination = as_path(destination)
        self.temporary: Path | None = None

    def __enter__(self) -> Path:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(
            prefix=f".{self.destination.name}.", suffix=".tmp", dir=self.destination.parent
        )
        os.close(handle)
        self.temporary = Path(name)
        return self.temporary

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        assert self.temporary is not None
        if exc_type is None:
            self.temporary.replace(self.destination)
        else:
            self.temporary.unlink(missing_ok=True)


GDAL_TYPE_BY_SCALE = {
    ValueScale.BOOLEAN: "Byte",
    ValueScale.NOMINAL: "Int32",
    ValueScale.ORDINAL: "Int32",
    ValueScale.SCALAR: "Float32",
    ValueScale.DIRECTIONAL: "Float32",
    ValueScale.LDD: "Byte",
}


def write_geotiff(
    destination: PathInput,
    array: np.ndarray,
    geotransform: Sequence[float],
    projection: str = "",
    nodata: float | None = None,
    gdal_type: str | None = None,
) -> Path:
    """Write a single-band LZW GeoTIFF atomically and return its path.

    :param gdal_type: GDAL data type name (``Float32``, ``Int32``, ``Byte``, ...);
        defaults to the type matching the array.
    """
    gdal = _gdal()
    from osgeo import gdal_array

    type_code = (
        gdal.GetDataTypeByName(gdal_type)
        if gdal_type
        else gdal_array.NumericTypeCodeToGDALTypeCode(array.dtype)
    )
    if not type_code:
        raise PreprocessingError(f"Unsupported data type for GeoTIFF: {gdal_type or array.dtype}")
    with AtomicOutput(destination) as temporary:
        # GDAL derives the driver from the extension of the final name; the
        # temporary file keeps it after the destination name.
        dataset = gdal.GetDriverByName("GTiff").Create(
            str(temporary), array.shape[1], array.shape[0], 1, type_code, options=["COMPRESS=LZW"]
        )
        try:
            band = dataset.GetRasterBand(1)
            if nodata is not None:
                band.SetNoDataValue(float(nodata))
            band.WriteArray(array)
            dataset.SetGeoTransform(tuple(float(v) for v in geotransform))
            if projection:
                dataset.SetProjection(projection)
            dataset.FlushCache()
        finally:
            dataset = None
    return as_path(destination)


def write_pcraster_map(
    destination: PathInput,
    array: np.ndarray,
    value_scale: ValueScale,
    geotransform: Sequence[float],
    nodata: float | None = None,
) -> Path:
    """Write a PCRaster map atomically from an array, on the given north-up geometry.

    PCRaster maps are north-up only, with axes that increase east and north
    (``cell_x > 0``, ``cell_y < 0``); a rotated, sheared, south-up or mirrored
    transform is refused. Cells equal to ``nodata`` (or not finite) become
    missing values.
    """
    import pcraster as pcr

    west, cell, rotation_x, north, rotation_y, cell_y = (float(v) for v in geotransform)
    if rotation_x != 0 or rotation_y != 0:
        raise PreprocessingError("PCRaster maps are north-up only; the geometry is rotated.")
    if cell <= 0 or cell_y >= 0:
        raise PreprocessingError(
            "PCRaster maps need a north-up, non-mirrored geometry: cell_x > 0 and cell_y < 0, "
            f"got cell_x={cell} and cell_y={cell_y}."
        )
    if abs(abs(cell_y) - cell) > 1e-9 * max(1.0, cell):
        raise PreprocessingError("PCRaster maps need square cells.")
    scale = {
        ValueScale.BOOLEAN: pcr.Boolean,
        ValueScale.NOMINAL: pcr.Nominal,
        ValueScale.ORDINAL: pcr.Ordinal,
        ValueScale.SCALAR: pcr.Scalar,
        ValueScale.DIRECTIONAL: pcr.Directional,
        ValueScale.LDD: pcr.Ldd,
    }[value_scale]
    rows, cols = array.shape
    pcr.setclone(rows, cols, cell, west, north)
    floating = value_scale in (ValueScale.SCALAR, ValueScale.DIRECTIONAL)
    data = np.array(array, dtype=np.float64 if floating else np.int32)
    missing = -9999.0 if floating else -9999
    invalid = ~np.isfinite(np.asarray(array, dtype=float))
    if nodata is not None:
        invalid |= np.asarray(array) == nodata
    data[invalid] = missing
    field = pcr.numpy2pcr(scale, data, missing)
    with AtomicOutput(destination) as temporary:
        pcr.report(field, str(temporary))
    return as_path(destination)


def dtype_for_nodata(dtype: np.dtype, nodata: float) -> np.dtype:
    """The smallest dtype no narrower than ``dtype`` that can also hold ``nodata``.

    :raises PreprocessingError: If ``nodata`` has a fractional part and
        ``dtype`` is an integer dtype (a Boolean, Nominal, Ordinal or LDD
        value scale cannot represent it).
    """
    dtype = np.dtype(dtype)
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


def remove_stale_manifest(directory: PathInput) -> None:
    """Delete a leftover ``manifest.csv`` so its presence implies a completed run.

    Every tool that writes a manifest calls this before its first output: a
    rerun that fails midway must not leave the previous run's manifest
    announcing a complete set.
    """
    (as_path(directory) / MANIFEST_NAME).unlink(missing_ok=True)


def write_manifest(directory: PathInput, rows: Iterable[tuple[str, str]]) -> Path:
    """Write ``manifest.csv`` (source, target) atomically; call it last."""
    manifest = as_path(directory) / MANIFEST_NAME
    with AtomicOutput(manifest) as temporary:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["source", "target"])
            writer.writerows(rows)
    return manifest
