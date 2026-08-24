# Golden fixture audit

## Why the goldens changed

The regression configuration in `tests/integration/test_cli.py` mapped
`TABLES.k_sat` to `txt/soil/Tsat.txt`, the same file already used for
`t_sat`, so the model never read the saturated hydraulic conductivity
fixture `txt/soil/Kr.txt`. The mapping was corrected and the goldens were
regenerated once with `tests/fixtures/regenerate_golden.py`.

## Generating environment and recipe

- Base commit: `fb740f51aeaa38c45f93dd011078f954e2804bfd` (`main`)
- Generator: the `exact` CI job on a GitHub-hosted runner of the `ubuntu-24.04`
  image (version `20260816.277.1`), in the environment created from
  `ci/golden-env.lock` (conda explicit spec with MD5; linux-64, Python 3.13.7,
  pcraster 4.4.2, gdal 3.11.5, numpy 2.3.4) named `golden`, running
  `python tests/fixtures/regenerate_golden.py` from the repository checkout
  (the project has no packaging metadata at this commit). The regenerated
  `tests/fixtures/base/out/` was promoted from the job's `golden-out` artifact.
- Why the runner is the generator: byte identity of the outputs depends on
  the C library and CPU of the executing host (identical conda packages
  produce different last-bit floats under different glibc/libm builds), so
  the canonical byte-exact environment is the CI runner image itself. Any
  other machine, including developer workstations, compares semantically.
- Runner pin: the job declares `runs-on: ubuntu-24.04`, never `ubuntu-latest`,
  so the platform cannot move to the next LTS image without an explicit change
  here, and it prints the host fingerprint (image version, glibc, CPU model)
  before reproducing, so a failure names the host that changed. Within an image
  version the pool is still heterogeneous, which is accepted: the byte-exact
  job guards the provenance of the goldens, while correctness is guarded by the
  semantic comparison that runs on the whole matrix. If the image (or its
  glibc) does move and the bytes change, regenerate on the new image and record
  the new provenance and impact in this file; do not relax the assertion.
- Determinism: the regeneration was executed twice on the same runner
  (regeneration step plus the byte-exact test's own rerun) and twice locally;
  each host reproduces its own bytes exactly. The promoted bytes were also
  reproduced by the `exact` job of the next commit, which ran on a different
  host of the same image (Azure `westus3` vs `westcentralus`), so the goldens
  are not bound to one physical machine of the pool.
- Byte-exact reproduction is asserted by the `exact` CI job
  (`RUBEM_EXACT_GOLDEN=1 pytest -m exact`) on that environment only; every
  other environment compares semantically with `rtol=1e-5`, `atol=1e-8`.
  Those defaults are calibrated to cross-environment Float32 noise: variables
  that no input change touches differ by up to ~3e-5 in absolute value between
  PCRaster/GDAL/Python builds and hosts, while real regressions (see the
  table below) sit orders of magnitude above 1e-5 relative. Georeferencing is
  not a data value and does not use those tolerances: geotransform components
  are compared with `rtol=0` and an absolute tolerance of one millionth of a
  pixel, so a misregistered output cannot pass on numerically identical
  cells.
- The goldens cover all three output families the configuration enables: the
  PCRaster raster series, the GeoTIFF raster series (18 files, added when the
  oracle gained GeoTIFF coverage; the legacy goldens never tracked them) and
  the time-series CSVs. The tss CSVs use CRLF line endings as written by the
  model; a scoped `.gitattributes` rule (`tests/fixtures/base/out/** -text`)
  keeps git from normalizing any golden byte.

## Impact of the correction (legacy vs regenerated)

Maximum absolute difference over valid (non-nodata) cells/values:

| Variable | Rasters | Time series CSV |
|---|---|---|
| itp | 3.051758e-05 | 0.0 |
| bfw | 2.769636e+01 | 1.427834e+01 |
| srn | 1.721894e-01 | 4.937000e-02 |
| eta | 5.181419e+01 | 1.270600e+00 |
| lfw | 4.381500e+01 | 2.936500e+01 |
| rec | 4.381500e+01 | 2.936500e+01 |
| smc | 1.492464e+02 | 9.440000e+01 |
| rnf | 7.151136e+01 | 4.091924e+01 |
| arn | 2.810858e+01 | 2.374000e+01 |

The soil-, baseflow- and runoff-related variables change materially because
the corrected `Kr.txt` values differ from `Tsat.txt`; interception (`itp`)
does not depend on `k_sat` and only shows Float32-level noise from the
change of generating environment relative to the legacy goldens.

## Legacy golden checksums (before this regeneration)

```
9b03293d225604ce34f535b4d3174a2f4f91905669c12396ca0cf4f76d5fa4cd  arn00000.001
c20521385afa24566b956c65afbe9b9a3173176b8f79a262e88f2f301b026f49  arn00000.002
a6801c6a16a0033a87e8ea657a328edc492df732863c37c96ab2b84545294f7a  bfw00000.001
dca4245849fb2376afe0bc3313b5ddeb88a573601f4d83e3d6088ab9949fb49b  bfw00000.002
021e156f87f94e3f867739e0ce40960e03292beb8912d5cfbfe37ed229fa0539  eta00000.001
23ce3115b79ae3d88d7d754a5458fbfe816c92bd4ce8515828ddfea96e5d9ad7  eta00000.002
2a17b3b281ca3307a4f26a300faf891e0233f2b45dec74786007810c13305b27  itp00000.001
07075cdc639f07e38b9f3f0036ca7efecc851921d62fdba7a82d4d352528fcb9  itp00000.002
b99b8d35fd8f54f4f0c6778167e4b2d30be4b47be2aa92b0aea936314a3fbd5d  lfw00000.001
ee95247e2d6a6de4267097edbb69de5f9805532037d36d3cf4cc77e1ffc69b6f  lfw00000.002
b99b8d35fd8f54f4f0c6778167e4b2d30be4b47be2aa92b0aea936314a3fbd5d  rec00000.001
ee95247e2d6a6de4267097edbb69de5f9805532037d36d3cf4cc77e1ffc69b6f  rec00000.002
9b3d6701d7194e1fc4e927793e949f91f92e1fc5b5f561aadff5d3b99b1929f6  rnf00000.001
7fac5378237ef9016e97c246282e9757db74424d9b8e9f33df4aa164ff7e723c  rnf00000.002
1db162e6fabc6799a4bef3cdd226d7dbaf3f0a30b657d06627f158c48f89e585  smc00000.001
1401e61918c5cd56c3e91aa26bfc6742108995f0028ec43252a6bcaca6d8c825  smc00000.002
ffb298d0df31c7966991fc40c0bcb2dbd4a53d4e63b61127b89c6d45334de643  srn00000.001
df4aadd8513f856fd5b49ab84b7f02355c92165e860d3587e4735bcfe6eaea3a  srn00000.002
2d4b0983d841b93b0c25369fffcb43303ef37f7a4b2c80eb5e980175c7f49131  tss_arn.csv
d679f14a4aac09eb82349be5f453f05c6237a19d491012381863fac8f2c39cde  tss_bfw.csv
3901797e9e706c197df90f741a2e919c98153db601e5a8a9f9cfc53014713f39  tss_eta.csv
977cc147b927df56cc5afd7dbc6b8dc3d800d492917bc149a5507799a376e3e4  tss_itp.csv
6971d44ee51bde4b4dbdab56b3cf263a2c360ec721b0bfe7578b5ac556835e56  tss_lfw.csv
6971d44ee51bde4b4dbdab56b3cf263a2c360ec721b0bfe7578b5ac556835e56  tss_rec.csv
edc1e831c4fc0d590c1ca38d07fdfe2755d7c5428e678d18ae44f847aaa306c5  tss_rnf.csv
e33ea72c5e8ed1451b11eb5532ebbbe6871adb3bb616899a9fe82fdd0db52404  tss_smc.csv
4e50e3665998c39bee21f1308215f464134764da74866203c568cd404cfca071  tss_srn.csv
```

The current checksums live in `tests/fixtures/base/out/SHA256SUMS` and are
guarded by `tests/integration/test_golden_integrity.py`. Any future golden
change must update this file with the new justification and impact summary.
