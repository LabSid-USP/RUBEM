import logging
import math
from collections.abc import Iterable

from osgeo import gdal, osr

from .._paths import PathInput, as_path


def read_raster_geometry(raster_path: PathInput) -> tuple[int, int, tuple, str]:
    """Return ``(cols, rows, geotransform, projection_wkt)`` of a raster.

    Only the header is read; the dataset is closed before returning.

    :raises FileNotFoundError: If the raster does not exist.
    :raises RuntimeError: If GDAL cannot open the raster.
    """
    resolved_path = as_path(raster_path)
    path = str(resolved_path)
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Invalid raster file: {path}")
    gdal.UseExceptions()
    gdal.AllRegister()
    dataset = gdal.OpenEx(path, gdal.GA_ReadOnly)
    try:
        transformation = tuple(dataset.GetGeoTransform())
        if len(transformation) != 6:
            raise ValueError(f"Invalid affine transform {transformation} in {path}")
        return (
            int(dataset.RasterXSize),
            int(dataset.RasterYSize),
            transformation,
            dataset.GetProjection() or "",
        )
    finally:
        dataset = None


def same_crs(first_wkt: str, second_wkt: str) -> bool:
    """Whether two WKT definitions describe the same coordinate reference system."""
    first = osr.SpatialReference()
    first.ImportFromWkt(first_wkt)
    second = osr.SpatialReference()
    second.ImportFromWkt(second_wkt)
    return bool(first.IsSame(second))


class OutputRasterBase:
    """Geometry and coordinate reference system of the output raster series.

    The geometry (size and affine transform) comes from the DEM, which every
    other raster of the simulation must share. A separate georeference raster
    may supply the coordinate reference system, and its geometry must equal
    the DEM's in every one of the six affine components; when both carry a
    CRS, they must describe the same one.

    :param base_raster_path: The DEM.
    :param georeference_path: Optional raster whose CRS is written to the
        output GeoTIFFs. Defaults to ``None``: the DEM's own CRS, if any.
    :param must_match: ``(label, path)`` pairs of rasters that must share the
        DEM geometry (the clone, for instance).
    :param allow_rotation: Whether a rotated or sheared affine transform is
        acceptable. PCRaster maps are north-up only, so a run that writes
        them must refuse rotation.

    :raises ValueError: On a geometry, CRS or rotation mismatch.
    """

    def __init__(
        self,
        base_raster_path: PathInput,
        georeference_path: PathInput | None = None,
        must_match: Iterable[tuple[str, PathInput]] = (),
        allow_rotation: bool = True,
    ):
        self.logger = logging.getLogger(__name__)
        self.cols, self.rows, self.transformation, self.projection = read_raster_geometry(
            base_raster_path
        )
        self.base_raster = str(as_path(base_raster_path))
        self.georeference = None

        for label, path in must_match:
            self.__check_geometry(label, path)

        if georeference_path:
            cols, rows, transformation, projection = self.__check_geometry(
                "georeference", georeference_path
            )
            if projection and self.projection and not same_crs(self.projection, projection):
                raise ValueError(
                    f"The georeference raster {str(as_path(georeference_path))} and the DEM "
                    f"{self.base_raster} have different coordinate reference systems."
                )
            if not projection:
                self.logger.warning(
                    "Georeference raster %s carries no coordinate reference system.",
                    str(as_path(georeference_path)),
                )
            self.projection = projection or self.projection
            self.georeference = str(as_path(georeference_path))

        if not allow_rotation and self.is_rotated:
            raise ValueError(
                f"The raster geometry of {self.base_raster} is rotated or sheared "
                f"(transform {self.transformation}); PCRaster maps are north-up only. "
                "Disable RASTER_FILE_FORMAT.map_raster_series or use an axis-aligned grid."
            )

    @property
    def is_rotated(self) -> bool:
        """Whether the affine transform has rotation or shear terms."""
        return self.transformation[2] != 0 or self.transformation[4] != 0

    def __check_geometry(self, label: str, path: PathInput) -> tuple[int, int, tuple, str]:
        cols, rows, transformation, projection = read_raster_geometry(path)
        if (cols, rows) != (self.cols, self.rows) or not all(
            math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
            for a, b in zip(transformation, self.transformation)
        ):
            raise ValueError(
                f"The {label} raster {str(as_path(path))} does not share the DEM geometry: "
                f"{cols}x{rows} cells with transform {transformation}, expected "
                f"{self.cols}x{self.rows} with transform {self.transformation} "
                f"({self.base_raster})."
            )
        return cols, rows, transformation, projection
