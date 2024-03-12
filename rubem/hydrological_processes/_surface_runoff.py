import pcraster as pcr
from pcraster._pcraster import Field


class SurfaceRunoff:
    """Class to calculate surface runoff.

    This class contains methods to calculate coefficient representing soil moisture conditions (Ch),
    potential runoff coefficient for permeable areas (Cper), percentage of impervious surface per grid cell and
    the potential runoff coefficient of the impervious area (Cimp), weighted potential runoff coefficient (Cwp),
    actual runoff coefficient (Csr), and surface runoff.
    """

    @staticmethod
    def get_coef_soil_moist_conditions(
        actual_soil_moist_cont: Field,
        soil_bulk_density: Field,
        rootzone_depth: Field,
        soil_moist_cont_sat_point: Field,
        beta: float,
    ) -> Field:
        """Return coefficient representing soil moisture conditions (Ch).

        :param actual_soil_moist_cont: Actual Soil moisture content [mm]
        :type actual_soil_moist_cont: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_bulk_density: Soil Bulk Density [g/cm3]
        :type soil_bulk_density:Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param rootzone_depth: Depth Rootzone [cm]
        :type rootzone_depth: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_moist_cont_sat_point: Soil moisture content at saturation point [-]
        :type soil_moist_cont_sat_point: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param beta: Rainfall Intensity parameter (calibrated)
        :type beta: float

        :returns: Coefficient representing soil moisture conditions [-]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        tur = actual_soil_moist_cont / (
            soil_bulk_density * rootzone_depth * 10
        )  # [%] soil moisture
        return (tur / soil_moist_cont_sat_point) ** beta

    @staticmethod
    def get_runoff_coef_permeable_areas(
        soil_water_coef_permeable_ares: Field,
        soil_bulk_density: Field,
        rootzone_depth: Field,
        land_surface_slope: Field,
        manning: Field,
        w1: float,
        w2: float,
        w3: float,
    ) -> Field:
        """Return the potential runoff coefficient for permeable areas (Cper).

        :param soil_water_coef_permeable_ares: Soil water content at wilting point
        :type soil_water_coef_permeable_ares: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_bulk_density: Soil Bulk Density [g/cm3]
        :type soil_bulk_density:Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param rootzone_depth: Depth Rootzone [cm]
        :type rootzone_depth: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param land_surface_slope: Land surfafe slope [%]
        :type land_surface_slope: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param manning: Manning's roughness coefficient [-]
        :type manning: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param w1: Weight for landuse component [-]
        :type w1: float

        :param w2: Weight for soil component [-]
        :type w2: float

        :param w3: Weight for slope component [-]
        :type w3: float

        :returns: Potential runoff coefficient for permeable areas (Cper).
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        tuw = soil_water_coef_permeable_ares / (
            soil_bulk_density * rootzone_depth * 10
        )  # [%] soil wilting point
        return (
            w1 * (0.02 / manning)
            + w2 * (tuw / (1 - tuw))
            + w3 * ((land_surface_slope / (10 + land_surface_slope)))
        )

    @staticmethod
    def get_impervious_surface_percent_per_grid_cell(
        open_water_area_fraction: Field, impervious_area_fraction: Field
    ) -> Field:
        """Return percentage of impervious surface per grid cell.

        :param open_water_area_fraction: Open Water Area Fraction [-]
        :type open_water_area_fraction: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param impervious_area_fraction: Impervious Area Fraction [-]
        :type impervious_area_fraction: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Percentage of impervious surface per grid cell
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """

        return open_water_area_fraction + impervious_area_fraction

    @staticmethod
    def get_runoff_coef_impervious_area(
        percent_impervious_surface_per_grid_cell: Field,
    ) -> Field:
        """Return the Potential runoff coefficient of the impervious area.

        :param percent_impervious_surface_per_grid_cell: percentage of impervious surface per grid cell
        :type percent_impervious_surface_per_grid_cell: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Potential runoff coefficient of the impervious area
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return 0.09 * pcr.exp((2.4 * percent_impervious_surface_per_grid_cell))

    @staticmethod
    def get_weighted_pot_runoff_coef(
        percent_impervious_surface_per_grid_cell: Field,
        runoff_coef_permeable_areas: Field,
        runoff_coef_impervious_area: Field,
    ) -> Field:
        """Return weighted potential runoff coefficient (Cwp).

        :param percent_impervious_surface_per_grid_cell: Percentage of impervious surface per grid cell
        :type percent_impervious_surface_per_grid_cell: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param runoff_coef_permeable_areas: Runoff coefficient for permeable areas (Cper)
        :type runoff_coef_permeable_areas: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param runoff_coef_impervious_area: Runoff coefficient of the impervious area [-]
        :type runoff_coef_impervious_area: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Weighted potential runoff coefficient (Cwp)
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return (
            (1 - percent_impervious_surface_per_grid_cell) * runoff_coef_permeable_areas
            + percent_impervious_surface_per_grid_cell * runoff_coef_impervious_area
        )

    @staticmethod
    def get_actual_runoff_coef(
        weighted_pot_runoff_coef: Field,
        average_daily_rainfall: Field,
        regional_consec_dryness: float,
    ) -> Field:
        """Return actual runoff coefficient (Csr).

        :param weighted_pot_runoff_coef: Weighted potential runoff coefficient (Cwp)
        :type weighted_pot_runoff_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param average_daily_rainfall: Average daily rainfall in rainy days (mm/day per month)
        :type average_daily_rainfall: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param regional_consec_dryness: Regional consecutive dryness level (mm)
        :type regional_consec_dryness: float

        :returns: Actual runoff coefficient (Csr) [-]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return (weighted_pot_runoff_coef * average_daily_rainfall) / (
            weighted_pot_runoff_coef * average_daily_rainfall
            - regional_consec_dryness * weighted_pot_runoff_coef
            + regional_consec_dryness
        )

    @staticmethod
    def get_surface_runoff(
        actual_runoff_coef: Field,
        soil_moist_cond_coef: Field,
        precipitation: Field,
        interception: Field,
        open_water_area_fraction: Field,
        evapotranspiration_open_water_area: Field,
        actual_soil_moist_cont_non_sat_zone: Field,
        soil_moist_cont_sat_point: Field,
    ) -> Field:
        """Return surface runoff [mm].

        :param actual_runoff_coef: Actual runoff coefficient (Csr) [-]
        :type actual_runoff_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_moist_cond_coef: Coefficient representing soil moisture conditions (Ch)
        :type soil_moist_cond_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param precipitation: Monthly precipitation [mm]
        :type precipitation: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param interception: Monthly Interception [mm]
        :type interception: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param open_water_area_fraction: Open Water Area Fraction [-]
        :type open_water_area_fraction: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param evapotranspiration_open_water_area: Evaporation of Open Water Area [mm]
        :type evapotranspiration_open_water_area: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param actual_soil_moist_cont_non_sat_zone: Actual soil moisture content non-saturated zone [mm]
        :type actual_soil_moist_cont_non_sat_zone: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_moist_cont_sat_point: Soil moisture content at saturation point [-]
        :type soil_moist_cont_sat_point: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Monthly surface runoff [mm]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        # condition for pixel of water
        cond_water_pixel = pcr.scalar(open_water_area_fraction == 1)
        # condition for positive value for (prec - ETao)
        cond_positive_prec_etowa = pcr.scalar(
            (precipitation - evapotranspiration_open_water_area) > 0
        )
        partial_surface_runoff = (
            actual_runoff_coef * soil_moist_cond_coef * (precipitation - interception)
        ) * (1 - cond_water_pixel) + (
            precipitation - evapotranspiration_open_water_area
        ) * cond_positive_prec_etowa * cond_water_pixel

        # condition for tur > tursat
        cond_saturation = pcr.scalar(
            actual_soil_moist_cont_non_sat_zone == soil_moist_cont_sat_point
        )
        return (
            (partial_surface_runoff * (1 - cond_saturation))
            + (precipitation - interception) * (cond_saturation) * (1 - cond_water_pixel)
            + partial_surface_runoff * (cond_water_pixel)
        )
