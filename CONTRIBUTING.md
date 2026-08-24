# Contributing to RUBEM

Thanks for your time and willingness to contribute to RUBEM! This page gives
a few guidelines.

## General questions

Please do not use the issue tracker for support questions. Use
[GitHub Discussions](https://github.com/LabSid-USP/RUBEM/discussions) or send
your questions to our [e-mail](mailto:rubem.hydrological@labsid.eng.br).

## Reporting bugs and requesting features

Bugs and feature requests are tracked on the GitHub
[issue tracker](https://github.com/LabSid-USP/RUBEM/issues). Before opening
an issue:

- Check that the bug or request has not been filed already (search the open
  and closed issues);
- Use the matching issue form and fill in every requested field. For bugs, a
  small reproducible test case is the best possible report;
- For security problems, follow the [security policy](SECURITY.md) instead of
  opening a public issue.

## Development environment

PCRaster and GDAL come from conda-forge; everything else installs with pip:

```sh
conda env create -f environment.yml  # micromamba: micromamba create -f environment.yml -y
conda activate rubem                 # micromamba: micromamba activate rubem
pip install -e '.[dev]'
```

## Working on a change

- Every pull request answers an open issue: discuss the change in an issue
  first, and reference it from the pull request (`Resolve #N`);
- Keep pull requests small and focused; stacked pull requests are welcome
  when a change builds on another one (name the base branch in the PR);
- Follow the existing code style. `ruff check .` and `ruff format .` must be
  clean; CI enforces both at a pinned version;
- Add or update tests for every change. Markers: `unit`, `integration`,
  `slow`, `exact` (the byte-exact golden reproduction, CI-only). Run the
  suite with `pytest`;
- The golden regression fixtures under `tests/fixtures/base/out/` are
  regenerated only by `tests/fixtures/regenerate_golden.py` on the frozen
  golden environment, and every change to them must be justified in
  `tests/fixtures/AUDIT.md`;
- Update the documentation when behavior changes; `sphinx-build -W` must stay
  clean (`pip install -e '.[docs]'`, then build `doc/source`).

## Commit and pull request style

- Imperative, capitalized commit subjects without a trailing period
  ("Add lateral flow validation");
- Fill in the pull request template, including how the change was tested;
- CI (`ci-success`) must be green before review.

## Code of Conduct

Please abide by the
[Code of Conduct](https://github.com/LabSid-USP/.github/blob/main/CODE_OF_CONDUCT.md)
when interacting with the project.
