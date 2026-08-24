# Regression fixtures

The `base/` dataset is a small synthetic scene used exclusively for
regression testing: it exists so the model's outputs can be compared against
known goldens, not to represent any real basin. Do not use it as a modelling
example; the published basin datasets are on HydroShare
(DOI 10.4211/hs.6f3670b8cd944e7ea72e03d1b9ca928f).

- `base/maps/`, `base/txt/`: model inputs (PCRaster rasters and lookup
  tables).
- `base/out/`: golden outputs plus `SHA256SUMS`. They are regenerated only by
  `regenerate_golden.py`, on the environment frozen in `ci/golden-env.lock`;
  every change must be justified in `AUDIT.md`.
- The configuration used by the tests and by the regeneration script comes
  from `tests/helpers/config.py::base_model_config`.
