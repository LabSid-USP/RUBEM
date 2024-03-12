import pcraster as pcr
from pcraster._pcraster import Field


class Soil:
    """Class to calculate soil processes.

    This class contains methods to calculate Lateral Flow (LF), Recharge (REC),
    Baseflow (BF), Actual Soil Moisture Content at non-saturated zone (TUr),
    and Actual Water Content at saturated zone (TUs).
    """

    @staticmethod
    def get_lateral_flow(
        preferred_flow_direction: float,
        hydraulic_cond_coef: Field,
        actual_soil_moist_cont_rootzone: Field,
        soil_moist_cont_sat_point: Field,
    ):
        """Return Lateral Flow in the pixel [mm].

        :param preferred_flow_direction: preferred flow direction parameter [-]
        :type preferred_flow_direction: float

        :param hydraulic_cond_coef: Hydraulic Conductivity of soil class [mm/month]
        :type hydraulic_cond_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param actual_soil_moist_cont_rootzone: Actual soil moisture content non-saturated zone [mm]
        :type actual_soil_moist_cont_rootzone: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_moist_cont_sat_point: Soil moisture content at saturation point []
        :type soil_moist_cont_sat_point: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Lateral Flow [mm]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return (
            preferred_flow_direction
            * hydraulic_cond_coef
            * ((actual_soil_moist_cont_rootzone / soil_moist_cont_sat_point) ** 2)
        )

    @staticmethod
    def get_recharge(
        preferred_flow_direction: float,
        hydraulic_cond_coef: Field,
        actual_soil_moist_cont_rootzone: Field,
        soil_mois_cont_sat_point: Field,
    ) -> Field:
        """Return Recharge in the pixel [mm].

        :param preferred_flow_direction: preferred flow direction parameter [-]
        :type preferred_flow_direction: float

        :param hydraulic_cond_coef: Hydraulic Conductivity of soil class [mm/month]
        :type hydraulic_cond_coef: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param actual_soil_moist_cont_rootzone: Actual soil moisture content non-saturated zone [mm]
        :type actual_soil_moist_cont_rootzone: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_mois_cont_sat_point: Soil moisture content at saturation point [-]
        :type soil_mois_cont_sat_point: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Monthly Recharge [mm]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return (
            (1 - preferred_flow_direction)
            * hydraulic_cond_coef
            * ((actual_soil_moist_cont_rootzone / soil_mois_cont_sat_point) ** 2)
        )

    @staticmethod
    def get_baseflow(
        previous_baseflow: Field,
        baseflow_recession_coef: float,
        recharge: Field,
        water_cont_sat_zone: Field,
        threshold_for_baseflow_ocurrence: Field,
    ) -> Field:
        """Return Baseflow in the pixel [mm].

        :param previous_baseflow: Baseflow at timestep t-1 [mm]
        :type previous_baseflow: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param baseflow_recession_coef: Baseflow recession coefficient (Calibrated) [-]
        :type baseflow_recession_coef: float

        :param recharge: Monthly Recharge at timestep t
        :type recharge: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param water_cont_sat_zone: Water content at saturated zone [mm]
        :type water_cont_sat_zone: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param threshold_for_baseflow_ocurrence: Threshold for baseflow ocurrence [mm]
        :type threshold_for_baseflow_ocurrence: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Monthly Baseflow [mm]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        # limit condition for base flow
        cond_lim_for_baseflow = pcr.scalar(water_cont_sat_zone > threshold_for_baseflow_ocurrence)
        return (
            (previous_baseflow * ((pcr.exp(1)) ** -baseflow_recession_coef))
            + (1 - ((pcr.exp(1)) ** -baseflow_recession_coef)) * recharge
        ) * cond_lim_for_baseflow

    # First soil layer
    @staticmethod
    def get_actual_soil_moist_cont_rootzone(
        previous_soil_moist_cont: Field,
        precipitation: Field,
        interception: Field,
        surface_runoff: Field,
        lateral_flow: Field,
        recharge: Field,
        actual_evapotranspiration: Field,
        open_water_area_fraction: Field,
        soil_moist_cont_sat_point: Field,
    ) -> Field:
        """Return Actual Soil Moisture Content at non-saturated zone in the pixel [mm].

        :param previous_soil_moist_cont: Soil moisture content at timestep t-1 [mm]
        :type previous_soil_moist_cont: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param precipitation: Monthly precipitation [mm]
        :type precipitation: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param interception: Monthly Interception [mm]
        :type interception: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param surface_runoff: Monthly Surface Runoff [mm]
        :type surface_runoff: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param lateral_flow: Monthly Lateral Flow [mm]
        :type lateral_flow: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param recharge: Monthly Recharge [mm]
        :type recharge: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param actual_evapotranspiration: Monthly Actual Evapotranspiration [mm]
        :type actual_evapotranspiration: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param open_water_area_fraction: Open Water Area Fraction [-]
        :type open_water_area_fraction: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param soil_moist_cont_sat_point: Soil moisture content at saturation point []
        :type soil_moist_cont_sat_point: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Soil Moisture Content [mm]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """

        # condition for pixel of water, if open_water_area_fraction different of 1 (not water)
        cond_water_pixel = pcr.scalar(open_water_area_fraction != 1)
        # soil balance
        balance = (
            previous_soil_moist_cont
            + precipitation
            - interception
            - surface_runoff
            - lateral_flow
            - recharge
            - actual_evapotranspiration
        )
        # condition for positivie balance
        cond_positive_balance = pcr.scalar(balance > 0)
        # if balance is negative TUR = 0, + if pixel is water, TUR = TUsat
        partial_soil_moist_cont = (
            balance * cond_positive_balance
        ) * cond_water_pixel + soil_moist_cont_sat_point * (1 - cond_water_pixel)
        # condition for tur > tursat
        cond_saturation = pcr.scalar(partial_soil_moist_cont < soil_moist_cont_sat_point)
        # If Tur>tsat, TUR=TUsat
        return (partial_soil_moist_cont * cond_saturation) + soil_moist_cont_sat_point * (
            1 - cond_saturation
        )

    # Second soil layer
    @staticmethod
    def get_actual_water_cont_sat_zone(
        previous_water_cont_sat_zone: Field,
        recharge: Field,
        baseflow: Field,
    ) -> Field:
        """Return Actual Water Content at saturated zone in the pixel [mm].

        :param previous_water_cont_sat_zone: Water content at saturated zone at timestep t-1 [mm]
        :type previous_water_cont_sat_zone: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param recharge: Monthly Recharge [mm]
        :type recharge: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param baseflow: Monthly Baseflow[mm]
        :type baseflow: Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Water content at saturated zone [mm]
        :rtype: Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        # soil balance
        return previous_water_cont_sat_zone + recharge - baseflow
