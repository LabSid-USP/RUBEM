"""Structured comparison helpers for the regression oracle.

``compare_rasters`` and ``compare_csv`` return a :class:`CompareResult` whose
``differences`` list explains every mismatch, so a failing assertion can print
``result.report()`` instead of a bare ``False``. Value comparisons always use
explicit ``rtol``/``atol``; raster comparisons honor nodata masks (NaN-aware)
and check geotransform components and the CRS.

The default tolerances absorb Float32 noise between environments: comparing
goldens across PCRaster/GDAL/Python builds shows differences up to ~3e-5 in
absolute value on variables that no input change touches, so tighter defaults
would flag pure environment noise. Real regressions sit orders of magnitude
above 1e-5 relative; byte identity is asserted only by the ``exact`` job on
the environment frozen in ``ci/golden-env.lock``.
"""

import hashlib
import os
from dataclasses import dataclass, field
from typing import Union

import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
osr.UseExceptions()

PathLike = Union[str, bytes, os.PathLike]

DEFAULT_RTOL = 1e-5
DEFAULT_ATOL = 1e-8
RASTER_FIELDS = ("bands", "shape", "nodata", "values", "geotransform", "projection")


@dataclass
class Difference:
    """A single mismatch between the two compared files."""

    field: str
    message: str

    def __str__(self):
        return f"[{self.field}] {self.message}"


@dataclass
class CompareResult:
    """Outcome of a comparison: ``equal`` plus the list of differences."""

    equal: bool
    differences: list = field(default_factory=list)

    def report(self):
        if self.equal:
            return "files are equal"
        return "\n".join(str(difference) for difference in self.differences)

    def __bool__(self):
        return self.equal


def sha256_of(path):
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nodata_mask(array, nodata):
    if nodata is None:
        return np.zeros(array.shape, dtype=bool)
    if np.isnan(nodata):
        return np.isnan(array)
    return np.isclose(array, nodata, rtol=0.0, atol=0.0)


def _require_file(path, label):
    if not path:
        raise ValueError(f"The {label} path is required.")
    if not os.path.isfile(str(path)):
        raise FileNotFoundError(f"The {label} file {path} does not exist.")


def _open_raster(path):
    try:
        dataset = gdal.OpenEx(str(path), gdal.OF_RASTER | gdal.OF_READONLY)
    except RuntimeError as error:
        raise ValueError(f"GDAL cannot open {path}: {error}") from error
    if dataset is None:
        raise ValueError(f"GDAL cannot open {path}.")
    return dataset


def _compare_projections(projection1, projection2, differences):
    if not projection1 and not projection2:
        return
    if bool(projection1) != bool(projection2):
        differences.append(
            Difference(
                "projection",
                f"one raster has no CRS: {projection1 or '<none>'!r} vs "
                f"{projection2 or '<none>'!r}",
            )
        )
        return
    reference1 = osr.SpatialReference()
    reference1.ImportFromWkt(projection1)
    reference2 = osr.SpatialReference()
    reference2.ImportFromWkt(projection2)
    if not reference1.IsSame(reference2):
        differences.append(
            Difference(
                "projection",
                f"CRS differ: {reference1.GetName()!r} vs {reference2.GetName()!r}",
            )
        )


def compare_rasters(
    raster1_path: PathLike,
    raster2_path: PathLike,
    *,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
    fields=RASTER_FIELDS,
) -> CompareResult:
    """Compare two rasters field by field.

    :param fields: Which aspects to compare; any subset of
        ``("bands", "shape", "nodata", "values", "geotransform", "projection")``.
    """
    _require_file(raster1_path, "first raster")
    _require_file(raster2_path, "second raster")

    differences = []
    raster1 = _open_raster(raster1_path)
    raster2 = _open_raster(raster2_path)
    try:
        if "bands" in fields and raster1.RasterCount != raster2.RasterCount:
            differences.append(
                Difference(
                    "bands",
                    f"band count {raster1.RasterCount} vs {raster2.RasterCount}",
                )
            )
        if "geotransform" in fields:
            geotransform1 = raster1.GetGeoTransform()
            geotransform2 = raster2.GetGeoTransform()
            for index, (component1, component2) in enumerate(
                zip(geotransform1, geotransform2)
            ):
                if not np.isclose(component1, component2, rtol=rtol, atol=atol):
                    differences.append(
                        Difference(
                            "geotransform",
                            f"component {index}: {component1!r} vs {component2!r}",
                        )
                    )
        if "projection" in fields:
            _compare_projections(
                raster1.GetProjection(), raster2.GetProjection(), differences
            )

        for band_index in range(1, min(raster1.RasterCount, raster2.RasterCount) + 1):
            band1 = raster1.GetRasterBand(band_index)
            band2 = raster2.GetRasterBand(band_index)
            array1 = band1.ReadAsArray()
            array2 = band2.ReadAsArray()
            nodata1 = band1.GetNoDataValue()
            nodata2 = band2.GetNoDataValue()

            if "nodata" in fields and not (
                (nodata1 is None and nodata2 is None)
                or (
                    nodata1 is not None
                    and nodata2 is not None
                    and np.isclose(nodata1, nodata2, rtol=0.0, atol=0.0, equal_nan=True)
                )
            ):
                differences.append(
                    Difference(
                        "nodata", f"band {band_index}: {nodata1!r} vs {nodata2!r}"
                    )
                )

            if "shape" in fields and array1.shape != array2.shape:
                differences.append(
                    Difference(
                        "shape",
                        f"band {band_index}: {array1.shape} vs {array2.shape}",
                    )
                )
                continue

            if "values" in fields and array1.shape == array2.shape:
                mask1 = _nodata_mask(array1, nodata1)
                mask2 = _nodata_mask(array2, nodata2)
                if not np.array_equal(mask1, mask2):
                    differences.append(
                        Difference(
                            "values",
                            f"band {band_index}: nodata masks differ on "
                            f"{int(np.count_nonzero(mask1 != mask2))} cell(s)",
                        )
                    )
                valid = ~(mask1 | mask2)
                if valid.any():
                    values1 = array1[valid].astype(np.float64)
                    values2 = array2[valid].astype(np.float64)
                    close = np.isclose(values1, values2, rtol=rtol, atol=atol, equal_nan=True)
                    if not close.all():
                        max_abs_diff = float(np.max(np.abs(values1 - values2)))
                        differences.append(
                            Difference(
                                "values",
                                f"band {band_index}: "
                                f"{int(np.count_nonzero(~close))}/{values1.size} "
                                f"cell(s) beyond rtol={rtol}, atol={atol}; "
                                f"max abs diff {max_abs_diff:.3e}",
                            )
                        )
    finally:
        raster1 = None
        raster2 = None

    return CompareResult(equal=not differences, differences=differences)


def compare_csv(
    csv1_path: PathLike,
    csv2_path: PathLike,
    *,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
    delimiter: str = ";",
) -> CompareResult:
    """Compare two delimited numeric files (header line ignored)."""
    _require_file(csv1_path, "first CSV")
    _require_file(csv2_path, "second CSV")

    differences = []
    data1 = np.genfromtxt(str(csv1_path), delimiter=delimiter, skip_header=1)
    data2 = np.genfromtxt(str(csv2_path), delimiter=delimiter, skip_header=1)
    data1 = np.atleast_2d(data1)
    data2 = np.atleast_2d(data2)

    if data1.shape != data2.shape:
        differences.append(Difference("shape", f"{data1.shape} vs {data2.shape}"))
    else:
        nan1 = np.isnan(data1)
        nan2 = np.isnan(data2)
        if not np.array_equal(nan1, nan2):
            differences.append(
                Difference(
                    "values",
                    f"NaN patterns differ on {int(np.count_nonzero(nan1 != nan2))} "
                    "cell(s)",
                )
            )
        valid = ~(nan1 | nan2)
        if valid.any():
            close = np.isclose(data1[valid], data2[valid], rtol=rtol, atol=atol)
            if not close.all():
                max_abs_diff = float(np.max(np.abs(data1[valid] - data2[valid])))
                differences.append(
                    Difference(
                        "values",
                        f"{int(np.count_nonzero(~close))}/{int(valid.sum())} "
                        f"value(s) beyond rtol={rtol}, atol={atol}; "
                        f"max abs diff {max_abs_diff:.3e}",
                    )
                )

    return CompareResult(equal=not differences, differences=differences)
