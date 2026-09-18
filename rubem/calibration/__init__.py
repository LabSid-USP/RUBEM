"""Automatic calibration of the model parameters against observed streamflow.

The package holds the objective function (Nash-Sutcliffe efficiency over the
sample stations), the decision vector of the free calibration parameters, the
worker that evaluates one candidate, and the runner that drives SciPy's
differential evolution.

Importing this package does not import SciPy: the optional dependency is
imported inside the functions that need it, so that reading a series or
computing an efficiency works in an installation without the
``rubem[calibration]`` extra.
"""
