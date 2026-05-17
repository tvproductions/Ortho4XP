# Source Data Formats

Repo-owned structured source data is JSON-backed and validated with Pydantic at
load time. Filenames keep the legacy source extension before `.json` so the
format lineage remains visible:

- `Providers/<region>/<name>.lay.json`
- `Extents/<region>/<name>.ext.json`
- `Filters/<name>.flt.json`
- `Providers/<name>.comb.json`

Generated JSON Schemas are committed next to the source families:

- `Providers/provider.lay.schema.json`
- `Providers/combined-provider.comb.schema.json`
- `Extents/extent.ext.schema.json`
- `Filters/color-filter.flt.schema.json`
- `zone-list.schema.json`

Runtime loaders read these JSON files for bundled source data. User
configuration files remain in the existing `.cfg` key/value format for
compatibility, with Pydantic handling value coercion and validation.
