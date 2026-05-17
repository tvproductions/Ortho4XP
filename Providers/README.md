# Provider Definitions

Provider files use JSON and are validated with Pydantic before a provider is
added to the runtime dictionary. Files live under `Providers/<region>/` and use
the provenance-preserving `<provider>.lay.json` filename convention. The
provider code comes from the filename before `.lay.json`.

The generated JSON Schema is committed at `Providers/provider.lay.schema.json`.

Schema-backed fields:

- `request_type`: `wms`, `wmts`, `tms`, or `local_tms`
- `grid_type`: `webmercator`
- `url_template`, `url_prefix`, `layers`, `image_type`, `tilematrixset`, `extent`
- `epsg_code`, `wms_version`, `wmts_version`, `wms_size`, `tile_size`
- `top_left_corner`, `scaledenominator`, `resolutions`
- `fake_headers`, `in_GUI`, `max_threads`, `max_zl`
- `color_filters`
- `imagery_dir`: `grouped`, `normal`, or `code`

JSON values should use native types. Booleans are `true` or `false`, numeric
fields are numbers, numeric sequences are arrays, and `fake_headers` is an
object whose keys and values are strings.

Runtime defaults are applied by the loader when omitted: `in_GUI=true`,
`image_type="jpeg"`, `extent="global"`, `color_filters="none"`, and
`imagery_dir="grouped"`.

Invalid fields or values include the provider code, field name, and source file
in the validation error so provider fixes can be made directly.

Combined providers at `Providers/<name>.comb.json` are also JSON and validated
with `Providers/combined-provider.comb.schema.json`.
