import os
from pathlib import Path

import pytest

from rubem.configuration.output_raster_base import (
    OutputRasterBase,
    read_raster_geometry,
    same_crs,
)
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.config import BASE_DATA_DIR
from tests.helpers.synthetic import CELL_SIZE, COLS, NORTH, ROWS, WEST, write_synthetic_dataset

FIXTURE_DEM_TIF = os.path.join(BASE_DATA_DIR, "maps", "dem", "dem.tif")


class TestOutputRasterBase:
    @pytest.mark.unit
    def test_reads_dimensions_and_transformation_from_pcraster_map(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)

        base_raster = OutputRasterBase(config["RASTERS"]["dem"])

        assert base_raster.cols == COLS
        assert base_raster.rows == ROWS
        transformation = base_raster.transformation
        assert len(transformation) == 6
        assert transformation[0] == pytest.approx(WEST)
        assert transformation[3] == pytest.approx(NORTH)
        assert transformation[1] == pytest.approx(CELL_SIZE)
        assert transformation[5] == pytest.approx(-CELL_SIZE)

    @pytest.mark.unit
    def test_reads_dimensions_and_transformation_from_geotiff(self):
        ensure_gdal_drivers()
        from osgeo import gdal

        base_raster = OutputRasterBase(FIXTURE_DEM_TIF)

        dataset = gdal.OpenEx(FIXTURE_DEM_TIF, gdal.GA_ReadOnly)
        try:
            assert base_raster.cols == dataset.RasterXSize
            assert base_raster.rows == dataset.RasterYSize
            assert base_raster.transformation == dataset.GetGeoTransform()
        finally:
            dataset = None

    @pytest.mark.unit
    def test_accepts_pathlib_path(self):
        base_raster = OutputRasterBase(Path(FIXTURE_DEM_TIF))

        assert base_raster.cols > 0
        assert base_raster.rows > 0

    @pytest.mark.unit
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            OutputRasterBase(tmp_path / "absent.tif")


LOCAL_CRS_WKT = 'LOCAL_CS["Engineering grid",UNIT["metre",1]]'


def write_geotiff(path, cols, rows, transformation, projection=""):
    """Write a small Float32 GeoTIFF with the given geometry and CRS."""
    ensure_gdal_drivers()
    from osgeo import gdal

    gdal.UseExceptions()
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), cols, rows, 1, gdal.GDT_Float32)
    try:
        dataset.SetGeoTransform(transformation)
        if projection:
            dataset.SetProjection(projection)
        dataset.GetRasterBand(1).Fill(1.0)
    finally:
        dataset = None
    return str(path)


def dem_tif_projection():
    return read_raster_geometry(FIXTURE_DEM_TIF)[3]


class TestGeoreference:
    @pytest.mark.unit
    def test_a_map_dem_has_no_crs(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)

        base_raster = OutputRasterBase(config["RASTERS"]["dem"])

        assert base_raster.projection == ""
        assert base_raster.georeference is None

    @pytest.mark.unit
    def test_the_georeference_supplies_the_crs(self, tmp_path):
        """The fixture DEM exists as a CRS-less map and as a WGS 84 GeoTIFF of
        the same geometry; the GeoTIFF lends its CRS to the map."""
        dem_map = os.path.join(BASE_DATA_DIR, "maps", "dem", "dem.map")

        base_raster = OutputRasterBase(dem_map, georeference_path=FIXTURE_DEM_TIF)

        assert base_raster.projection == dem_tif_projection()
        assert "WGS 84" in base_raster.projection
        assert base_raster.georeference == FIXTURE_DEM_TIF

    @pytest.mark.unit
    def test_a_georeference_without_crs_is_accepted_with_a_warning(self, tmp_path, caplog):
        config = write_synthetic_dataset(tmp_path)
        cols, rows, transformation, _ = read_raster_geometry(config["RASTERS"]["dem"])
        georeference = write_geotiff(tmp_path / "georeference.tif", cols, rows, transformation)

        with caplog.at_level("WARNING"):
            base_raster = OutputRasterBase(config["RASTERS"]["dem"], georeference_path=georeference)

        assert base_raster.projection == ""
        assert "carries no coordinate reference system" in caplog.text

    @pytest.mark.unit
    def test_a_georeference_with_another_geometry_is_rejected(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        cols, rows, transformation, _ = read_raster_geometry(config["RASTERS"]["dem"])
        shifted = (transformation[0] + 1.0,) + transformation[1:]
        georeference = write_geotiff(tmp_path / "georeference.tif", cols, rows, shifted)

        with pytest.raises(ValueError, match="does not share the DEM geometry"):
            OutputRasterBase(config["RASTERS"]["dem"], georeference_path=georeference)

    @pytest.mark.unit
    def test_a_georeference_with_another_size_is_rejected(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        cols, rows, transformation, _ = read_raster_geometry(config["RASTERS"]["dem"])
        georeference = write_geotiff(tmp_path / "georeference.tif", cols + 1, rows, transformation)

        with pytest.raises(ValueError, match="does not share the DEM geometry"):
            OutputRasterBase(config["RASTERS"]["dem"], georeference_path=georeference)

    @pytest.mark.unit
    def test_a_georeference_with_another_crs_than_the_dem_is_rejected(self, tmp_path):
        cols, rows, transformation, _ = read_raster_geometry(FIXTURE_DEM_TIF)
        georeference = write_geotiff(
            tmp_path / "georeference.tif", cols, rows, transformation, LOCAL_CRS_WKT
        )

        with pytest.raises(ValueError, match="different coordinate reference systems"):
            OutputRasterBase(FIXTURE_DEM_TIF, georeference_path=georeference)

    @pytest.mark.unit
    def test_the_same_crs_in_both_rasters_is_accepted(self, tmp_path):
        cols, rows, transformation, projection = read_raster_geometry(FIXTURE_DEM_TIF)
        georeference = write_geotiff(
            tmp_path / "georeference.tif", cols, rows, transformation, projection
        )

        base_raster = OutputRasterBase(FIXTURE_DEM_TIF, georeference_path=georeference)

        assert same_crs(base_raster.projection, projection)

    @pytest.mark.unit
    def test_a_missing_georeference_raises(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)

        with pytest.raises(FileNotFoundError):
            OutputRasterBase(config["RASTERS"]["dem"], georeference_path=tmp_path / "absent.tif")


class TestMustMatch:
    @pytest.mark.unit
    def test_the_clone_shares_the_dem_geometry(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)

        OutputRasterBase(
            config["RASTERS"]["dem"], must_match=[("clone", config["RASTERS"]["clone"])]
        )

    @pytest.mark.unit
    def test_a_clone_with_another_geometry_is_rejected(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        cols, rows, transformation, _ = read_raster_geometry(config["RASTERS"]["dem"])
        clone = write_geotiff(tmp_path / "clone.tif", cols, rows + 1, transformation)

        with pytest.raises(ValueError, match="The clone raster .* does not share the DEM geometry"):
            OutputRasterBase(config["RASTERS"]["dem"], must_match=[("clone", clone)])


class TestRotation:
    ROTATED = (0.0, 1.0, 0.1, 3.0, 0.1, -1.0)

    @pytest.mark.unit
    def test_rotation_is_rejected_when_pcraster_maps_are_written(self, tmp_path):
        dem = write_geotiff(tmp_path / "dem.tif", 3, 3, self.ROTATED)

        with pytest.raises(ValueError, match="rotated or sheared"):
            OutputRasterBase(dem, allow_rotation=False)

    @pytest.mark.unit
    def test_rotation_is_accepted_for_geotiff_only_runs(self, tmp_path):
        dem = write_geotiff(tmp_path / "dem.tif", 3, 3, self.ROTATED)

        base_raster = OutputRasterBase(dem, allow_rotation=True)

        assert base_raster.is_rotated
        assert base_raster.transformation == pytest.approx(self.ROTATED)

    @pytest.mark.unit
    def test_an_axis_aligned_grid_is_not_rotated(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)

        assert not OutputRasterBase(config["RASTERS"]["dem"], allow_rotation=False).is_rotated


class TestReadRasterGeometry:
    @pytest.mark.unit
    def test_reads_the_header_of_a_geotiff(self, tmp_path):
        transformation = (10.0, 2.0, 0.0, 20.0, 0.0, -2.0)
        path = write_geotiff(tmp_path / "grid.tif", 4, 2, transformation, LOCAL_CRS_WKT)

        cols, rows, read_transformation, projection = read_raster_geometry(path)

        assert (cols, rows) == (4, 2)
        assert read_transformation == pytest.approx(transformation)
        assert same_crs(projection, LOCAL_CRS_WKT)

    @pytest.mark.unit
    def test_a_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_raster_geometry(tmp_path / "absent.tif")

    @pytest.mark.unit
    def test_an_unreadable_file_raises(self, tmp_path):
        broken = tmp_path / "broken.tif"
        broken.write_bytes(b"not a raster")

        with pytest.raises(RuntimeError):
            read_raster_geometry(broken)
