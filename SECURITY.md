# Security Policy

## Supported Versions

Only the latest release of RUBEM receives security fixes.

| Version | Supported |
| ------- | --------- |
| latest release | yes |
| older releases | no |

## Reporting a Vulnerability

Please do not open a public issue for security problems. Report them
privately through
[GitHub private vulnerability reporting](https://github.com/LabSid-USP/RUBEM/security/advisories/new)
or by email to [rubem.hydrological@labsid.eng.br](mailto:rubem.hydrological@labsid.eng.br).

Include the affected version, a description of the problem and, when
possible, a minimal reproduction. You will receive an acknowledgement within
a week; please allow the maintainers a reasonable time to release a fix
before any public disclosure.

## Verifying a release

Every release published from a `v*` tag ships, next to the wheel and the
source distribution: `SHA256SUMS.txt`; Sigstore signature bundles
(`*.sigstore.json`, one per distribution); a GitHub build provenance
attestation; `sbom.cdx.json` (CycloneDX inventory of the environment the
released wheel installs into) and `conda-inventory.json` (the conda packages
of the byte-exact regression environment, from `ci/golden-env.lock`).

```console
$ gh attestation verify rubem-<version>-py3-none-any.whl --owner LabSid-USP
$ python -m sigstore verify github rubem-<version>-py3-none-any.whl \
    --bundle rubem-<version>-py3-none-any.whl.sigstore.json \
    --repository LabSid-USP/RUBEM
```

The OpenSSF Scorecard check for signed releases considers the last five
releases, so it reports green only once five consecutive releases carry the
signatures.

