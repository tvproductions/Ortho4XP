# Provider Definitions

Provider files currently use Ortho4XP's legacy `.lay` format: one
`key=value` pair per line, with `#` comments. The loader validates this format
with a schema before a provider is added to the runtime dictionary.

This keeps the existing source data usable while removing ad hoc parsing. A
future TODO tracks migrating provider files to JSON and evaluating Pydantic for
typed validation, generated JSON Schema, and clearer diagnostics.

Schema-backed fields:

- `request_type`: `wms`, `wmts`, `tms`, or `local_tms`
- `grid_type`: `webmercator`
- `url_template`, `url_prefix`, `layers`, `image_type`, `tilematrixset`, `extent`
- `epsg_code`, `wms_version`, `wmts_version`, `wms_size`, `tile_size`
- `top_left_corner`, `scaledenominator`, `resolutions`
- `fake_headers`, `in_GUI`, `max_threads`, `max_zl`
- `color_filters`; legacy `color_filter` is accepted as an alias
- `imagery_dir`: `grouped`, `normal`, or `code`

Invalid fields or values include the provider code, field name, and source file
in the validation error so provider fixes can be made directly.
