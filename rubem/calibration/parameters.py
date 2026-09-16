"""The decision vector of the calibration and its translation to model parameters.

The differential evolution searches eight free parameters, ``alpha``, ``beta``,
``w_1``, ``w_2``, ``rcd``, ``f``, ``alpha_gw`` and ``x``; the slope factor
weight ``w_3`` is not searched but derived from the other two weights, since the
three weights of the weighted runoff coefficient must add up to 1. The search is
therefore eight-dimensional with the linear constraint ``w_1 + w_2 <= 1``, which
keeps the derived weight inside its own range.

The bounds are the ones the application settings declare (``appsettings.json``,
section ``value_ranges.variables``), the same ranges
:class:`rubem.configuration.calibration_parameters.CalibrationParameters`
validates against, so a candidate the optimizer proposes inside the bounds is a
configuration the model accepts.

Nothing here imports SciPy at module level; :func:`weights_constraint`, the only
function that needs it, imports it when it is called.
"""

import logging
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import numpy as np

from ..configuration._ranges import variable_range

if TYPE_CHECKING:
    from scipy.optimize import LinearConstraint

logger = logging.getLogger(__name__)

FREE_PARAMETERS = ("alpha", "beta", "w_1", "w_2", "rcd", "f", "alpha_gw", "x")
"""The parameters the optimizer searches, in the order of the decision vector."""

DERIVED_PARAMETER = "w_3"
"""The slope factor weight, derived from ``w_1`` and ``w_2`` instead of searched."""

CALIBRATION_PARAMETERS = (
    "alpha",
    "beta",
    "w_1",
    "w_2",
    "w_3",
    "rcd",
    "f",
    "alpha_gw",
    "x",
)
"""The nine calibration parameters of the model, in the order of the configuration."""

_ALIASES = {"b": "beta", "w1": "w_1", "w2": "w_2", "w3": "w_3"}
"""Spellings the legacy configuration file accepts for a calibration parameter."""


def bounds() -> list[tuple[float, float]]:
    """Return the ``(minimum, maximum)`` bound of every free parameter.

    The bounds come from the application settings, in the order of
    :data:`FREE_PARAMETERS`, which is the order of the decision vector.

    :return: One ``(minimum, maximum)`` pair per free parameter.
    :rtype: list[tuple[float, float]]
    """
    return [variable_range(name) for name in FREE_PARAMETERS]


def vector_to_parameters(vector: Sequence[float] | np.ndarray) -> dict[str, float]:
    """Return the nine calibration parameters a decision vector stands for.

    The eight free values are read in the order of :data:`FREE_PARAMETERS` and
    the slope factor weight is derived as ``w_3 = 1 - w_1 - w_2``, so that the
    three weights always add up to 1.

    :param vector: The eight free values, in the order of :data:`FREE_PARAMETERS`.
    :type vector: collections.abc.Sequence[float] | numpy.ndarray

    :return: The nine parameters, keyed by the names of
        :class:`rubem.configuration.calibration_parameters.CalibrationParameters`.
    :rtype: dict[str, float]

    :raises ValueError: If the vector does not have eight entries.
    """
    values = np.asarray(vector, dtype=np.float64).ravel()
    if values.size != len(FREE_PARAMETERS):
        raise ValueError(
            f"The decision vector must have {len(FREE_PARAMETERS)} entries "
            f"({', '.join(FREE_PARAMETERS)}), got {values.size}."
        )
    parameters = {name: float(value) for name, value in zip(FREE_PARAMETERS, values, strict=True)}
    # The two weights are added first and the sum is subtracted once. Taking
    # them away one at a time, ``1 - w_1 - w_2``, rounds twice: for 20 of the
    # 101 pairs of two-decimal weights that add up to 1, among them
    # ``w_1 = 0.33, w_2 = 0.67``, it lands one ulp below zero, and
    # :class:`rubem.configuration.calibration_parameters.CalibrationParameters`
    # then refuses the run. With a single subtraction the weight is exactly
    # zero at the boundary and never negative while ``w_1 + w_2 <= 1``.
    parameters[DERIVED_PARAMETER] = 1.0 - (parameters["w_1"] + parameters["w_2"])
    return {name: parameters[name] for name in CALIBRATION_PARAMETERS}


def parameters_to_vector(parameters: Mapping[str, float]) -> np.ndarray:
    """Return the decision vector of a set of calibration parameters.

    This is how the configuration under calibration becomes the ``x0`` of the
    differential evolution. Both spellings the configuration files use are
    accepted, the canonical ``beta``, ``w_1``, ``w_2`` and the legacy ``b``,
    ``w1``, ``w2``; the derived ``w_3`` is ignored, since it is not searched.
    The straightforward way to obtain the mapping is to dump the loaded
    :class:`rubem.configuration.calibration_parameters.CalibrationParameters`
    of a configuration, which has already normalised the spellings.

    :param parameters: The calibration parameters, by name.
    :type parameters: collections.abc.Mapping[str, float]

    :return: The eight free values, in the order of :data:`FREE_PARAMETERS`.
    :rtype: numpy.ndarray

    :raises KeyError: If a free parameter is missing from the mapping.
    """
    normalised = {_ALIASES.get(name, name): value for name, value in parameters.items()}
    missing = [name for name in FREE_PARAMETERS if name not in normalised]
    if missing:
        raise KeyError(
            f"The calibration parameters are missing {', '.join(missing)}; "
            f"the decision vector needs {', '.join(FREE_PARAMETERS)}."
        )
    return np.asarray([float(normalised[name]) for name in FREE_PARAMETERS], dtype=np.float64)


def is_admissible(vector: Sequence[float] | np.ndarray) -> bool:
    """Whether a decision vector describes a configuration the model accepts.

    A vector is admissible when every free value lies inside its bound, when
    the two searched weights add up to at most 1 and when the derived ``w_3``
    lies inside its own bound. The derived weight is taken from
    :func:`vector_to_parameters`, the very value the run would be given, so
    that the guard can never disagree with the derivation and let through a
    candidate
    :class:`rubem.configuration.calibration_parameters.CalibrationParameters`
    would then refuse.

    :param vector: The eight free values, in the order of :data:`FREE_PARAMETERS`.
    :type vector: collections.abc.Sequence[float] | numpy.ndarray

    :return: ``True`` when the model can be run with this candidate.
    :rtype: bool
    """
    values = np.asarray(vector, dtype=np.float64).ravel()
    if values.size != len(FREE_PARAMETERS):
        return False
    if not np.all(np.isfinite(values)):
        return False
    for value, (minimum, maximum) in zip(values, bounds(), strict=True):
        if not minimum <= value <= maximum:
            return False

    weights = float(values[FREE_PARAMETERS.index("w_1")] + values[FREE_PARAMETERS.index("w_2")])
    if weights > 1.0:
        return False
    derived = vector_to_parameters(values)[DERIVED_PARAMETER]
    minimum, maximum = variable_range(DERIVED_PARAMETER)
    return minimum <= derived <= maximum


def weights_constraint() -> "LinearConstraint":
    """Return the linear constraint ``w_1 + w_2 <= 1`` on the decision vector.

    The differential evolution receives it so that it never spends a model run
    on a candidate whose slope factor weight would come out negative: SciPy
    evaluates the constraint before the objective and skips the members that
    violate it.

    :return: The constraint, over the eight entries of the decision vector.
    :rtype: scipy.optimize.LinearConstraint

    :raises ImportError: If SciPy is not installed.
    """
    from scipy.optimize import LinearConstraint

    coefficients = np.zeros((1, len(FREE_PARAMETERS)), dtype=np.float64)
    coefficients[0, FREE_PARAMETERS.index("w_1")] = 1.0
    coefficients[0, FREE_PARAMETERS.index("w_2")] = 1.0
    return LinearConstraint(coefficients, -np.inf, 1.0)
