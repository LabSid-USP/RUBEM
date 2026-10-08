# Batalha: comparison of the three MODFLOW branches

`prepare.py` creates comparable configurations and derived rasters without
changing the original Batalha dataset. The source dataset is not distributed
with this example. The three `*.template.json` files show the complete
nine-month, wetting-disabled configuration, using `${dataset}` and
`${prepared}` as path placeholders. Run the preparer to obtain executable
JSON files with resolved paths and the required derived rasters.
The preparer requires PCRaster, NumPy and SciPy. SciPy is included in the
`rubem[calibration]` extra and is needed here to find nearest valid heads.

These are explicit numerical sensitivity scenarios. Reconstructed heads
are initialization estimates, not observations. Numerical convergence does
not establish geological correctness or calibration accuracy.

```sh
python examples/batalha_modflow/prepare.py \
  /path/to/RUBEM-datasets/batalha_basin /tmp/batalha-prepared \
  --months 9 --wetting off
rubem run -c /tmp/batalha-prepared/feat_356_modflow_coupling.json
```

Use `feat_modflow_module.json` in `feat_modflow_module` and
`feat_calibrator_modflow.json` in `feat_calibrator_modflow`. All three use
`nstp=1`, the original monthly window and dynamic root-depth coupling, and
PCG tolerances of 0.01 m and 0.01 m³/day. They require no validation bypass.
The old branches still have their implementation differences; the prepared
inputs do not repair their code or guarantee identical recharge.

## Declared preparation policies

The source `bauru_modflow.json` contains an invalid layer stack. All active
cells satisfy `top_model > botton3 > botton2 > botton`. The preparation
retains each original record's head/conductivity suffix and LAYCON:

| Physical layer | Prototype number | PR number | Top | Bottom | Suffix | LAYCON |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| Upper | 3 | 1 | top_model | botton3 | 3 | 1 |
| Middle | 2 | 2 | botton3 | botton2 | 2 | 2 |
| Lower | 1 | 3 | botton2 | botton | 1 | 2 |

PCRaster numbers layers from the bottom, whereas MODFLOW numbers them from
the top. Every reference to a layer is remapped, including RIV, GHB and
wetting. Recharge option 3 retains its meaning of the highest active cell;
it is not a layer number. See [PCRaster DIS](https://pcraster.geo.uu.nl/pcraster/4.4.2/documentation/modflow/dis.html).

- **Conductivity:** assume KX is the dimensionless ratio Kh/Kv, so Kh=KY
  and Kv=KY/KX. This agrees with the workbook's KH and VANIS labels and
  endpoints; the original modeler's definition of the ratio still matters.
  The convention follows [USGS LPF VKA](https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/lpf.html).
- **Storage:** interpret the current `ss.map` as Ss in 1/m. Multiply by
  each confined/convertible layer's thickness before supplying BCF Sf1;
  the top LAYCON1 layer uses `sy.map` as Sf1. The input key
  `specific_storage` in these configurations holds the dimensionless BCF
  coefficient. The current map is 1e-6, whereas the supplied parameter
  workbook lists 2e-4; this example deliberately retains the map's value.
  See [USGS BCF Sf1/Sf2](https://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/bcf.htm).
- **Initial heads:** replace only missing, nonpositive or sentinel heads
  inside the active domain with the nearest positive finite active head
  in the same layer. Preserve original positive heads, even below their
  layer bottom. Do not clamp to the bottom or top. The nearest donor may
  sit in a different elevation column, so an initialized cell can still
  start dry. `--head-donors wet` additionally restricts donors to those
  above their own bottom, without changing original positive dry heads.
  The algorithm uses [SciPy's exact distance transform](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html).
- **River:** assign each riverbed to the layer containing its elevation.
  This places 1,894 cells in the upper layer, 284 in the middle and 31 in
  the lower. Exclude the 68 riverbeds above the model top, recording them
  in `derived/river-excluded.map`; do not lower the riverbed artificially.
  This is an explicit interpretation of the supplied elevation surfaces,
  not a verified river/aquifer conceptual model.
- **GHB:** retain the original boundaries on the upper layer only. External
  GHB head is not required to lie inside that cell's elevation interval;
  do not duplicate its conductance across all three layers.
- **Cell dimensions:** retain the model's 30 m square-cell approximation.
  The source clone is geographic; the coupling sets MODFLOW row and column
  dimensions explicitly.

Every preparation writes `manifest.json` with source SHA-256 hashes,
initialization counts, river allocation/exclusion counts and assumptions.
Files ending in `-original-heads.json` preserve the source head maps with
all other preparation policies unchanged. They are deliberately unsuitable
for a production run: current PR validation must reject their no-data
sentinels without `--allow-blocking-problems`.

## Wetting sensitivity

The preparer's default is `--wetting below`, with a derived WETDRY=-1 map
so only the cell below can rewet a dry cell. `--wetting lateral` enables
both lateral and lower neighbors. `--wetting off` disables rewetting and
lets cells that dry remain inactive. Disabling it changes the represented
physics; it is a separate scenario, not an automatic numerical correction.
The positive, finite `--wetdry-threshold` argument sets the magnitude of
WETDRY in metres (default 1). Increasing this threshold changes numerical
rewetting hysteresis; the value is not an observed hydrogeologic parameter.

```sh
python examples/batalha_modflow/prepare.py \
  /path/to/RUBEM-datasets/batalha_basin /tmp/batalha-wetting \
  --months 9 --wetting below --wetdry-threshold 10 \
  --mxiter 200 --wetfct 0.1 --ihdwet 1
```

All flags are model-wide and the generated conductivity flags are uniformly
true. The example does not rely on the PCRaster extension's apparent
per-layer COMPUTE option, whose last setter call actually controls all
layers.

The original dataset also has nonblocking surface-model warnings: land-use
series gaps, DEM no-data, an inverted crop-coefficient interval and a land-use
class whose fractions sum to zero. Those inputs remain unchanged and their
warnings remain visible.

## The scientist's configuration (`--profile scientist`)

`--profile scientist` emits the configuration delivered with the dataset on
2026-10-08 (`bauru_modflow(patched).json`, which puts `bound3.map` on the top
layer) for the three branches, changing only the paths, the window and the
output directory; it derives no raster. The PR file is the same model in the
top-down schema. It serves parity checks against the prototypes, not as a
recommended setup:

- the PR refuses the 277 + 18 `-888` initial heads that stay active in the
  two lower layers, so run it with `rubem run -c ... --allow-blocking-problems`
  (`allow_blocking_problems=True` in the API);
- its PCG closure (HCLOSE 20 m, RCLOSE 10 m³/day) accepts the quiet phase of a
  wet/dry limit cycle at the one top-layer cell left active 81 m below its
  bottom (row 15, column 231); the same inputs fail the first substep at
  1 m / 1 m³/day or stricter on every branch;
- `KX` (4.81–5.19, the workbook's vertical anisotropy) enters as horizontal
  conductivity and `ss.map` (1e-6) as the unscaled storage coefficient, as
  delivered.

```sh
python examples/batalha_modflow/prepare.py \
  /path/to/RUBEM-datasets/batalha_basin /tmp/batalha-scientist \
  --months 9 --profile scientist
rubem run -c /tmp/batalha-scientist/feat_356_modflow_coupling.json --allow-blocking-problems
```

Measured with these files (nine months): the two prototypes complete with
identical outputs; the PR completes with the same MODFLOW budgets, heads within
0.51 m of the prototypes and baseflow 2.2 % lower over the window, because the
prototypes report the river leakage of the last native time step for the whole
month while the PR integrates its substeps.

## Optional integration check

```sh
RUBEM_DATASET_DIR=/path/to/RUBEM-datasets \
  pytest tests/integration/test_batalha_modflow.py -q
```

This runs two months for each explicit scenario: rewetting disabled and
rewetting from below with a 10 m threshold, WETFCT=0.1 and IHDWET=1. It
validates the original-head refusal, checks MODFLOW convergence and
water-budget discrepancy, and compares monthly baseflow against the
independently reported river-exchange rates. It skips when the external
dataset or `mf2005` is unavailable.
The 10 m scenario has no rewetting events in its first three months and
matches the wetting-disabled outputs over that interval. All three branches
failed PCG convergence in month four when repeated WET/DRY conversions
began. Passing the two-month check therefore does not demonstrate stable
rewetting over the full nine-month window.
The 1 m threshold with the original WETFCT=1, IHDWET=0 and MXITER=2000
also failed in the first month, with repeated wet/dry transitions and a
reported budget discrepancy of 0.2200%. Increasing the iteration limit
alone did not resolve that scenario.

The nine-month wetting-disabled exercise with these prepared inputs completed
on all three branches. After remapping layer numbers and output names, the
168 common rasters and nine surface-model CSV files were numerically identical
between the PR and both prototypes. The prototypes also wrote eight `mfdrv`
rasters containing the previous month's water-table head; the PR reports
current water-table head and the resulting effective root depth instead.
The top layer's dry cells increased from 4,197 to 4,498. This illustrates why
convergence with rewetting disabled must not be interpreted as proof that the
wetting-enabled conceptual model is solved.
