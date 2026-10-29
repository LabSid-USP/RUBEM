# Batalha: comparison of the three MODFLOW branches

`prepare.py` creates comparable configurations and derived rasters without
changing the original Batalha dataset. The source dataset is not distributed
with this example. The three `*.template.json` files show the shape of the
configuration in each branch, using `${dataset}` and `${prepared}` as path
placeholders. Run the preparer to obtain executable JSON files with resolved
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
the repair. PCRaster
numbers layers from the bottom, whereas MODFLOW and the PR number them from
the top; every layer reference is remapped, including RIV, GHB and wetting.
Recharge option 3 keeps its meaning of the highest active cell. See
[PCRaster DIS](https://pcraster.geo.uu.nl/pcraster/4.4.3/documentation/modflow/dis.html).

These are explicit numerical sensitivity scenarios. Derived heads are
initialization estimates, not observations. Numerical convergence does not
establish geological correctness or calibration accuracy.

## `--profile scientist`

Emits the delivered configuration unchanged for the three branches: only
the paths, the simulation window (`--months`, 2 to 24 from August 2023) and
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
  /path/to/RUBEM-datasets/batalha_basin /tmp/batalha-scientist \
  --months 9 --profile scientist
rubem run -c /tmp/batalha-scientist/feat_356_modflow_coupling.json --allow-blocking-problems
```

Measured with these files (nine months, 2026-10-08): the two prototypes
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
  /path/to/RUBEM-datasets/batalha_basin /tmp/batalha-answered \
  --source /path/to/RUBEM-datasets/batalha_basin/bauru_modflow_t_ini_jul25_hist_x065.json \
  --months 24 --first-step 277 --station 137,241 --nstp 1 \
  --ghb none --wetting-fixes a1,a2 --wetting off --hclose 0.01 --rclose 0.01
rubem run -c /tmp/batalha-answered/feat_356_modflow_coupling.json
```

This is the configuration the scientist decided on 2026-10-26 (NSTP 1, the
closure with the smallest budget discrepancy, GHB off as the baseline and
split as the sensitivity case). Run exactly like this on 2026-10-29, it
completed the 24 months with a budget discrepancy of 0.00 % in every step,
and the three branches wrote byte-identical outputs.

The PR configuration of this profile passes validation without
`--allow-blocking-problems`. The remaining non-blocking warnings are inherited
from the dataset: land-use series gaps, DEM no-data, an inverted
crop-coefficient interval, a land-use class whose fractions sum to zero, river
beds outside their layer's elevation interval and a few filled middle-layer
heads below the layer bottom.

The earlier `reconstructed` profile (2026-09-28: `Sf1 = Ss × thickness`,
river beds assigned by elevation, GHB on the top layer, wetting from below)
was superseded by answers 3, 8 and 11 and removed.

## Optional integration check

```sh
RUBEM_DATASET_DIR=/path/to/RUBEM-datasets \
  pytest tests/integration/test_batalha_modflow.py -q
```

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
loose criterion. The test checks MODFLOW convergence and water-budget discrepancy,
compares monthly baseflow against the independently reported river-exchange
rates, and checks the manifest. It skips when the external dataset or
`mf2005` is unavailable. Passing two months does not demonstrate stable
rewetting over a longer window.
