# Security Policy

## Supported Versions

Only the latest release and the current `master` branch receive security updates.

## Reporting a Vulnerability

Please report security vulnerabilities through [GitHub Security Advisories](../../security/advisories/new). Do not open a public issue for security vulnerabilities.

Reports are reviewed as soon as possible. You will receive a response within 7 days acknowledging receipt and outlining next steps.

## Known Dependency Risks

### GDAL CVEs (assessed 2026-10-11)

All platforms now select GDAL 3.13.3. The final universal `uv audit --locked`
checked 93 third-party packages and reported zero vulnerabilities or adverse
statuses on 2026-10-11. The earlier Linux GDAL 3.9.0 pin produced ten advisory
records representing the seven distinct CVEs below; that pin has been removed.

The affected components are HDF4 EOS and NetCDF drivers. Ortho4XP's raster
pipeline uses `osgeo.gdal` Python bindings for GeoTIFF, PNG, VRT and in-memory
raster operations; the old GDAL CLI subprocess path has been retired. No
intentional HDF4 or NetCDF processing occurs in these workflows. This usage
assessment does not remove the advisories or establish safety for arbitrary
untrusted files passed to GDAL's format autodetection.

| CVE | Advisory |
|-----|----------|
| CVE-2026-8084 | PYSEC-2026-2153 |
| CVE-2026-8086 | PYSEC-2026-2154 |
| CVE-2026-8087 | PYSEC-2026-2155 / GHSA-h9rh-5ffh-h669 |
| CVE-2026-8088 | PYSEC-2026-2156 / GHSA-j3f5-rw74-g4rv |
| CVE-2026-8212 | PYSEC-2026-4 / GHSA-r5m4-5vww-w9f5 |
| CVE-2026-8213 | PYSEC-2026-2157 |
| CVE-2026-49014 | PYSEC-2026-193 / GHSA-wphc-7cm7-8mf7 |

The reported fixes are available in GDAL 3.13.3. Windows wheels are supplied
by [the existing geospatial wheel vendor](https://github.com/cgohlke/geospatial-wheels/releases/tag/v2026.8.20),
and Homebrew supplies the same native version on macOS. Linux setup now builds
the checksum-verified native GDAL release through the project bootstrap before
installing its matching Python bindings. Windows runtime probes passed; native
Linux compilation and macOS execution remain verification gaps recorded in
[the alignment design](docs/superpowers/specs/2026-10-11-skills-first-alignment-design.md).
An advisory scan does not establish execution compatibility on those platforms.
