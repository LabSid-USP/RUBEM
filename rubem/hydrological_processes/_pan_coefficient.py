"""The Class A pan coefficient (kp) formula, shared by the model and the preprocessing tools.

The formula is equation S29 of the supplementary document (PDF page 9)::

    kp = 0.482 + 0.024 ln(B) - 0.000376 U2 + 0.0045 UR

where ``B`` is the Class A pan border width (the fetch distance) in meters,
between 20 and 30 m, ``U2`` is the average wind speed at 2 m above the ground
surface in m/s and ``UR`` is the relative humidity in %.

The expression is written once, with the natural logarithm injected by the
caller, so that the model (PCRaster fields, :func:`pcraster.ln`) and the
preprocessing tools (numpy arrays, :func:`numpy.log`) evaluate the same terms
in the same order.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

INTERCEPT = 0.482
FETCH_DISTANCE_COEFFICIENT = 0.024
WIND_SPEED_COEFFICIENT = 0.000376
RELATIVE_HUMIDITY_COEFFICIENT = 0.0045

RECOMMENDED_FETCH_DISTANCE_RANGE = (20.0, 30.0)
"""Fetch distance range of the supplement, in meters."""


def pan_coefficient(
    fetch_distance: Any,
    wind_speed: Any,
    relative_humidity: Any,
    *,
    log: Callable[[Any], Any],
) -> Any:
    """Return the Class A pan coefficient (kp) of equation S29.

    Every argument may be a number, a numpy array or a PCRaster field, as long
    as ``log`` is the natural logarithm of that type; the result has the type
    the arithmetic produces.

    :param fetch_distance: Class A pan border width (B) [m], 20 to 30.
    :param wind_speed: Average wind speed at 2 m above the ground (U2) [m/s].
    :param relative_humidity: Relative humidity (UR) [%].
    :param log: Natural logarithm of the caller's type (``numpy.log``,
        ``pcraster.ln``, ``math.log``).
    :returns: Class A pan coefficient (kp) [-].
    """
    return (
        INTERCEPT
        + FETCH_DISTANCE_COEFFICIENT * log(fetch_distance)
        - WIND_SPEED_COEFFICIENT * wind_speed
        + RELATIVE_HUMIDITY_COEFFICIENT * relative_humidity
    )
