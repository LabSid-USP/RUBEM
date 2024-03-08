import pcraster as pcr


class Interception:
    """Class to calculate interception.

    This class contains methods to calculate Simple Ratio (SR), Crop Coefficient (Kc),
    Fraction of Photosynthetically Active Radiation (FPAR), Leaf Area Index (LAI),
    and Interception.
    """

    @staticmethod
    def get_reflectances_simple_ration(ndvi: pcr._pcraster.Field) -> pcr._pcraster.Field:
        """Return Reflectances Simple Ratio (SR).

        :param ndvi: Normalized Difference Vegetation Index (NDVI) at the pixel
        :type ndvi: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Reflectances Simple Ratio (SR) [-]
        :rtype: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return (1 + ndvi) / (1 - ndvi)

    @staticmethod
    def get_crop_coef(
        ndvi: pcr._pcraster.Field,
        ndvi_min: pcr._pcraster.Field,
        ndvi_max: pcr._pcraster.Field,
        crop_coef_min: pcr._pcraster.Field,
        crop_coef_max: pcr._pcraster.Field,
    ) -> pcr._pcraster.Field:
        """Return Crop Coefficient (Kc).

        :param ndvi: Normalized Difference Vegetation Index (NDVI) at the pixel
        :type ndvi: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param ndvi_min: Minimum Normalized Difference Vegetation Index (NDVI) at the pixel
        :type ndvi_min: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param ndvi_max: Maximum Normalized Difference Vegetation Index (NDVI) at the pixel
        :type ndvi_max: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param crop_coef_min: Minimum Crop Coefficient landuse class [-]
        :type crop_coef_min: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param crop_coef_max: Maximum Crop Coefficient landuse class [-]
        :type crop_coef_max: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Crop Coefficient (Kc) [-]
        :rtype: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return crop_coef_min + (
            (crop_coef_max - crop_coef_min) * ((ndvi - ndvi_min) / (ndvi_max - ndvi_min))
        )

    @staticmethod
    def get_fpar(
        fpar_min: float,
        fpar_max: float,
        reflectances_simple_ratio: pcr._pcraster.Field,
        reflectances_simple_ratio_min: pcr._pcraster.Field,
        reflectances_simple_ratio_max: pcr._pcraster.Field,
    ) -> pcr._pcraster.Field:
        """Return Fraction of Photosynthetically Active Radiation (FPAR).

        :param fpar_min: Minimum Fraction of Photosynthetically Active Radiation [-]
        :type fpar_min: float

        :param fpar_max: Maximum Fraction of Photosynthetically Active Radiation [-]
        :type fpar_max: float

        :param reflectances_simple_ratio: Reflectances Simple Ratio [-]
        :type reflectances_simple_ratio: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param reflectances_simple_ratio_min: Mimimum Reflectances Simple Ratio [-]
        :type reflectances_simple_ratio_min: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param reflectances_simple_ratio_max: Maximum Reflectances Simple Ratio [-]
        :type reflectances_simple_ratio_max: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Fraction of Photosynthetically Active Radiation (FPAR) [-]
        :rtype: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        fpar_comp = (
            (reflectances_simple_ratio - reflectances_simple_ratio_min)
            * (fpar_max - fpar_min)
            / (reflectances_simple_ratio_max - reflectances_simple_ratio_min)
        ) + fpar_min
        return pcr.min(fpar_comp, fpar_max)

    @staticmethod
    def get_leaf_area_index(
        fpar: pcr._pcraster.Field,
        fpar_max: float,
        leaf_area_index_max: float,
    ) -> pcr._pcraster.Field:
        """Return Leaf Area Index (LAI).

        :param fpar: Fraction of Photosynthetically Active Radiation (FPAR) [-]
        :type fpar: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param fpar_max: Maximum Fraction of Photosynthetically Active Radiation (FPAR) [-]
        :type fpar_max: float

        :param leaf_area_index_max: Maximum Leaf Area Index [-]
        :type leaf_area_index_max: float

        :returns: Leaf Area Index (LAI) [-]
        :rtype:pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        return leaf_area_index_max * ((pcr.log10(1 - fpar)) / (pcr.log10(1 - fpar_max)))

    @staticmethod
    def get_interception(
        alfa: float,
        leaf_area_index: pcr._pcraster.Field,
        precipitation: pcr._pcraster.Field,
        rainy_days: pcr._pcraster.Field,
        vegeted_area_fraction: pcr._pcraster.Field,
    ) -> pcr._pcraster.Field:
        """Return Interception [mm].

        :param alfa: Interception Parameter [-]
        :type alfa: float

        :param leaf_area_index: Leaf Area Index (LAI) [-]
        :type leaf_area_index: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param precipitation: Monthly Precipitation [mm]
        :type precipitation: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param rainy_days: Number of rainy days for month
        :type rainy_days: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :param vegeted_area_fraction: Vegetated Area Fraction
        :type vegeted_area_fraction: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``

        :returns: Monthly Interception [mm]
        :rtype: pcr._pcraster.Field ``PCRASTER_VALUESCALE=VS_SCALAR``
        """
        # condition of precipitation, to divide by non zero number (missing value)
        cond_non_zero_prec = pcr.scalar((precipitation != 0))
        cond_zero_prec = pcr.scalar((precipitation == 0))
        prec = precipitation * cond_non_zero_prec + (precipitation * cond_zero_prec + 0.00001)

        partial_den = 1 + (
            precipitation * ((1 - (pcr.exp(-0.463 * leaf_area_index))) / (alfa * leaf_area_index))
        )
        min_daily_interception_limit = alfa * leaf_area_index * (1 - (1 / partial_den))
        interception_rate = 1 - pcr.exp(-min_daily_interception_limit * rainy_days / prec)

        # Total interception
        return vegeted_area_fraction * precipitation * interception_rate
