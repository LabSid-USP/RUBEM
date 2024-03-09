import pcraster as pcr
from pcraster._pcraster import Field


class Evapotranspiration:
    """Class to calculate evapotranspiration.

    This class contains methods to calculate potential evapotranspiration (ETp),
    water stress coefficient (Ks), actual evapotranspiration of vegetated area (ETva),
    pan coefficient (Kp), actual evapotranspiration of open water area (ETowa),
    and actual evapotranspiration of bare soil area (ETbsa).
    """

    @staticmethod
    def get_water_stress_coef_et_vegeted_area(
        actual_soil_moisture_content: Field,
        soil_class_wilting_point: Field,
        soild_class_field_capacity: Field,
    ) -> Field:
        """Return Water Stress Coefficient (Ks) for evapotranspiration of vegetated area.

        :param actual_soil_moisture_content: Actual Soil Moisture Content [mm]
        :type actual_soil_moisture_content: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_class_wilting_point: Wilting Point of soil class [mm]
        :type soil_class_wilting_point: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soild_class_field_capacity: Field Capacity of soil class [mm]
        :type soild_class_field_capacity: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Water Stress Coefficient (Ks) [-]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        ks_cond = pcr.scalar(
            actual_soil_moisture_content > soil_class_wilting_point
        )  # when actual_soil_moisture_content < soil_class_wilting_point, (false, ks = 0)
        # Multiply (actual_soil_moisture_content - soil_class_wilting_point) to avoid negative ln
        return (pcr.ln((actual_soil_moisture_content - soil_class_wilting_point) * ks_cond + 1)) / (
            pcr.ln(soild_class_field_capacity - soil_class_wilting_point + 1)
        )

    @staticmethod
    def get_et_vegetated_area(
        potential_etp: Field,
        crop_coef: Field,
        water_stress_coef: Field,
    ) -> Field:
        """Return evapotranspiration of vegetated area.

        :param potential_etp: Potential Evapotranspiration [mm]
        :type potential_etp: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param crop_coef: Crop Coefficient [-]
        :type crop_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param water_stress_coef: Water Stress Coefficient [-]
        :type water_stress_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Actual Evapotranspiration
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return potential_etp * crop_coef * water_stress_coef

    @staticmethod
    def get_pan_coef_et_open_water_area(
        fetch_distance: int, wind_speed: float, relative_humidity: float
    ) -> Field:
        """Return pan coefficient (Kp) for evapotranspiration of open water area.

        :param fetch_distance: Fetch distance
        :type fetch_distance: int

        :param wind_speed: Wind speed at 2 meters [m/s-1]
        :type wind_speed: float

        :param relative_humidity: Relative humidity [%]
        :type relative_humidity: float

        :returns: pan coefficient (Kp) []
        :rtype: float
        """
        return (
            0.482
            + 0.024 * pcr.ln(fetch_distance)
            - 0.000376 * wind_speed
            + 0.0045 * relative_humidity
        )

    @staticmethod
    def get_actual_et_open_water_area(
        potential_etp: Field,
        pan_coef: Field,
        precipitation: Field,
        open_water_area_fraction: Field,
    ) -> Field:
        """Return actual evapotranspiration of open water area.

        :param potential_etp: Monthly Potential Evapotranspiration [mm]
        :type potential_etp: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param pan_coef: pan coefficient (Kp) []
        :type pan_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param precipitation: Monthly Precipitation [mm]
        :type precipitation: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param open_water_area_fraction: Open water Area Fraction
        :type open_water_area_fraction: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Actual evapotranspiration of open water area
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        # condition for pixel of water
        cond_water_pixel = pcr.scalar(open_water_area_fraction == 1)

        partial_actual_etowa = potential_etp / pan_coef

        # conditions for max value for partial_actual_etp_owa,
        # if partial_actual_etp_owa > precipitation in pixel with open_water_area_fraction = 1, then actual_etp_owa = precipitation
        cond_max_etp_kp = pcr.scalar((partial_actual_etowa) > precipitation)

        return (
            (partial_actual_etowa) * (1 - cond_water_pixel)
            + precipitation * cond_water_pixel * cond_max_etp_kp
            + (partial_actual_etowa) * cond_water_pixel * (1 - cond_max_etp_kp)
        )

    @staticmethod
    def get_water_stress_coef_et_bare_soil_area(
        potential_et: Field,
        crop_coef_min: Field,
        watet_stress_coef: Field,
    ) -> Field:
        """Return Water Stress Coefficient (Ks) for evapotranspiration of bare soil area.

        :param potential_et: Monthly Potential Evapotranspiration [mm]
        :type potential_et: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param crop_coef_min: Minimum crop Coefficient [-]
        :type crop_coef_min: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param watet_stress_coef: Water Stress Coefficient [-]
        :type watet_stress_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Actual Evapotranspiration of bare soil area
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        cond = 1 * pcr.scalar(watet_stress_coef != 0)  # if ks is different from 0
        return potential_et * crop_coef_min * watet_stress_coef * cond
