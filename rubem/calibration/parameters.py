"""The decision vector of the calibration and its translation to model parameters.

The differential evolution searches the free calibration parameters, ``alpha``,
``beta``, ``w_1``, ``w_2``, ``rcd``, ``f``, ``alpha_gw`` and ``x``; the slope
factor weight ``w_3`` is not searched but derived from the other two weights,
since the three weights of the weighted runoff coefficient must add up to 1. A
search over all eight is therefore eight-dimensional with the linear constraint
``w_1 + w_2 <= 1``, which keeps the derived weight inside its own range.

:class:`DecisionSpace`, built by :func:`decision_space`, is that vector for one
run. It narrows the bounds of a parameter to a range of the user's choosing and
takes a parameter out of the vector altogether, at a value the user pins it to:
a fixed parameter keeps its value in the nine parameters every candidate is run
with, but the optimizer never moves it, and the dimension of the search falls by
one. Fixing one of the two searched weights replaces the linear constraint with
a narrower bound on the other, since only one of them is left to vary.

The bounds a run starts from are the ones the application settings declare
(``appsettings.json``, section ``value_ranges.variables``), the same ranges
:class:`rubem.configuration.calibration_parameters.CalibrationParameters`
validates against, so a candidate the optimizer proposes inside the bounds is a
configuration the model accepts. An override may only narrow them, never widen
them, for the same reason.

A configuration that enables MODFLOW adds the parameters of its ``modflow``
section, named in :mod:`rubem.calibration.modflow_parameters`. They are never
searched by default: a MODFLOW parameter joins the vector only when the caller
bounds it, after the eight parameters above, or fixes it, and its bound is
checked against the values the parameter may take instead of a range of the
application settings. Without MODFLOW names the space is the one described
above.

The module-level :func:`bounds`, :func:`vector_to_parameters`,
:func:`parameters_to_vector`, :func:`is_admissible` and
:func:`weights_constraint` are the default space, the one without fixed
parameters and without overridden bounds.

Nothing here imports SciPy at module level;
:meth:`DecisionSpace.weights_constraint`, the only method that needs it, imports
it when it is called.
"""

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import numpy as np

from ..configuration._ranges import variable_range
from .modflow_parameters import MODFLOW_PREFIX, ModflowCatalog

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


@dataclass(frozen=True)
class DecisionSpace:
    """The decision vector of one calibration: what is searched and between which bounds.

    The instances are plain data and are built by :func:`decision_space`, which
    is what validates them; they travel to the worker processes inside the
    evaluation context, so they hold nothing but names and numbers.

    :param free_names: The searched parameters, in the order of the decision
        vector: the entries of :data:`FREE_PARAMETERS` that are not fixed, then
        the bounded MODFLOW parameters.
    :type free_names: tuple[str, ...]

    :param fixed: The parameters that are not searched, by name, with the value
        every candidate carries.
    :type fixed: dict[str, float]

    :param bounds: One ``(minimum, maximum)`` pair per free parameter, in the
        order of :attr:`free_names`.
    :type bounds: tuple[tuple[float, float], ...]

    :param modflow_names: The MODFLOW parameters of the run, searched or
        fixed, in the order of the MODFLOW catalog. Empty, the default, when
        the run calibrates none.
    :type modflow_names: tuple[str, ...]
    """

    free_names: tuple[str, ...]
    fixed: dict[str, float]
    bounds: tuple[tuple[float, float], ...]
    modflow_names: tuple[str, ...] = ()

    @property
    def dimension(self) -> int:
        """Number of coordinates of the decision vector.

        :return: The number of free parameters.
        :rtype: int
        """
        return len(self.free_names)

    def to_parameters(self, vector: Sequence[float] | np.ndarray) -> dict[str, float]:
        """Return the nine calibration parameters a decision vector stands for.

        The free values are read in the order of :attr:`free_names`, the fixed
        ones are inserted at the value they were pinned to, and the slope factor
        weight is derived as ``w_3 = 1 - w_1 - w_2``, so that the three weights
        always add up to 1. The MODFLOW parameters of the run follow the nine.

        :param vector: The free values, in the order of :attr:`free_names`.
        :type vector: collections.abc.Sequence[float] | numpy.ndarray

        :return: The nine parameters, keyed by the names of
            :class:`rubem.configuration.calibration_parameters.CalibrationParameters`,
            then the :attr:`modflow_names`.
        :rtype: dict[str, float]

        :raises ValueError: If the vector does not have :attr:`dimension` entries.
        """
        values = np.asarray(vector, dtype=np.float64).ravel()
        if values.size != self.dimension:
            raise ValueError(
                f"The decision vector must have {self.dimension} entries "
                f"({', '.join(self.free_names)}), got {values.size}."
            )
        parameters = dict(self.fixed)
        parameters.update(
            {name: float(value) for name, value in zip(self.free_names, values, strict=True)}
        )
        # The two weights are added first and the sum is subtracted once. Taking
        # them away one at a time, ``1 - w_1 - w_2``, rounds twice: for 20 of the
        # 101 pairs of two-decimal weights that add up to 1, among them
        # ``w_1 = 0.33, w_2 = 0.67``, it lands one ulp below zero, and
        # :class:`rubem.configuration.calibration_parameters.CalibrationParameters`
        # then refuses the run. With a single subtraction the weight is exactly
        # zero at the boundary and never negative while ``w_1 + w_2 <= 1``.
        parameters[DERIVED_PARAMETER] = 1.0 - (parameters["w_1"] + parameters["w_2"])
        return {name: parameters[name] for name in (*CALIBRATION_PARAMETERS, *self.modflow_names)}

    def from_parameters(self, parameters: Mapping[str, float]) -> np.ndarray:
        """Return the decision vector of a set of calibration parameters.

        This is how the configuration under calibration becomes the ``x0`` of the
        differential evolution. Both spellings the configuration files use are
        accepted, the canonical ``beta``, ``w_1``, ``w_2`` and the legacy ``b``,
        ``w1``, ``w2``; the derived ``w_3`` and the fixed parameters are ignored,
        since they are not searched. The straightforward way to obtain the
        mapping is to dump the loaded
        :class:`rubem.configuration.calibration_parameters.CalibrationParameters`
        of a configuration, which has already normalised the spellings.

        :param parameters: The calibration parameters, by name.
        :type parameters: collections.abc.Mapping[str, float]

        :return: The free values, in the order of :attr:`free_names`.
        :rtype: numpy.ndarray

        :raises KeyError: If a free parameter is missing from the mapping.
        """
        normalised = {_ALIASES.get(name, name): value for name, value in parameters.items()}
        missing = [name for name in self.free_names if name not in normalised]
        if missing:
            raise KeyError(
                f"The calibration parameters are missing {', '.join(missing)}; "
                f"the decision vector needs {', '.join(self.free_names)}."
            )
        return np.asarray([float(normalised[name]) for name in self.free_names], dtype=np.float64)

    def is_admissible(self, vector: Sequence[float] | np.ndarray) -> bool:
        """Whether a decision vector describes a configuration the model accepts.

        A vector is admissible when every free value lies inside its bound, when
        the two weights add up to at most 1 and when the derived ``w_3`` lies
        inside its own bound. The derived weight is taken from
        :meth:`to_parameters`, the very value the run would be given, so that the
        guard can never disagree with the derivation and let through a candidate
        :class:`rubem.configuration.calibration_parameters.CalibrationParameters`
        would then refuse.

        :param vector: The free values, in the order of :attr:`free_names`.
        :type vector: collections.abc.Sequence[float] | numpy.ndarray

        :return: ``True`` when the model can be run with this candidate.
        :rtype: bool
        """
        values = np.asarray(vector, dtype=np.float64).ravel()
        if values.size != self.dimension:
            return False
        if not np.all(np.isfinite(values)):
            return False
        for value, (minimum, maximum) in zip(values, self.bounds, strict=True):
            if not minimum <= value <= maximum:
                return False

        parameters = self.to_parameters(values)
        if parameters["w_1"] + parameters["w_2"] > 1.0:
            return False
        minimum, maximum = variable_range(DERIVED_PARAMETER)
        return minimum <= parameters[DERIVED_PARAMETER] <= maximum

    def weights_constraint(self) -> "LinearConstraint | None":
        """Return the linear constraint ``w_1 + w_2 <= 1`` on the decision vector.

        The differential evolution receives it so that it never spends a model
        run on a candidate whose slope factor weight would come out negative:
        SciPy evaluates the constraint before the objective and skips the members
        that violate it. The constraint indexes the vector by position, so its
        coefficients are placed at the positions the two weights occupy in
        :attr:`free_names`.

        A search in which at most one of the two weights is free needs no
        constraint: one fixed weight turns the sum into a bound on the other,
        which :func:`decision_space` has already applied, and two fixed weights
        leave nothing to constrain.

        :return: The constraint over the decision vector, or ``None`` when fewer
            than two of the weights are searched.
        :rtype: scipy.optimize.LinearConstraint | None

        :raises ImportError: If SciPy is not installed.
        """
        positions = [
            self.free_names.index(name) for name in ("w_1", "w_2") if name in self.free_names
        ]
        if len(positions) < 2:
            return None

        from scipy.optimize import LinearConstraint

        coefficients = np.zeros((1, self.dimension), dtype=np.float64)
        for position in positions:
            coefficients[0, position] = 1.0
        return LinearConstraint(coefficients, -np.inf, 1.0)


def decision_space(
    fixed: Mapping[str, float] | None = None,
    bounds: Mapping[str, tuple[float, float]] | None = None,
    modflow: ModflowCatalog | None = None,
) -> DecisionSpace:
    """Return the decision space of one calibration.

    Without arguments the space is the whole search: the eight free parameters
    of :data:`FREE_PARAMETERS`, each between the bounds of the application
    settings.

    ``fixed`` takes parameters out of the decision vector; their values stay in
    the nine parameters every candidate is run with. ``bounds`` narrows the range
    a free parameter is searched in. Both accept the legacy spellings ``b``,
    ``w1`` and ``w2``.

    Fixing one of the two searched weights narrows the upper bound of the other
    instead of constraining the pair, so that the derived ``w_3 = 1 - w_1 - w_2``
    cannot fall below its own minimum; when that narrowing leaves the other
    weight a single value, it is fixed at that value as well and leaves the
    decision vector. Fixing both of them derives ``w_3`` once and checks it here,
    before the search starts.

    A name that starts with ``modflow.`` is a parameter of the MODFLOW section,
    looked up in ``modflow``. It has no range in the application settings, so
    it is searched only when it is bounded, after the eight parameters, and the
    bound is mandatory: finite, its minimum below its maximum and inside the
    values the parameter may take (strictly positive, and at most 1 for a
    specific yield). A fixed one keeps its value in every candidate.

    :param fixed: The parameters that are not searched, with the value every
        candidate carries. Defaults to ``None``, no fixed parameter.
    :type fixed: collections.abc.Mapping[str, float], optional

    :param bounds: The ``(minimum, maximum)`` range to search a parameter in,
        by name. Defaults to ``None``, the ranges of the application settings.
    :type bounds: collections.abc.Mapping[str, tuple[float, float]], optional

    :param modflow: The MODFLOW parameters of the configuration, ``None``, the
        default, when it does not enable MODFLOW.
    :type modflow: rubem.calibration.modflow_parameters.ModflowCatalog, optional

    :return: The decision vector of the run.
    :rtype: DecisionSpace

    :raises ValueError: If a name is not a searched parameter or is the derived
        ``w_3``, if a fixed value lies outside the range of the settings, if an
        overridden bound is not a narrower range of the settings range, if a
        fixed weight leaves the other one no admissible value, if two fixed
        weights derive a ``w_3`` outside its range, if every parameter is fixed
        and nothing is left to search, or if a MODFLOW name is given without
        ``modflow``, is not in it, or has a bound or a fixed value outside the
        values it may take.
    """
    fixed = fixed or {}
    bounds = bounds or {}
    modflow_space = _modflow_space(
        {name: value for name, value in fixed.items() if name.startswith(MODFLOW_PREFIX)},
        {name: value for name, value in bounds.items() if name.startswith(MODFLOW_PREFIX)},
        modflow,
    )
    modflow_free, modflow_fixed, modflow_bounds, modflow_names = modflow_space
    fixed_values = {
        _canonical(name, "fixed"): float(value)
        for name, value in fixed.items()
        if not name.startswith(MODFLOW_PREFIX)
    }
    overrides = {
        _canonical(name, "bounded"): value
        for name, value in bounds.items()
        if not name.startswith(MODFLOW_PREFIX)
    }

    settings_ranges = {name: variable_range(name) for name in FREE_PARAMETERS}
    effective = dict(settings_ranges)
    for name, override in overrides.items():
        if name in fixed_values:
            raise ValueError(
                f"'{name}' is fixed at {fixed_values[name]}, so a bound for it has nowhere "
                "to apply: only the free parameters are searched."
            )
        effective[name] = _narrowed(name, override, settings_ranges[name])

    for name, value in fixed_values.items():
        minimum, maximum = settings_ranges[name]
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(
                f"'{name}' cannot be fixed at {value}: the value lies outside the range "
                f"({minimum}, {maximum}) of the application settings."
            )

    free_names = tuple(name for name in FREE_PARAMETERS if name not in fixed_values)
    if not free_names and not modflow_free:
        raise ValueError(
            "Every calibration parameter is fixed, so the search has nothing to look for; "
            "leave at least one of them free."
        )

    effective.update(_weight_bounds(fixed_values, effective))
    # A fixed weight can leave the other one a single admissible value (w_1 = 1
    # leaves w_2 = 0). A parameter with one value is not searched: it joins the
    # fixed ones, so the dimension, the budget and the initial population describe
    # the search that really runs, and no coordinate of zero width reaches SciPy.
    for name in ("w_1", "w_2"):
        if name in fixed_values:
            continue
        minimum, maximum = effective[name]
        if minimum == maximum:
            fixed_values[name] = minimum
            free_names = tuple(free for free in free_names if free != name)
    if not free_names and not modflow_free:
        raise ValueError(
            "Every calibration parameter is fixed, so the search has nothing to look for; "
            "leave at least one of them free."
        )
    return DecisionSpace(
        free_names=(*free_names, *modflow_free),
        fixed={**fixed_values, **modflow_fixed},
        bounds=(*(effective[name] for name in free_names), *modflow_bounds),
        modflow_names=modflow_names,
    )


def _modflow_space(
    fixed: Mapping[str, float],
    bounds: Mapping[str, Sequence[float]],
    modflow: ModflowCatalog | None,
) -> tuple[tuple[str, ...], dict[str, float], tuple[tuple[float, float], ...], tuple[str, ...]]:
    """Return the searched and the fixed MODFLOW parameters, in the order of the catalog.

    :return: The searched names, the fixed values, the bounds of the searched
        names and every MODFLOW name of the run.

    :raises ValueError: If a name is given without a catalog or is not in it,
        if it is both fixed and bounded, or if its value or its bound lies
        outside the values the parameter may take.
    """
    given = [*fixed, *bounds]
    if not given:
        return (), {}, (), ()
    if modflow is None:
        raise ValueError(
            f"The MODFLOW parameter(s) {', '.join(given)} cannot be calibrated: the "
            "configuration does not enable MODFLOW."
        )
    for name in given:
        if name not in modflow.values:
            raise ValueError(
                f"'{name}' is not a MODFLOW parameter of this configuration. Its calibratable "
                f"MODFLOW parameters are {', '.join(modflow.names) or 'none'}."
            )
    for name in bounds:
        if name in fixed:
            raise ValueError(
                f"'{name}' is fixed at {fixed[name]}, so a bound for it has nowhere "
                "to apply: only the free parameters are searched."
            )
    for name, value in fixed.items():
        if not modflow.admits(name, value):
            raise ValueError(
                f"'{name}' cannot be fixed at {value}: the value lies outside "
                f"{modflow.domain(name)}, the values the parameter may take."
            )
    checked = {}
    for name, override in bounds.items():
        minimum, maximum = _pair(name, override)
        if not (
            minimum < maximum and modflow.admits(name, minimum) and modflow.admits(name, maximum)
        ):
            raise ValueError(
                f"The bound ({minimum}, {maximum}) of '{name}' is not a range inside "
                f"{modflow.domain(name)}, the values the parameter may take, with its minimum "
                "below its maximum."
            )
        checked[name] = (minimum, maximum)
    searched = tuple(name for name in modflow.names if name in checked)
    return (
        searched,
        {name: float(fixed[name]) for name in modflow.names if name in fixed},
        tuple(checked[name] for name in searched),
        tuple(name for name in modflow.names if name in fixed or name in checked),
    )


def _canonical(name: str, action: str) -> str:
    """Return the canonical spelling of a parameter the caller named.

    :raises ValueError: If the name is the derived weight or is not a searched
        parameter at all.
    """
    canonical = _ALIASES.get(name, name)
    if canonical == DERIVED_PARAMETER:
        raise ValueError(
            f"'{name}' cannot be {action}: the slope factor weight is derived from the "
            "other two weights (w_3 = 1 - w_1 - w_2) and is not part of the decision vector; "
            "fix or bound w_1 and w_2 instead."
        )
    if canonical not in FREE_PARAMETERS:
        raise ValueError(
            f"'{name}' cannot be {action}: it is not a searched calibration parameter. "
            f"The searched parameters are {', '.join(FREE_PARAMETERS)}."
        )
    return canonical


def _narrowed(
    name: str, override: Sequence[float], settings_range: tuple[float, float]
) -> tuple[float, float]:
    """Return an overridden bound, checked against the range of the settings.

    :raises ValueError: If the override is not a range with a minimum below its
        maximum, or if it is not contained in the range of the settings.
    """
    minimum, maximum = _pair(name, override)
    settings_minimum, settings_maximum = settings_range
    if (
        not math.isfinite(minimum)
        or not math.isfinite(maximum)
        or minimum >= maximum
        or minimum < settings_minimum
        or maximum > settings_maximum
    ):
        raise ValueError(
            f"The bound ({minimum}, {maximum}) of '{name}' is not a narrower range of its "
            f"application settings range ({settings_minimum}, {settings_maximum}): a bound "
            "narrows the settings range and its minimum lies below its maximum."
        )
    return minimum, maximum


def _pair(name: str, override: Sequence[float]) -> tuple[float, float]:
    """Return a bound as a pair of numbers.

    :raises ValueError: If the bound is not two numbers.
    """
    try:
        values = tuple(float(value) for value in override)
    except TypeError:
        # A single number instead of a pair: the same mistake as a pair of the
        # wrong length, and it is answered with the same sentence.
        raise ValueError(
            f"The bound of '{name}' must be a (minimum, maximum) pair, got {override!r}."
        ) from None
    if len(values) != 2:
        raise ValueError(
            f"The bound of '{name}' must be a (minimum, maximum) pair, got {len(values)} value(s)."
        )
    minimum, maximum = values
    return minimum, maximum


def _weight_bounds(
    fixed_values: Mapping[str, float], effective: Mapping[str, tuple[float, float]]
) -> dict[str, tuple[float, float]]:
    """Return the bounds the fixed weights impose on the weight that is left.

    With both weights searched the pair is handled by the linear constraint of
    :meth:`DecisionSpace.weights_constraint` and nothing is narrowed here. With
    one of them fixed the constraint would have a single term, which is a bound:
    the free weight may not exceed what leaves the derived ``w_3`` at or above
    its own minimum. With both of them fixed the derived weight is a number, and
    it is checked here.

    :raises ValueError: If the free weight has no admissible value left, or if
        two fixed weights derive a ``w_3`` outside its range.
    """
    derived_minimum, derived_maximum = variable_range(DERIVED_PARAMETER)
    weights = [name for name in ("w_1", "w_2") if name in fixed_values]
    if not weights:
        return {}

    if len(weights) == 2:
        derived = 1.0 - (fixed_values["w_1"] + fixed_values["w_2"])
        if not derived_minimum <= derived <= derived_maximum:
            raise ValueError(
                f"Fixing w_1 at {fixed_values['w_1']} and w_2 at {fixed_values['w_2']} derives "
                f"w_3 = {derived}, outside its range ({derived_minimum}, {derived_maximum}); "
                "the three weights must add up to 1."
            )
        return {}

    (pinned,) = weights
    free_weight = "w_2" if pinned == "w_1" else "w_1"
    minimum, maximum = effective[free_weight]
    narrowed = min(maximum, 1.0 - fixed_values[pinned] - derived_minimum)
    if narrowed < minimum:
        raise ValueError(
            f"Fixing {pinned} at {fixed_values[pinned]} leaves {free_weight} no value in its "
            f"range ({minimum}, {maximum}): the derived w_3 = 1 - w_1 - w_2 would fall below "
            f"{derived_minimum} for every one of them."
        )
    return {free_weight: (minimum, narrowed)}


def bounds() -> list[tuple[float, float]]:
    """Return the ``(minimum, maximum)`` bound of every free parameter.

    The bounds come from the application settings, in the order of
    :data:`FREE_PARAMETERS`, which is the order of the decision vector of a
    search without fixed parameters and without overridden bounds.

    :return: One ``(minimum, maximum)`` pair per free parameter.
    :rtype: list[tuple[float, float]]
    """
    return list(decision_space().bounds)


def vector_to_parameters(vector: Sequence[float] | np.ndarray) -> dict[str, float]:
    """Return the nine calibration parameters a decision vector stands for.

    The vector is the one of the default decision space, the eight free values
    in the order of :data:`FREE_PARAMETERS`; see
    :meth:`DecisionSpace.to_parameters`.

    :param vector: The eight free values, in the order of :data:`FREE_PARAMETERS`.
    :type vector: collections.abc.Sequence[float] | numpy.ndarray

    :return: The nine parameters, keyed by the names of
        :class:`rubem.configuration.calibration_parameters.CalibrationParameters`.
    :rtype: dict[str, float]

    :raises ValueError: If the vector does not have eight entries.
    """
    return decision_space().to_parameters(vector)


def parameters_to_vector(parameters: Mapping[str, float]) -> np.ndarray:
    """Return the decision vector of a set of calibration parameters.

    The vector is the one of the default decision space; see
    :meth:`DecisionSpace.from_parameters`.

    :param parameters: The calibration parameters, by name.
    :type parameters: collections.abc.Mapping[str, float]

    :return: The eight free values, in the order of :data:`FREE_PARAMETERS`.
    :rtype: numpy.ndarray

    :raises KeyError: If a free parameter is missing from the mapping.
    """
    return decision_space().from_parameters(parameters)


def is_admissible(vector: Sequence[float] | np.ndarray) -> bool:
    """Whether a decision vector describes a configuration the model accepts.

    The vector is the one of the default decision space; see
    :meth:`DecisionSpace.is_admissible`.

    :param vector: The eight free values, in the order of :data:`FREE_PARAMETERS`.
    :type vector: collections.abc.Sequence[float] | numpy.ndarray

    :return: ``True`` when the model can be run with this candidate.
    :rtype: bool
    """
    return decision_space().is_admissible(vector)


def weights_constraint() -> "LinearConstraint":
    """Return the linear constraint ``w_1 + w_2 <= 1`` on the decision vector.

    The constraint is the one of the default decision space, in which both
    weights are searched; see :meth:`DecisionSpace.weights_constraint`.

    :return: The constraint, over the eight entries of the decision vector.
    :rtype: scipy.optimize.LinearConstraint

    :raises ImportError: If SciPy is not installed.
    """
    # Both weights are searched in the default space, so the constraint is there.
    return cast("LinearConstraint", decision_space().weights_constraint())
