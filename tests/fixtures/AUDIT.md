# Golden fixture audit

## 2026-09: the interception zero-precipitation guard (partial regeneration)

`Interception.get_interception` protects the interception-rate equation
`I_R = 1 - exp(-I_D * d_p / P_m)` against a zero monthly precipitation by
replacing `P_m` with `1e-5` in the denominator. The guard was written as
`prec = P * (P != 0) + (P * (P == 0) + 0.00001)`, whose `+ 0.00001` sits
outside the conditional term, so every positive precipitation reached the
denominator as `P + 1e-5 mm` instead of `P` (issue #319). The guard is now
`pcr.ifthenelse(P != 0, P, 1e-5)`: positive precipitation is used unchanged
and the epsilon only applies where `P == 0`.

Only the 28 goldens whose bytes moved were replaced; the other 17 keep the
bytes of the previous regeneration:

- `itp`, `srn`, `smc`, `rnf`, `arn` at timesteps 1 and 2 and `bfw`, `eta`,
  `lfw`, `rec` at timestep 2, as `.001`/`.002` maps and `.tif`.

Timestep 1 of `bfw`, `eta`, `lfw` and `rec` is untouched because none of them
reads the interception of the current step: the first-step evapotranspiration,
lateral flow and recharge depend on the initial soil moisture only, and the
first-step baseflow on the initial storage. The `tss_*.csv` series are
bit-identical because the sampled values are written with six significant
digits and the change is four orders of magnitude below that.

### Generating environment of the replaced files

- Base commit: branch `fix_319` (`9bcdb32`, the interception guard fix).
- Generator: `python tests/fixtures/regenerate_golden.py` in the environment
  created from `ci/golden-env.lock` plus `ci/golden-pip.lock` (micromamba,
  environment name `golden`; linux-64, Python 3.13.7, pcraster 4.4.2,
  gdal 3.11.5, numpy 2.3.4), run in a Docker container of the `ubuntu:24.04`
  image (glibc 2.39-0ubuntu8.8, x86_64, Intel Core i5-9300H) on a developer
  workstation.
- Why this host is acceptable as the generator: before promoting anything the
  container reproduced the previous goldens' exact digests for all 45 files on
  `main` (`RUBEM_EXACT_GOLDEN=1 pytest tests -m exact` passed), and the
  regenerated set matches, digest by digest, the 28 values the `exact` job on
  `ubuntu-24.04` reported for this branch (run 33662562795) while the 17
  untouched files keep their previous digests. The promoted bytes are
  therefore the runner's bytes.
- The `ubuntu-24.04` runner image remains the canonical reference: if the
  `exact` job ever disagrees with these bytes, the runner is right and the
  goldens must be regenerated there, recording the new provenance here.

### Impact of the correction (previous goldens vs regenerated)

Maximum absolute difference over valid (non-nodata) cells/values, both runs
executed on the same host so the numbers isolate the formula change from
cross-environment float noise. The correction removes a `1e-5 mm`
perturbation of the denominator, so the differences are numerical noise of
that order; the semantic comparison of the CI matrix (`rtol=1e-5`, `atol=1e-8`)
rejected the previous goldens on a single cell of `srn00000.001` (`7.6e-6`
absolute on a value of `0.359 mm`, a relative difference of `2.1e-5`); every
other cell of the 28 files is within tolerance.

| Variable | Rasters | Time series CSV |
|---|---|---|
| itp | 3.051758e-05 | 0.000000e+00 |
| bfw | 5.722046e-06 | 0.000000e+00 |
| srn | 3.051758e-05 | 0.000000e+00 |
| eta | 1.525879e-05 | 0.000000e+00 |
| lfw | 1.144409e-05 | 0.000000e+00 |
| rec | 1.144409e-05 | 0.000000e+00 |
| smc | 2.441406e-04 | 0.000000e+00 |
| rnf | 3.051758e-05 | 0.000000e+00 |
| arn | 9.536743e-07 | 0.000000e+00 |

### Checksums replaced by this change

```
arn00000.001    ce57ba29d78d4ee34478846feddd5174989cbb98424597c881ecf1d15590ea71 -> d69e08b361d806a0f7ce12355da07e528877c45bad172a2e7e62bbed02bd7e5c
arn00000.002    4cd64f93219c0bec9d916c776d09437ee514ede9e4aaf4a6007a1657291151ee -> 42f869b0d426de4c9001d270d988dc8831f4e56633c75d4d688021309b016938
arn0000001.tif  7514c4f592ede4d784a0c5740b4eb70f5bb125e2ba3ac5f6f23d001abdaacc56 -> 6af5d1a876be6b787cd39435d5649cb39d275abab931b7da70267d5af67c31f2
arn0000002.tif  5c36bb78a75dbbe93e6b50f7ae1ac3964362caedb7ee8e8786501e50c751a10b -> d20f9aea086718715e1df574903a6b42ad1eb5e8e4169f92aaeeb2ac17094661
bfw00000.002    4f97716a4e12d5e1c638a5a92f1916ecbf86a673ed8483fad97662951b0aa8c0 -> 25337dc1a07283fcc20d4ed41b59ae1a41ea2bf6d9bb044145bde50b4a181b03
bfw0000002.tif  a9c06de4a637b314a268aba5f52b71d7f0ffa85bedd527e9faa570e3d4646393 -> 850869ad708803604fc0be62a11d779a757050a2b89f6ef6359ca4524aeae508
eta00000.002    eedd02e76c13a715935b4208e7633e42ce90dd965d080b9869c362c1c69f28d2 -> 3b1a7c1dba5550dd63ad074aba0cf8a4ceb14cb22912863b7c04e85736288c89
eta0000002.tif  207bec5bf17a648dac95abacd37a5e8d5f097ba389ba2de26db205684b519518 -> 36755552d3baba98ce31b4faeddb56ed45b14c42c143c348ecdab196e2f471c7
itp00000.001    e23b3a20a6dfb17643232de55fb662abadce20e1b1ede8ebdcefc1685502b31e -> 07d20fc6a916a1a6e1d0f05e50a0148c4e46f114973fc3ec8bb8c7b55eed7f4d
itp00000.002    3db154ca40886199a76cbc79134bde30f316af0a88762bcd48042fc57c6251e3 -> 1e75cd897feb5b4294ae26e1d6d4a5b296bab3cb680d177c421ef160c2d0c13c
itp0000001.tif  d26cb8e35d219d42d9e9bbc85ed4894e571d050846e62e147c0bbd1998f4084e -> 7d2cae4cb721207804665ea17e740ee22e80a0f9d8428ceb97d045f3fb2c8f01
itp0000002.tif  70833d07a35986f41568f99c3c761724a149da391957ae0438e84ecd474515a4 -> 053fecb91d9c1accecc4c55c39ecfca7876a1c62dfd8026cc8c40e70f2a302c4
lfw00000.002    39b63a64601417381974d2d867c7804c232e318f281ff776c6fb1024101530fa -> 0b26a24974dd6a624c53d1934b4f2e435e081876eb9232b86bb7d2342efc5168
lfw0000002.tif  6368a08f67f1149c7769fa7370521fad92475503203faec27e6ce135186c8ff2 -> 3e97bfae3a463d6d03be84e56de99095238605689ffcb0c2bcb90ca9752a8fc5
rec00000.002    39b63a64601417381974d2d867c7804c232e318f281ff776c6fb1024101530fa -> 0b26a24974dd6a624c53d1934b4f2e435e081876eb9232b86bb7d2342efc5168
rec0000002.tif  6368a08f67f1149c7769fa7370521fad92475503203faec27e6ce135186c8ff2 -> 3e97bfae3a463d6d03be84e56de99095238605689ffcb0c2bcb90ca9752a8fc5
rnf00000.001    33964839e235df79aeffb88b739d038a623018d40b78ba828b67c76737d9a7b0 -> 1bb10b7857af3444e4d514ed4d1c0e98eba5a8d8044749d26e17e0e6cb2fdcef
rnf00000.002    d75b07fc85708ccf5a2da774946dc5e2b534b59caf228c1838ddfb660e5870a3 -> 5050acb87e16ae3fa887d8c3d382ba4c2687670ea06a24c3383a7daa9b1abf74
rnf0000001.tif  0277d8ab6cd0f63c64b6891d7dc24a5259778736b63e14aba28c4d023834ac8d -> 32366dd15e0472a338482c4c89beb26d6a490015cd537f6a9612310b7fc3829e
rnf0000002.tif  e5bf7e18e4dac6c726947f0bf7f60f3cd70927aec882eeb43c566b2c5d40fec9 -> cec71d479de16248ab43390e67754e7bec0faad670ed358c51c012db3bf2395a
smc00000.001    ebea49d1c10a5f765077200189fc1e522db1ff18afd151ab25da78e4581276c2 -> 12093112fe0a0cb6386f95689b4e85ffebd9dfdebb6594ab6d2d7154c67f1530
smc00000.002    877cab02bbeeb0c8be4190f8ae3a4e2fde65793fb8ef2cb9cf15cd95e807fb36 -> 06b243cb7506be05ab28ccd42dd9308bf959a4f22de73e681e37945fbc74e2a6
smc0000001.tif  65ca77bc7f41d3d9921384948a5c8ed412f934b08f4026e2b95bc9831430760c -> 8ae6eda9e3c3f58ff4be6274a35f44825f29c4788a788b65662e611c467dc20a
smc0000002.tif  9d8ead92ec46bf7dd074eda97e2acbf1371c055aa803884b84f1bfbf96f4546d -> efcec70afcf36c1be13225c4b044bffb9eaea887d1837247b01189840bc38a13
srn00000.001    fcd21ad7fa2da8ff4a1d0256eecc579c9cab0fab2c974a15abcbdc37a5f31c5c -> 7cd60c400e55d1273c4153bb0fe4908bbfb39afe83ce678adeba25d866e7637c
srn00000.002    35fc364b2e309f007aedf027433e1947bb28ce99014ffc4d4cad073022b3f0ac -> 5a816daf6ab93c21b0ea54cad56c00a52a1ca013da54681cf35aa81643fc4c69
srn0000001.tif  12574eb21b4f3a0fe2f8a9337fc8dae824f196bf96e4c467afe8e9cc98c6bff3 -> 5bfdd75f8b6eecc6283af426a18e1e20e5bb2e8915311f8326935e7e30988975
srn0000002.tif  cf608b6e227a2ee934b0988eb616ce67ef6c3c549acd936b0bafdf4a2d6d3de8 -> 6df7eedabfdc7be1be614ab5edd80406291da71267f74c1c0b9b86ed67ac253d
```

## 2026-08: the Ch soil moisture unit correction (partial regeneration)

`SurfaceRunoff.get_coef_soil_moist_conditions` converted the actual soil
moisture content from mm to a fraction (`Tur / (Dg * Zr * 10)`) before
dividing it by the saturation point. That conversion was wrong: the caller
already passes `soil_moist_content_sat_point` in mm (`_dynamic_model.py`
builds it as `tusat * Dg * Zr * 10`), so Ch compared a fraction against a
depth and came out smaller than it should be by a factor of
`(Dg * Zr * 10) ** beta` — with this fixture's `Dg` (1.25-1.64), `Zr`
(22-92 cm) and `beta` (0.5), a factor of roughly 24 to 39. Ch multiplies
`(P - I)` directly in `get_surface_runoff`, with no clipping, so the surface
runoff was suppressed by that factor. The division was removed and Ch is now
the mm/mm ratio `(Tur / Tursat) ** beta`.

Only the 12 goldens whose values actually moved were replaced; the other 33
keep the bytes of the previous regeneration, so the diff of this change is
exactly the affected variables:

- `srn`, `smc`, `rnf`, `arn` at timestep 2, as `.002` map, `.tif` and
  `tss_*.csv`.

Timestep 1 is untouched because the fixture sets `t_ini = 1.0`, so the
initial soil moisture equals the saturation point and `get_surface_runoff`
takes its saturated branch (`srn = P - I`), which does not read Ch. The
variables that do not depend on Ch (`itp`, `bfw`, `eta`, `lfw`, `rec`) are
bit-identical.

### Generating environment of the replaced files

- Base commit: branch `fix_318` (`eab4553`, the Ch soil moisture unit fix).
- Generator: `python tests/fixtures/regenerate_golden.py` in the environment
  created from `ci/golden-env.lock` plus `ci/golden-pip.lock` (micromamba,
  environment name `golden`; linux-64, Python 3.13.7, pcraster 4.4.2,
  gdal 3.11.5, numpy 2.3.4), run on Ubuntu 24.04.2 under WSL2 on a developer
  workstation (glibc 2.39-0ubuntu8.4, x86_64, Intel Core i7-12700H).
- Why this host is acceptable as the generator: byte identity is a property of
  the C library and CPU, not of the machine, so a host is a valid generator
  only if it reproduces the runner's bytes. That was verified before promoting
  anything: the run produced the previous goldens' exact digests for the 37
  files this change does not touch, and the exact digests the `exact` job on
  `ubuntu-24.04` reported for the 8 files it does, so the promoted bytes are
  the runner's bytes. `RUBEM_EXACT_GOLDEN=1 pytest tests -m exact` passes in
  this environment.
- The `ubuntu-24.04` runner image remains the canonical reference: if the
  `exact` job ever disagrees with these bytes, the runner is right and the
  goldens must be regenerated there, recording the new provenance here.

### Impact of the correction (previous goldens vs regenerated)

Maximum absolute difference over valid (non-nodata) cells/values, both runs
executed on the same host so the numbers isolate the formula change from
cross-environment float noise:

| Variable | Rasters | Time series CSV |
|---|---|---|
| itp | 0.000000e+00 | 0.000000e+00 |
| bfw | 0.000000e+00 | 0.000000e+00 |
| srn | 1.026310e+02 | 3.522971e+01 |
| eta | 0.000000e+00 | 0.000000e+00 |
| lfw | 0.000000e+00 | 0.000000e+00 |
| rec | 0.000000e+00 | 0.000000e+00 |
| smc | 1.026310e+02 | 3.523000e+01 |
| rnf | 1.026310e+02 | 3.522970e+01 |
| arn | 2.423833e+01 | 1.820190e+01 |

### Checksums replaced by this change

```
srn00000.002    83165b7a643e73f62f7724681863f591a31c3b45c19b875601d621a9b56bb2e6 -> 35fc364b2e309f007aedf027433e1947bb28ce99014ffc4d4cad073022b3f0ac
smc00000.002    88999e794f1625cb03e418a7335e8eea853c7bc84f2f57fef36d001204aeb3ba -> 877cab02bbeeb0c8be4190f8ae3a4e2fde65793fb8ef2cb9cf15cd95e807fb36
rnf00000.002    058580a89fb1137e61abcd9c7aa74399963cc03c208a80605c1b752b03749694 -> d75b07fc85708ccf5a2da774946dc5e2b534b59caf228c1838ddfb660e5870a3
arn00000.002    59d42872d6adc7cf5a0a7da4e8daacfeb8f3c5be53c79bc8981af141d46aaaa2 -> 4cd64f93219c0bec9d916c776d09437ee514ede9e4aaf4a6007a1657291151ee
srn0000002.tif  a2f624db3e41808be94e02f549fe0363db7faf65fc06d6fe461073a4d26e288a -> cf608b6e227a2ee934b0988eb616ce67ef6c3c549acd936b0bafdf4a2d6d3de8
smc0000002.tif  46d96253aa9047be531a02597cd350c65ac97db438f0194571842d38563a903d -> 9d8ead92ec46bf7dd074eda97e2acbf1371c055aa803884b84f1bfbf96f4546d
rnf0000002.tif  21a583574ea1af17882fb35c77ee37cb18b112b7929b6daa5ec2ee3ff22ca80f -> e5bf7e18e4dac6c726947f0bf7f60f3cd70927aec882eeb43c566b2c5d40fec9
arn0000002.tif  8fc702536057758ce89d0e76a6328b42e0744378cde29999901a6a75493a2c79 -> 5c36bb78a75dbbe93e6b50f7ae1ac3964362caedb7ee8e8786501e50c751a10b
tss_srn.csv     fa87eaf67f6b23cec33776c3c76d4164d50663542e531c117a8abb6f1abf441e -> 66da9bb684f1873d1739588853c1f8109b35f295354022c32f8975499357e5fe
tss_smc.csv     ea3c1d32cb8892d74a1d375c352fead84e83e4d591e8ad345cede2f4e68928b8 -> 95c54fc37ae5f5ff7e277aabe3d2fe0ebb2101aae620971c0e86065b87a94e9c
tss_rnf.csv     70e7bb1ce8dba75795cede407eff3dd445721812165ff85f554bf3bca42bf714 -> 2882d376e33facd35295ccf2d059e843316252a69489080382bab33f21e6c1ba
tss_arn.csv     b44aa9fcb00b450e1dda4c00b082335de2c775da951ad5b13402f1e8326031c3 -> a51bdb9c3ca82657f10ea5bb545bf8036fd35716b5c9db6bcd751b1485428531
```

## The k_sat lookup table correction

The regression configuration in `tests/integration/test_cli.py` mapped
`TABLES.k_sat` to `txt/soil/Tsat.txt`, the same file already used for
`t_sat`, so the model never read the saturated hydraulic conductivity
fixture `txt/soil/Kr.txt`. The mapping was corrected and the goldens were
regenerated once with `tests/fixtures/regenerate_golden.py`.

### Generating environment and recipe

- Base commit: `fb740f51aeaa38c45f93dd011078f954e2804bfd` (`main`)
- Generator: the `exact` CI job on a GitHub-hosted runner of the `ubuntu-24.04`
  image (version `20260816.277.1`, glibc 2.39), in the environment created from
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
  reproduced by three later runs of the `exact` job (glibc 2.39-0ubuntu8.8) on
  hosts in `westus3` and `eastus2` rather than the generating `westcentralus`,
  covering both CPU vendors of the hosted pool (an AMD EPYC 9V74 and an Intel
  Xeon Platinum 8573C), so within an image version the goldens are not bound to
  one machine or one CPU.
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

### Impact of the correction (legacy vs regenerated)

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

### Legacy golden checksums (before this regeneration)

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

## Known input inconsistencies

- `txt/lulc/kcmax.txt` gives land use class 25 a maximum crop coefficient
  (0.2) below its minimum (`kcmin.txt`: 0.7); class 25 occurs in the land use
  rasters. The goldens encode this behaviour, so the legacy loader reports
  `kc_max < kc_min` as a warning rather than rejecting the configuration.
