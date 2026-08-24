Release Notes
=============

This is the list of changes to RUBEM between each release. For full details, see the commit logs on the `Github page <https://github.com/LabSid-USP/RUBEM>`__.

For a list of known issues and their fixes, visit the `Github issues page <https://github.com/LabSid-USP/RUBEM/issues>`__.

Unreleased
----------

- Fixed the regression test oracle (corrected fixture inputs, structured
  comparators, byte-exact reproduction on a frozen environment).
- Packaged RUBEM with ``pyproject.toml``: ``pip install`` support, the
  ``rubem`` console script and a single PEP 440 version source.
- Replaced the PyInstaller bundles with sdist/wheel distributions verified by
  the release pipeline.
- Rebuilt the CI (lint, OS/Python matrix, documentation build, packaging
  smokes) and updated the documentation build mechanics.
- Stopped changing the process working directory during a run; time series
  and raster outputs are addressed by absolute paths.
- Enabled time series per output variable and made the CSV conversion
  transactional over the run's own ``.tss`` files.
- Exported time series only after a successful run, replaced library
  ``print()`` calls with log records, and fixed the output summary flags.
- Failed clearly when the first NDVI or land-use raster cannot be read.
- Gave ``rubem.cli.main`` an argument list parameter, removed the PyInstaller
  launcher module, and made the GeoTIFF writer reject unsupported formats.
  Run the model with ``rubem`` or ``python -m rubem``; executing the package
  directory as a script (``python rubem``) is no longer supported.
- Honoured ``RASTER_FILE_FORMAT.map_raster_series`` (PCRaster maps can now be
  disabled; a configuration with output variables but no raster format is
  rejected), added the optional ``RASTER_FILE_FORMAT.no_data_value`` for the
  GeoTIFF series (default ``-9999``), and matched raster series file names
  with the prefix taken literally.
- Added the optional ``RASTERS.georeference`` raster whose coordinate
  reference system is written to the GeoTIFF outputs; the clone and the
  georeference must share the DEM geometry, rotated grids are refused when
  PCRaster maps are written, and a GeoTIFF that cannot be written is removed
  instead of being left half-written.
- Corrected the spelling of ``Interception.get_reflectances_simple_ratio``,
  ``soil_moisture_content_wilting_point`` and the ``rubem.file._file_conversions``
  module; the old names still work for one minor release and emit a
  ``DeprecationWarning``.
- Moved the package to ``pathlib`` (enforced by ruff's ``PTH`` and ``UP``
  rules); every public path parameter accepts ``str`` or ``os.PathLike``,
  and ``bytes`` paths are deprecated (accepted with a ``DeprecationWarning``
  for one minor release).
- Rebuilt the configuration value objects (``SimulationPeriod``,
  ``RasterGrid``, ``CalibrationParameters``, ``InitialSoilConditions``,
  ``ModelConstants``) as frozen Pydantic models with the same keywords,
  attributes and messages; ``pydantic`` is now a runtime dependency. New
  checks: the grid size must be finite with a finite square, the FPAR bounds
  must satisfy ``0 < min < max < 1`` and ``lai_max`` must be positive.
- Rebuilt the output configuration objects as Pydantic models:
  ``OutputVariables`` holds ``OutputVariable`` objects (attribute access; the
  dictionary-style ``get()`` is deprecated), ``OutputDataDirectory`` creates
  the directory in ``ensure_exists()`` rather than on construction, and
  ``OutputRasterBase.from_file()`` reads the geometry.
- Rebuilt the input file objects (``InputRasterFiles``, ``InputRasterSeries``,
  ``InputTableFiles``) as frozen Pydantic models with the same keywords,
  attributes and exceptions; validation problems are ``Problem`` objects and
  ``ConfigurationError`` carries the blocking ones.
- Added content validation of the inputs (skipped with ``-s``): lookup tables
  must parse, ``dg``, ``Zr``, ``Tsat``, ``manning`` and the rainy days must be
  positive, the rainy days must cover the twelve months, ``Tcc > Tw`` for
  every class; ``kp`` must be positive and NDVI below 1 in every cell,
  ``ndvi_max > ndvi_min`` per cell, sample identifiers contiguous from 1; the
  precipitation, ETP and Kp series must cover every simulated step and the
  NDVI and land use series the first one. Blocking problems raise
  ``ConfigurationError``; ``kc_max < kc_min``, later NDVI/land use gaps and
  area fractions not adding up to 1 are reported as warnings.
- Rebuilt the application settings as a plain Pydantic model
  (``AppSettings.default()`` selects the ``PYTHON_ENVIRONMENT`` file at call
  time; the ranges singleton is gone) and made the command line report an
  invalid configuration with its message instead of a traceback.
- Added ``ModelConfigurationFile``, the legacy JSON file as a validated
  model: the spellings found in circulating files are accepted as aliases
  (``K_sat``, ``T_ini``, ``w1``, ``kcmin``, ...), unknown keys are reported and
  ignored, duplicated keys are reported (the last value still wins), and
  relative paths are anchored on the directory of the JSON file
  (``ModelConfiguration.load(path)``) or on an explicit ``base_dir``.
- Moved the command line to Typer: ``rubem run -c <config> [-s]`` runs a
  simulation and ``rubem config schema --format legacy`` prints the JSON
  Schema of the configuration file; ``rubem -c <config>`` still works for one
  minor release with a deprecation warning. ``typer`` is a runtime dependency.

Version 0.9.0-beta.3
---------------------

**Date**: Mar 21, 2024

- `@soaressgabriel <https://github.com/soaressgabriel>`__ Fix unsuccessful execution without station locations map (`#123 <https://github.com/LabSid-USP/RUBEM/pull/123>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Implement a configuration system within the application that can handle multiple formats (`#103 <https://github.com/LabSid-USP/RUBEM/pull/103>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Fix error in the description of the series of rasters resulting from the model simulation (`#129 <https://github.com/LabSid-USP/RUBEM/pull/129>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Rename "Total Runoff" resulting raster series to "Accumulated Total Runoff" (`#130 <https://github.com/LabSid-USP/RUBEM/pull/130>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Remove unused input directory specification from doc pages (`#134 <https://github.com/LabSid-USP/RUBEM/pull/134>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [tests] Add integration test for Sphinx documentation build (`#136 <https://github.com/LabSid-USP/RUBEM/pull/136>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [tests] Migrate tests from `unittest` to `pytest` (`#137 <https://github.com/LabSid-USP/RUBEM/pull/137>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Add validation rules for input rasters (`#111 <https://github.com/LabSid-USP/RUBEM/pull/111>`__);
- `@dependabot <https://github.com/dependabot>`__ [actions] Bump actions/checkout from 2 to 4 (`#138 <https://github.com/LabSid-USP/RUBEM/pull/138>`__);
- `@dependabot <https://github.com/dependabot>`__ [actions] Bump github/codeql-action from 1 to 3 (`#139 <https://github.com/LabSid-USP/RUBEM/pull/139>`__);
- `@dependabot <https://github.com/dependabot>`__ [actions] Bump actions/setup-python from 2 to 5 (`#140 <https://github.com/LabSid-USP/RUBEM/pull/140>`__);
- `@dependabot <https://github.com/dependabot>`__ [actions] Bump conda-incubator/setup-miniconda from 2 to 3 (`#141 <https://github.com/LabSid-USP/RUBEM/pull/141>`__);
- `@dependabot <https://github.com/dependabot>`__ [actions] Bump actions/stale from 3 to 9 (`#142 <https://github.com/LabSid-USP/RUBEM/pull/142>`__);
- `@dependabot <https://github.com/dependabot>`__ [actions] Bump codecov/codecov-action from 2 to 4 (`#143 <https://github.com/LabSid-USP/RUBEM/pull/143>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [doc] Add Zenodo DOI badges to README and documentation (`#145 <https://github.com/LabSid-USP/RUBEM/pull/145>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Add optional specification of a LDD raster in the model simulation configuration (`#132 <https://github.com/LabSid-USP/RUBEM/pull/132>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Make timespans human-readable (`#148 <https://github.com/LabSid-USP/RUBEM/pull/148>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Fix checking for files in the output directory when it doesn't exist (`#149 <https://github.com/LabSid-USP/RUBEM/pull/149>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [readthedocs] Fix Read the Docs Sphinx build (`#152 <https://github.com/LabSid-USP/RUBEM/pull/152>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Wrap PCRaster's raster file, raster series and lookup table reading functions (`#153 <https://github.com/LabSid-USP/RUBEM/pull/153>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Remove DEM raster (GeoTIFF) from simulation configuration and model report (`#154 <https://github.com/LabSid-USP/RUBEM/pull/154>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Make sample points raster in model simulation configuration optional (`#150 <https://github.com/LabSid-USP/RUBEM/pull/150>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Enable export of the resulting Total Runoff (RNF) raster series and time series (`#147 <https://github.com/LabSid-USP/RUBEM/pull/147>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [doc] Update Code of Conduct links (`#160 <https://github.com/LabSid-USP/RUBEM/pull/160>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [doc] Update README with latest information and links to doc (`#161 <https://github.com/LabSid-USP/RUBEM/pull/161>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [doc] Update copyright information in LICENSE file (`#162 <https://github.com/LabSid-USP/RUBEM/pull/162>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [doc] Use Citation File Format `CITATION.cff` instead of BibTeX entries (`#164 <https://github.com/LabSid-USP/RUBEM/pull/164>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Configure logging settings based on a configuration file (`#156 <https://github.com/LabSid-USP/RUBEM/pull/156>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Rename `modules` to `hydrological_processes` and update imports (`#165 <https://github.com/LabSid-USP/RUBEM/pull/165>`__);
- `@dependabot <https://github.com/dependabot>`__ [actions] Bump softprops/action-gh-release from 1 to 2 (`#168 <https://github.com/LabSid-USP/RUBEM/pull/168>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Refactor codebase and adopt common conventions of open source Python projects (`#167 <https://github.com/LabSid-USP/RUBEM/pull/167>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [readthedocs] Update build os  and Python versions in `.readthedocs.yaml` (`#177 <https://github.com/LabSid-USP/RUBEM/pull/177>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [readthedocs] Fix Read the Docs Sphinx build II (`#175 <https://github.com/LabSid-USP/RUBEM/pull/175>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Implement Relative import for source files within model directory (`#172 <https://github.com/LabSid-USP/RUBEM/pull/172>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Add check if selected GDAL driver is available before using it (`#173 <https://github.com/LabSid-USP/RUBEM/pull/173>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Implement start date alignment for input raster series (`#178 <https://github.com/LabSid-USP/RUBEM/pull/178>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [actions] Update build release workflow (`#185 <https://github.com/LabSid-USP/RUBEM/pull/185>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ Improve handling of file paths for absolute paths internally (`#187 <https://github.com/LabSid-USP/RUBEM/pull/187>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [actions] Fix file paths in `build-release.yml` (`#188 <https://github.com/LabSid-USP/RUBEM/pull/188>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [actions] Fix zip file path in build-release workflow (`#189 <https://github.com/LabSid-USP/RUBEM/pull/189>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__ [actions] Update hash computation command in `build-release.yml` (`#190 <https://github.com/LabSid-USP/RUBEM/pull/190>`__);

Version 0.2.3-beta.2
---------------------

**Date**: Jan 24, 2024

- `@soaressgabriel <https://github.com/soaressgabriel>`__: Fix error in the implementation of the Total Discharge equation (`#106 <https://github.com/LabSid-USP/RUBEM/pull/106>`__);

Version 0.2.2-beta.1
---------------------

**Date**: May 17, 2023

- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add Paraíba do Sul dataset (`#86 <https://github.com/LabSid-USP/RUBEM/pull/86>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Update 'Initial Soil Conditions' subsection of the 'Soil Parameters' section of the user guide (`#88 <https://github.com/LabSid-USP/RUBEM/pull/88>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Update citation information (`#90 <https://github.com/LabSid-USP/RUBEM/pull/90>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add missing information about conditions in the mathematical formulation of the model (`#92 <https://github.com/LabSid-USP/RUBEM/pull/92>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Update Sphinx documentation settings and packages (`#82 <https://github.com/LabSid-USP/RUBEM/pull/94>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Incorporate RuntimeError exception handling and logging in file reading operations (`#98 <https://github.com/LabSid-USP/RUBEM/pull/98>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Implement GitHub Actions Workflow for Building and Releasing Application (`#99 <https://github.com/LabSid-USP/RUBEM/pull/99>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Update of Issue and Pull Request Templates (`#101 <https://github.com/LabSid-USP/RUBEM/pull/101>`__);

Version 0.1.3-alpha
-------------------

**Date**: March 23, 2022

- `@soaressgabriel <https://github.com/soaressgabriel>`__: Fix errors and inconsistencies in doc pages (`#82 <https://github.com/LabSid-USP/RUBEM/pull/82>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Update copyright strings (`#81 <https://github.com/LabSid-USP/RUBEM/pull/81>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Replace download links for the datasets (`#80 <https://github.com/LabSid-USP/RUBEM/pull/80>`__);


Version 0.1.0-alpha
-------------------

**Date**: November 23, 2021

- `@soaressgabriel <https://github.com/soaressgabriel>`__: Update module doc string (`#27 <https://github.com/LabSid-USP/RUBEM/pull/27>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add usage of configuration file via CLI (`#6 <https://github.com/LabSid-USP/RUBEM/pull/6>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add reportMapSeries function (`#29 <https://github.com/LabSid-USP/RUBEM/pull/29>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add user help documentation (`#60 <https://github.com/LabSid-USP/RUBEM/pull/60>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add bug issue, feature request issue and pull request templates (`#67 <https://github.com/LabSid-USP/RUBEM/pull/67>`__); 
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add export format configuration (`#31 <https://github.com/LabSid-USP/RUBEM/pull/31>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add dynamic readout of land use map-series files (`#30 <https://github.com/LabSid-USP/RUBEM/pull/30>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Add check if genTss files is enabled (`#50 <https://github.com/LabSid-USP/RUBEM/pull/50>`__);
- `@LINAMARIAOSORIO <https://github.com/LINAMARIAOSORIO>`__: Add documentation strings to code (`#57 <https://github.com/LabSid-USP/RUBEM/pull/57>`__);
- `@LINAMARIAOSORIO <https://github.com/LINAMARIAOSORIO>`__: Add input data preprocessing scripts (`#58 <https://github.com/LabSid-USP/RUBEM/pull/58>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Fix header of the CSV files (`#33 <https://github.com/LabSid-USP/RUBEM/pull/33>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Fix area measurement unit (`#36 <https://github.com/LabSid-USP/RUBEM/pull/36>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Fix bug that did not consider the entire month in the simulation (`#39 <https://github.com/LabSid-USP/RUBEM/pull/39>`__);
- `@LINAMARIAOSORIO <https://github.com/LINAMARIAOSORIO>`__: Fix unusual values of the Recharge (`#43 <https://github.com/LabSid-USP/RUBEM/pull/43>`__);
- `@LINAMARIAOSORIO <https://github.com/LINAMARIAOSORIO>`__: Fix types of argument and return variables of functions in their docstrings (`#79 <https://github.com/LabSid-USP/RUBEM/pull/79>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Adopt new project file structure (`#52 <https://github.com/LabSid-USP/RUBEM/pull/52>`__);
- `@LINAMARIAOSORIO <https://github.com/LINAMARIAOSORIO>`__: Remove Soil Porosity parameter (`#44 <https://github.com/LabSid-USP/RUBEM/pull/44>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Remove white background from favicon from user help page (`#70 <https://github.com/LabSid-USP/RUBEM/pull/70>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Refactoring unit tests (`#77 <https://github.com/LabSid-USP/RUBEM/pull/77>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Refactoring of core module (`#76 <https://github.com/LabSid-USP/RUBEM/pull/76>`__);
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Review of the source code base (`#5 <https://github.com/LabSid-USP/RUBEM/pull/4 and https://github.com/LabSid-USP/RUBEM/pull/5>`__); 
- `@soaressgabriel <https://github.com/soaressgabriel>`__: Clean up the source code base (`#18 <https://github.com/LabSid-USP/RUBEM/pull/18>`__);

