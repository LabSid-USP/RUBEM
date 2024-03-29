import pytest

from rubem.configuration.model_configuration import CalibrationParameters


class TestCalibrationParameters:

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "alpha, beta, w_1, w_2, w_3, rcd, f, alpha_gw, x",
        [
            (0.0099, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (10.001, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.0099, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (0.5, 1.0001, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, -0.0001, 0.5, 0.5, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 1.00001, 0.0, 0.0, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.5, -0.0001, 0.5, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.0, 1.00001, 0.0, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.5, 0.5, -0.0001, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.0, 0.0, 1.00001, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 0.9999, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 10.001, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.0099, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 1.0001, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.0099, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 1.0001, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, -0.001),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 1.0001),
            (0.5, 0.5, 0.33, 0.34, 0.34, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.00, 0.00, 0.00, 5.0, 0.5, 0.5, 0.5),
        ],
    )
    def test_calibration_parameters_constructor_bad_args(
        self, alpha, beta, w_1, w_2, w_3, rcd, f, alpha_gw, x
    ):
        with pytest.raises(Exception):
            CalibrationParameters(
                alpha=alpha,
                beta=beta,
                w_1=w_1,
                w_2=w_2,
                w_3=w_3,
                rcd=rcd,
                f=f,
                alpha_gw=alpha_gw,
                x=x,
            )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "alpha, beta, w_1, w_2, w_3, rcd, f, alpha_gw, x",
        [
            (0.01, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (10.0, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.01, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (0.5, 1.00, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.0, 0.5, 0.5, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 1.0, 0.0, 0.0, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.5, 0.0, 0.5, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.0, 1.0, 0.0, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.5, 0.5, 0.0, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.0, 0.0, 1.0, 5.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 1.00, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 10.0, 0.5, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.01, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 1.00, 0.5, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.01, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 1.00, 0.5),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 0.0),
            (0.5, 0.5, 0.33, 0.33, 0.34, 5.0, 0.5, 0.5, 1.0),
        ],
    )
    def test_calibration_parameters_constructor_good_args(
        self, alpha, beta, w_1, w_2, w_3, rcd, f, alpha_gw, x
    ):
        _ = CalibrationParameters(
            alpha=alpha,
            beta=beta,
            w_1=w_1,
            w_2=w_2,
            w_3=w_3,
            rcd=rcd,
            f=f,
            alpha_gw=alpha_gw,
            x=x,
        )
