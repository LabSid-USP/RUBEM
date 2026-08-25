import logging
import math
from collections.abc import Iterable

from osgeo import gdal, osr
from pydantic import BaseModel, ConfigDict, Field

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


class OutputRasterBase(BaseModel):
    """Geometry and coordinate reference system of the output raster series.

    The geometry (size and affine transform) comes from the DEM, which every
    other raster of the simulation must share. A separate georeference raster
    may supply the coordinate reference system, and its geometry must equal
    the DEM's in every one of the six affine components; when both carry a
    CRS, they must describe the same one.

    Build it with :meth:`from_file` (or the equivalent positional call
    ``OutputRasterBase(dem_path, ...)``).

    :param cols: Number of columns.
    :param rows: Number of rows.
    :param transformation: The six affine components (GDAL order).
    :param projection: CRS as WKT, empty when unknown.
    :param base_raster: Path of the DEM the geometry was read from.
    :param georeference: Path of the georeference raster, if any.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cols: int = Field(gt=0)
    rows: int = Field(gt=0)
    transformation: tuple[float, float, float, float, float, float]
    projection: str = ""
    base_raster: str = ""
    georeference: str | None = None

    def __init__(
        self,
        base_raster_path: PathInput | None = None,
        georeference_path: PathInput | None = None,
        must_match: Iterable[tuple[str, PathInput]] = (),
        allow_rotation: bool = True,
        **data,
    ) -> None:
        if base_raster_path is not None:
            data = OutputRasterBase._read(
                base_raster_path, georeference_path, must_match, allow_rotation
            )
        super().__init__(**data)

    @classmethod
    def from_file(
        cls,
        base_raster_path: PathInput,
        georeference_path: PathInput | None = None,
        must_match: Iterable[tuple[str, PathInput]] = (),
        allow_rotation: bool = True,
    ) -> "OutputRasterBase":
        """Read the geometry from the DEM and check the related rasters.

        :param base_raster_path: The DEM.
        :param georeference_path: Optional raster whose CRS is written to the
            output GeoTIFFs. Defaults to ``None``: the DEM's own CRS, if any.
        :param must_match: ``(label, path)`` pairs of rasters that must share
            the DEM geometry (the clone, for instance).
        :param allow_rotation: Whether a rotated or sheared affine transform
            is acceptable. PCRaster maps are north-up only, so a run that
            writes them must refuse rotation.

        :raises ValueError: On a geometry, CRS or rotation mismatch.
        """
        return cls(**cls._read(base_raster_path, georeference_path, must_match, allow_rotation))

    @staticmethod
    def _read(
        base_raster_path: PathInput,
        georeference_path: PathInput | None,
        must_match: Iterable[tuple[str, PathInput]],
        allow_rotation: bool,
    ) -> dict:
        logger = logging.getLogger(__name__)
        cols, rows, transformation, projection = read_raster_geometry(base_raster_path)
        base_raster = str(as_path(base_raster_path))
        georeference = None

        def check_geometry(label: str, path: PathInput) -> tuple[int, int, tuple, str]:
            other = read_raster_geometry(path)
            other_cols, other_rows, other_transformation, _ = other
            if (other_cols, other_rows) != (cols, rows) or not all(
                math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
                for a, b in zip(other_transformation, transformation)
            ):
                raise ValueError(
                    f"The {label} raster {as_path(path)} does not share the DEM geometry: "
                    f"{other_cols}x{other_rows} cells with transform {other_transformation}, "
                    f"expected {cols}x{rows} with transform {transformation} ({base_raster})."
                )
            return other

        for label, path in must_match:
            check_geometry(label, path)

        if georeference_path:
            _, _, _, georeference_projection = check_geometry("georeference", georeference_path)
            if (
                georeference_projection
                and projection
                and not same_crs(projection, georeference_projection)
            ):
                raise ValueError(
                    f"The georeference raster {as_path(georeference_path)} and the DEM "
                    f"{base_raster} have different coordinate reference systems."
                )
            if not georeference_projection:
                logger.warning(
                    "Georeference raster %s carries no coordinate reference system.",
                    as_path(georeference_path),
                )
            projection = georeference_projection or projection
            georeference = str(as_path(georeference_path))

        if not allow_rotation and (transformation[2] != 0 or transformation[4] != 0):
            raise ValueError(
                f"The raster geometry of {base_raster} is rotated or sheared "
                f"(transform {transformation}); PCRaster maps are north-up only. "
                "Disable RASTER_FILE_FORMAT.map_raster_series or use an axis-aligned grid."
            )

        return {
            "cols": cols,
            "rows": rows,
            "transformation": transformation,
            "projection": projection,
            "base_raster": base_raster,
            "georeference": georeference,
        }

    @property
    def is_rotated(self) -> bool:
        """Whether the affine transform has rotation or shear terms."""
        return self.transformation[2] != 0 or self.transformation[4] != 0
