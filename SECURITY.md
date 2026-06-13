# Security Policy

## Supported Versions

Only the latest release and the current `master` branch receive security updates.

## Reporting a Vulnerability

Please report security vulnerabilities through [GitHub Security Advisories](../../security/advisories/new). Do not open a public issue for security vulnerabilities.

Reports are reviewed as soon as possible. You will receive a response within 7 days acknowledging receipt and outlining next steps.

## Known Dependency Risks

### GDAL CVEs (assessed 2026-06-13)

The following GDAL CVEs are flagged by `uv audit` for the pinned versions
(3.9.0 Linux, 3.12.2 Windows, 3.12.3 macOS). All four target HDF4 EOS or
NetCDF format drivers that Ortho4XP does not use. Ortho4XP uses GDAL only for
GeoTIFF warp/translate and Web Mercator projection via `gdal_translate` and
`gdalwarp`. No HDF4 or NetCDF processing occurs in any workflow.

| CVE | Component | CVSS | Exposure |
|-----|-----------|------|----------|
| CVE-2026-8212 | `hdf-eos/SWapi.c` | 5.5 | None |
| CVE-2026-8088 | `hdf-eos/GDapi.c` | 5.5 | None |
| CVE-2026-8087 | `hdf-eos/GDapi.c` | 7.8 | None |
| PYSEC-2026-193 | `netcdf/netcdfsg.cpp` | 7.8 | None |

GDAL 3.13.1 fixes all four but has no binary wheels on PyPI for any platform.
This assessment will be revisited when `uv audit` is integrated into the
maintenance-qa pipeline and GDAL wheels become available.
