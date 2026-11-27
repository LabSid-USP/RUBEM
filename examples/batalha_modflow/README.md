# Batalha: comparison of the three MODFLOW branches

`prepare.py` creates comparable configurations and derived rasters without
changing the original Batalha dataset. The source dataset is the scientist's
unpublished delivery, not distributed with this example; the layout and the
bytes it is checked against are described under
[The dataset](#the-dataset-the-delivery-of-2026-11-03). The three
`*.template.json` files show the shape of the configuration in each branch,
using `${dataset}` and `${prepared}` as path placeholders. Run the preparer to obtain executable JSON files with resolved
paths and the derived rasters. It requires PCRaster, NumPy and SciPy (the
`rubem[calibration]` extra; SciPy finds the nearest valid heads).

The preparer starts from the configuration the scientist delivers with the
dataset (`--source`, default `<dataset>/bauru_modflow.json`, written in the
prototype branches' bottom-up schema) and writes the same physical model for
the three branches: `feat_modflow_module.json`, `feat_calibrator_modflow.json`
and `feat_356_modflow_coupling.json` (the PR, top-down schema). The window is
`--months` monthly steps from `--start` (default 01/08/2023). When the delivered
series begin earlier than the window, `--first-step N` names the source step of
the window's first month and the preparer writes `derived/series/<name>/` with
symbolic links (copies where links are refused) to the source rasters, taking
for each step the latest raster at or before it (the land-use series has one
raster per year): the historical dataset delivered on 2026-10-29 starts in
August 2000, so August 2023 is `--first-step 277`. `--station ROW,COL` writes
`derived/samples-station.map` with a new sample id on that 1-based cell, for
`rubem calibrate --stations`; the DAEE station 6D-007 lies on the channel cell
(137, 241). When the listed `ndvi_max`/`ndvi_min` files are missing, the maps of
the same name in the NDVI series directory are used and the manifest records
the repair under `ndvi_extremes_repaired`. PCRaster numbers layers from the
bottom, whereas MODFLOW and the PR number them from
the top; every layer reference is remapped, including RIV, GHB and wetting.
Recharge option 3 keeps its meaning of the highest active cell. See
[PCRaster DIS](https://pcraster.geo.uu.nl/pcraster/4.4.3/documentation/modflow/dis.html).

These are explicit numerical sensitivity scenarios. Derived heads are
initialization estimates, not observations. Numerical convergence does not
establish geological correctness or calibration accuracy.

## `--profile scientist`

Emits the delivered configuration unchanged for the three branches: only
the paths, the simulation window (`--start`, `--months`, `--first-step`) and
the output directory are rewritten, and no raster is derived. It reproduces
the scientist's own runs for parity checks; it is not a recommended setup:

- the PR refuses the `-888` initial heads that stay active in the two lower
  layers (the manifest counts them), so run it with
  `rubem run -c ... --allow-blocking-problems` (`allow_blocking_problems=True`
  in the API);
- `KX` (the workbook's vertical anisotropy) enters as horizontal conductivity
  and `ss.map` as the unscaled storage coefficient, as delivered;
- with the delivered solver (HCLOSE 20 m, RCLOSE 10 m³/day) the nine months
  measured on 2026-10-08 close only because the criterion accepts the quiet
  phase of a wet/dry limit cycle at the one top-layer cell left active 81 m
  below its bottom (row 15, column 231).

```sh
python examples/batalha_modflow/prepare.py \
  /path/to/datasets/batalha_basin /tmp/batalha-scientist \
  --source /path/to/datasets/batalha_basin/bauru_modflow_t_ini_jul25_hist_x065.json \
  --months 9 --first-step 277 --profile scientist
rubem run -c /tmp/batalha-scientist/feat_356_modflow_coupling.json --allow-blocking-problems
```

Measured with the files of 2026-10-08 (nine months; that delivery's series
started in August 2023, so it needed no `--first-step`): the two prototypes
complete with identical outputs; the PR completes with the same MODFLOW
budgets, heads within 0.51 m of the prototypes and baseflow 2.2 % lower over
the window, because the prototypes report the river leakage of the last native
time step for the whole month while the PR integrates its substeps.

## `--profile answered` (default)

Applies the scientist's answers of 2026-10-13 to the questions raised on
2026-10-08, deriving the rasters they require into `derived/`. Every policy
and every altered cell count is written to `manifest.json`.

| Physical layer | Prototype number | PR number | Top | Bottom | Head suffix | K suffix (`base3`) | LAYCON |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Upper | 3 | 1 | top_model | botton3 | 3 | 1 | 1 |
| Middle | 2 | 2 | botton3 | botton2 | 2 | 2 | 2 |
| Lower | 1 | 3 | botton2 | botton | 1 | 3 | 2 |

- **Conductivity (answers 1 and 2):** `KX` is the dimensionless vertical
  anisotropy `Kh/Kv`, already "transformed into the anisotropy"; `Kh = KY`
  and `Kv = KY/KX` in m/day, the latter written as `derived/kv-<layer>.map`.
  The scientist's rule for the suffixes is that the base layer has one
  conductivity class and the other two have two: `KX3`/`KY3` hold a single
  value and `HK3.txt` one class, so `--conductivity base3` (default) gives
  suffix 3 to the base and suffix 1 to the top; `--conductivity as-delivered`
  keeps suffix `n` on prototype layer `n`, as in the delivered JSON. The
  extension computes the transmissivity and the vertical leakance from these
  two maps ([PCRaster BCF](https://pcraster.geo.uu.nl/pcraster/4.4.3/documentation/modflow/bcf.html)).
- **Storage (answer 3):** `ss.map` (1e-6) is the dimensionless confined
  storage coefficient `Sf1` and enters unscaled; the top `LAYCON` 1 layer
  reads `sy.map` as `Sf1`
  ([USGS BCF Sf1/Sf2](https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/bcf.htm)).
- **Initial heads (answers 4 and 9):** in the two lower layers, the `-888`
  cells are dry cells of the source model; every active cell without a
  positive finite head takes the nearest one in the same layer
  ([SciPy's exact distance transform](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html))
  and stays active, so it can wet again. In the top layer, negative heads on
  active cells take `head2.map` at the same cell (none are active under
  `bound3.map`, which the manifest records as zero), and heads above
  `top_model.map`, the DIS top, are cut at the surface. The nearest donor
  may sit in a different elevation column, so a filled cell can still start
  dry; the manifest counts them.
- **River (answer 8):** the delivered entries, on the top layer.
- **GHB (answers 8 and 11), `--ghb`:** `none` disables the package (the
  scientist's first preference); `top` keeps the delivered entry; `full`
  repeats the delivered maps on the three layers, which triples the column
  conductance; `split` (option B of question 11) puts
  `derived/ghb-conductance-third.map` (`ghb_cond/3`) on each layer, so the
  column keeps the map's conductance, as the map was computed for the whole
  saturated thickness. The PR GHB entry has no scale factor, hence the
  derived map.
- **Wetting repairs around cell (15, 231) (answer 5), `--wetting-fixes`:**
  `a1` repairs the active top-layer heads below the layer bottom with the
  middle-layer head of the same cell; `a2` deactivates those cells in a
  derived boundary map and zeroes their WETDRY in a derived wetting map, so
  they never rewet; `d` sets IHDWET 1, with which a rewetted cell starts at
  `BOT + WETFCT · WETDRY`
  ([USGS BCF IHDWET](https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/bcf.htm)).
  The manifest lists the cells concerned.
- **Wetting strategy (answer 6, option D), `--wetting`:** `as-delivered`
  keeps `wet.map` (WETDRY +1 m: a dry cell rewets from the cell below or
  from the four lateral neighbours); `below` writes `derived/wetting-below.map`
  with the sign negated, so only the cell below can rewet a dry cell; `off`
  disables rewetting, and cells that dry stay inactive, which changes the
  represented physics
  ([USGS BCF WETDRY](https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/bcf.htm)).
- **Solver and time stepping (answers 6 and 7):** `--hclose`, `--rclose`,
  `--mxiter`, `--iter1`, `--damp`, `--nstp`, `--wetfct` and `--iwetit`
  override the delivered values; the manifest records the result.
- **Cell dimensions:** the model's 30 m square-cell approximation is kept.
  The source clone is geographic; the coupling sets MODFLOW row and column
  dimensions explicitly.

```sh
python examples/batalha_modflow/prepare.py \
  /path/to/datasets/batalha_basin /tmp/batalha-answered \
  --source /path/to/datasets/batalha_basin/bauru_modflow_t_ini_jul25_hist_x065.json \
  --months 24 --first-step 277 --station 137,241 --nstp 1 \
  --ghb none --wetting-fixes a1,a2 --wetting off --hclose 0.01 --rclose 0.01
rubem run -c /tmp/batalha-answered/feat_356_modflow_coupling.json
```

This is the configuration the scientist decided on 2026-10-26 (NSTP 1, the
closure with the smallest budget discrepancy, GHB off as the baseline and
split as the sensitivity case). Run exactly like this on 2026-10-29, it
completed the 24 months with a budget discrepancy of 0.00 % in every step,
and the three branches wrote byte-identical outputs. That run read the copy
of 2026-10-29, which differs from the delivery of 2026-11-03 in the
`kcmax`/`kcmin` tables and the NDVI extremes (see below), so its outputs are
not those of the 2026-11-03 bytes.

The PR configuration of this profile passes validation without
`--allow-blocking-problems`. The remaining non-blocking warnings are inherited
from the dataset: on the delivery of 2026-11-03, DEM no-data, a land-use class
whose fractions sum to zero, river beds outside their layer's elevation
interval and a few filled middle-layer heads below the layer bottom; with the
`kcmax`/`kcmin` tables of `batalha_basin.zip` (class 25: 0.2 and 0.7), an
inverted crop-coefficient interval as well, and, without `--first-step`
links, land-use series gaps.

The earlier `reconstructed` profile (2026-09-28: `Sf1 = Ss × thickness`,
river beds assigned by elevation, GHB on the top layer, wetting from below)
was superseded by answers 3, 8 and 11 and removed.

## The dataset: the delivery of 2026-11-03

The Batalha inputs are the scientist's unpublished delivery of 2026-11-03,
not one of the published RUBEM datasets. It came as two archives, and both
are needed, in this layout:

```text
<datasets>/batalha_basin/
  bauru_modflow_t_ini_jul25_hist_x065.json   from batalha_basin.zip
  Qobs-sim.xlsx, calibracao/, arquivos_drain/ from batalha_basin.zip
  bauru_lai_max_tiago.json                    from batalha_basin.zip
  input/                                      from batalha_basin_hist.zip
```

`batalha_basin_hist.zip` holds the historical series (`prec_hist`,
`etp_hist`, `kp_hist`, `ndvi_hist`, `cob_hist`, 313 monthly steps from August
2000, so August 2023 is step 277) and the static inputs. The `input/` of
`batalha_basin.zip` has only the earlier 24-month folders, and the preparer
stops on it with `FileNotFoundError` for `input/ndvi_hist`. The 454 files
under the `input/` of `batalha_basin.zip` are all in the historical archive
too, and three differ: `input/dem/dem.map.aux.xml`, which no model reads, and
`input/text/landuse/kcmax.txt` and `kcmin.txt`, where class 25 is 0.2 and 0.7
in `batalha_basin.zip` but 0.7 and 0.2 in the historical archive.
`batalha_basin.zip` (17,718,872 bytes, SHA-256
`a53cf9bbc6ed98dd071c3cf9b4039babf19429054cf980f77ac423e7834aa056`, 471
files) extracts to a directory named `Dataset/`; `batalha_basin_hist.zip`
(565,130,305 bytes, SHA-256
`0d159aeca8f946b98f679201a006423934e86bb3a8c53d1b2b4c303b9739c5e6`, 4,825
files) extracts to `input/`. Extract the first, rename `Dataset/` to
`batalha_basin/`, then extract the second inside `batalha_basin/` so that its
`input/` replaces the 24-month one; the historical archive's class-25
coefficients are the ones in use. The reverse order leaves the inverted
coefficients of `batalha_basin.zip` in place.

The delivered JSON names `input/ndvi/ndvi_max.map` and `ndvi_min.map`, from
the earlier NDVI folder, which this layout has, so the preparer uses that
pair. A copy without `input/ndvi/` (such as the one the runs of 2026-10-29
read) makes the preparer fall back to the pair in `ndvi_hist/` and record the
repair in `manifest.json` under `ndvi_extremes_repaired`; the two pairs differ
(`ndvi_min` basin mean 0.43 in `ndvi/`, 0.33 in `ndvi_hist/`).

`delivery-2026-11-03.sha256` lists the SHA-256 of 153 delivery files: the
145 the 24-month window from August 2023 reads (the JSON, every file its
`RASTERS`, `TABLES` and `MODFLOW` sections name, both NDVI extreme pairs, and
the series rasters of steps 277 to 300, `cob_hist` steps 277 and 289), plus
`input/dem/ldd.map` and the other tables under `input/text/`, which identify
the delivery but are not read. The extra calibration maps in `input/modflow`
and the GDAL `.aux.xml` sidecars, which PCRaster does not read and GDAL may
rewrite, are left out. The JSON's bytes include its paths, so a copy whose
JSON was rewritten for another machine is listed as differing. Check a copy
with `sha256sum`, or regenerate the list:

```sh
cd /path/to/datasets/batalha_basin
sha256sum --check /path/to/RUBEM/examples/batalha_modflow/delivery-2026-11-03.sha256
python /path/to/RUBEM/examples/batalha_modflow/prepare.py . --hashes \
  --source bauru_modflow_t_ini_jul25_hist_x065.json --first-step 277 --months 24
```

The preparer records the SHA-256 of the files the prepared window reads in
`manifest.json` under `source_sha256`.

## Optional integration check

```sh
RUBEM_DATASET_DIR=/path/to/datasets \
  pytest tests/integration/test_batalha_modflow.py -q
```

`RUBEM_DATASET_DIR` names the directory that holds `batalha_basin/` in the
layout above. The test reads `bauru_modflow_t_ini_jul25_hist_x065.json` by
name, derives the source step of August 2023 from its `SIM_TIME.start`, and
skips, naming the file and the layout, when it is absent. CI never sets the
variable, so CI never runs this test; there the coupling is covered by the
unit and integration tests that drive `mf2005` on synthetic grids.

This runs two months of three scenarios: the delivered configuration (which
must be refused without the bypass and closes at the delivered 20 m /
10 m³/day), and the answers with GHB off and with GHB split, both with the
three wetting repairs, rewetting from below only and 1 m / 1 m³/day. With the
corrected conductivities the delivered criterion no longer closes the first
substep (the wet/dry cycle at cell (15, 231) reaches 72 m of head change) and,
once repaired, leaves budget discrepancies of 2–6 % in some substeps. Measured
on 2026-10-18 over 24 months: 1 m / 1 m³/day with rewetting from below keeps
the discrepancy below 0.1 % but fails in month 12, when about thirty thin
active cells dry at the end of the dry season and rewet from the middle layer
every third iteration; 0.01 m / 0.01 m³/day closes all 24 months only with
rewetting off (discrepancy at most 0.03 %), with the same baseflow as the
loose criterion. The test checks MODFLOW convergence and requires every
listing's water-budget discrepancy to stay below 1 %, the closure the
scientist accepted on 2026-10-26; that is a numerical sanity bound, not
calibrated accuracy. The largest value measured is 0.16 %, in the first
stress period of the delivery of 2026-09-23 (NSTP 5, with 0.06 % in the
second period); in this two-month window on the delivery of 2026-11-03 it is
at most 0.02 % in the three cases (measured on 2026-11-03). Over longer
windows the scientist's own configuration reaches 0.11 % (24 months,
2026-10-18) and 0.12 % (the first 24 of 300 months, 2026-11-03), still within
the bound. The test also compares monthly baseflow against
the independently reported river-exchange rates and checks the manifest. It
compares the `source_sha256` of the prepared manifest (the files the
two-month window read) with `delivery-2026-11-03.sha256`: on a copy whose bytes differ, or that lacks a
file the window reads, it does not fail for that reason but emits a
`DeliveryCopyWarning` naming the paths, so that the verdict is labelled as one
on another copy, and it skips the exact cell counts that hold for the
delivered bytes (filled heads, clipped heads, the station's sample id). It
skips when the external dataset or `mf2005` is unavailable. Passing two
months does not demonstrate stable rewetting over a longer window.
