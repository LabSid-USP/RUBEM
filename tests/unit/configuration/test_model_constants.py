import pytest

from rubem.configuration.model_constants import ModelConstants


class TestModelConstants:

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "fpar_max, fpar_min, lai_max, imp_int",
        [
            (-0.01, 0.0, 0.0, 0.0),
            (0.0, -0.01, 0.0, 0.0),
            (0.0, 0.0, -0.01, 0.0),
            (0.0, 0.0, 0.0, -0.01),
            (1.01, 1.0, 12.0, 3.0),
            (1.0, 1.01, 12.0, 3.0),
            (1.0, 1.0, 12.01, 3.0),
            (1.0, 1.0, 12.0, 3.01),
        ],
    )
    def test_model_constants_constructor_bad_args(self, fpar_max, fpar_min, lai_max, imp_int):
        with pytest.raises(Exception):
            ModelConstants(
                fraction_photo_active_radiation_max=fpar_max,
                fraction_photo_active_radiation_min=fpar_min,
                leaf_area_interception_max=lai_max,
                impervious_area_interception=imp_int,
            )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "fpar_max, fpar_min, lai_max, imp_int",
        [
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 1.0, 12.0, 3.0),
        ],
    )
    def test_model_constants_constructor_good_args(self, fpar_max, fpar_min, lai_max, imp_int):
        ModelConstants(
            fraction_photo_active_radiation_max=fpar_max,
            fraction_photo_active_radiation_min=fpar_min,
            leaf_area_interception_max=lai_max,
            impervious_area_interception=imp_int,
        )
