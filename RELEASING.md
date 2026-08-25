# Releasing RUBEM

Releases are cut from `main` by pushing a `v*` tag; the pipeline builds
nothing on its own but promotes the artifacts CI already verified.

1. Make sure `main` is green (`ci-success`) and the changelog's *Unreleased*
   section lists everything since the previous release.
2. Set the version in `rubem/__init__.py` (PEP 440: `0.10.0b1`, `0.10.0`) and
   in `CITATION.cff`; move the *Unreleased* entries under a new
   `Version <x.y.z>` heading with the date; open a pull request and merge it.
3. Tag the merge commit and push the tag:

   ```console
   $ git tag -a v0.10.0b1 -m "RUBEM 0.10.0b1"
   $ git push origin v0.10.0b1
   ```

4. The `Release` workflow then runs `ancestry` (the tag must be on `main`),
   the reusable CI, `verify` (the built wheel installs, its version equals the
   tag, the no-natives smoke passes) and `publish` (SBOM, conda inventory,
   Sigstore signatures, build provenance attestation, checksums, GitHub
   release with generated notes; pre-releases are flagged from the version).
5. Verify the published artifacts as described in `SECURITY.md`.

Rehearse the pipeline on a fork before the first release of a new line.
Publishing to PyPI is out of scope; users install the wheel from the release
into a conda environment that provides PCRaster and GDAL.
