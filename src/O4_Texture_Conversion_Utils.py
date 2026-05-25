import os
import time

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Texture_Encoder as TEX
import O4_UI_Utils as UI
from O4_Subprocess_Utils import run_external_command


# Conversion helpers own external encoder/GDAL cleanup once imagery has prepared
# the source raster. Keeping this boundary outside O4_Imagery_Utils limits future
# CUDA/Vulkan backend work to texture modules instead of the legacy imagery file.
def texture_encode_request(tile, texture_attrs, conversion_input):
    til_x_left, til_y_top, zoomlevel, provider_code = texture_attrs
    source_path, output_file_name, dxt5 = conversion_input
    return TEX.TextureEncodeRequest(
        source_path=source_path,
        output_path=os.path.join(tile.build_dir, "textures", output_file_name),
        codec="bc3" if dxt5 else "bc1",
        display_name=output_file_name,
        provider_code=provider_code,
        til_x_left=til_x_left,
        til_y_top=til_y_top,
        zoomlevel=zoomlevel,
    )


def cleanup_conversion_temps(erase_tmp_png, png_file_name, tmp_tif_file_name=None):
    if erase_tmp_png:
        _remove_conversion_temp(
            os.path.join(FNAMES.resource_path("tmp"), png_file_name)
        )
    if tmp_tif_file_name:
        _remove_conversion_temp(tmp_tif_file_name)


def convert_dds_texture(tile, texture_attrs, conversion_input, cleanup_input):
    request = texture_encode_request(tile, texture_attrs, conversion_input)
    try:
        encode_result = TEX.encode_texture(request)
        return TEX.TextureConversionResult.from_encode_result(encode_result)
    finally:
        cleanup_conversion_temps(*cleanup_input)


def convert_geotiff_texture(tile, texture_attrs, conversion_input, gdal_commands):
    provider_code = texture_attrs[3]
    out_file_name = conversion_input[1]
    command_result = _geotiff_conversion_command(
        tile,
        texture_attrs,
        conversion_input,
        gdal_commands,
    )
    if isinstance(command_result, TEX.TextureConversionResult):
        return command_result
    conv_cmd, tmp_tif_to_cleanup = command_result
    result = _run_geotiff_conversion(tile, conv_cmd, out_file_name)
    cleanup_conversion_temps(
        conversion_input[2],
        conversion_input[3],
        tmp_tif_to_cleanup,
    )
    if result.ok:
        return TEX.TextureConversionResult.success(out_file_name, provider_code)
    return TEX.TextureConversionResult.failure(
        out_file_name,
        provider_code,
        _geotiff_error_summary(result),
    )


def _geotiff_conversion_command(tile, texture_attrs, conversion_input, gdal_commands):
    file_to_convert, out_file_name, erase_tmp_png, png_file_name, tmp_tif = (
        conversion_input
    )
    bounds = _geotiff_bounds(texture_attrs)
    gdal_transl_cmd, gdalwarp_cmd = gdal_commands
    if bounds[0] - bounds[2] < 0.04:
        return (
            _gdal_translate_command(
                gdal_transl_cmd, bounds, file_to_convert, out_file_name
            ),
            None,
        )
    geotag_cmd = _gdal_geotag_command(
        gdal_transl_cmd,
        bounds,
        file_to_convert,
        tmp_tif,
    )
    geotag_result = run_external_command(geotag_cmd)
    if not geotag_result.ok:
        cleanup_conversion_temps(erase_tmp_png, png_file_name, tmp_tif)
        return _geotag_failure_result(tile, texture_attrs[3], out_file_name)
    return _gdalwarp_command(gdalwarp_cmd, tmp_tif, out_file_name), tmp_tif


def _geotiff_bounds(texture_attrs):
    til_x_left, til_y_top, zoomlevel, _provider_code = texture_attrs
    (latmax, lonmin) = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    (latmin, lonmax) = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
    (xmin, ymin) = GEO.geo_to_webm(lonmin, latmin)
    (xmax, ymax) = GEO.geo_to_webm(lonmax, latmax)
    return latmax, lonmin, latmin, lonmax, xmin, ymin, xmax, ymax


def _gdal_translate_command(gdal_transl_cmd, bounds, file_to_convert, out_file_name):
    latmax, lonmin, latmin, lonmax, _xmin, _ymin, _xmax, _ymax = bounds
    return [
        gdal_transl_cmd,
        "-of",
        "Gtiff",
        "-co",
        "COMPRESS=JPEG",
        "-a_ullr",
        str(lonmin),
        str(latmax),
        str(lonmax),
        str(latmin),
        "-a_srs",
        "epsg:4326",
        file_to_convert,
        os.path.join(FNAMES.Geotiff_dir, out_file_name),
    ]


def _gdal_geotag_command(gdal_transl_cmd, bounds, file_to_convert, tmp_tif):
    _latmax, _lonmin, _latmin, _lonmax, xmin, ymin, xmax, ymax = bounds
    return [
        gdal_transl_cmd,
        "-of",
        "Gtiff",
        "-co",
        "COMPRESS=JPEG",
        "-a_ullr",
        str(xmin),
        str(ymax),
        str(xmax),
        str(ymin),
        "-a_srs",
        "epsg:3857",
        file_to_convert,
        tmp_tif,
    ]


def _gdalwarp_command(gdalwarp_cmd, tmp_tif, out_file_name):
    return [
        gdalwarp_cmd,
        "-of",
        "Gtiff",
        "-co",
        "COMPRESS=JPEG",
        "-s_srs",
        "epsg:3857",
        "-t_srs",
        "epsg:4326",
        "-ts",
        "4096",
        "4096",
        "-rb",
        tmp_tif,
        os.path.join(FNAMES.Geotiff_dir, out_file_name),
    ]


def _geotag_failure_result(tile, provider_code, out_file_name):
    UI.vprint(
        1,
        "ERROR: Could not geotag texture (gdal not present ?) ",
        os.path.join(tile.build_dir, "textures", out_file_name),
    )
    return TEX.TextureConversionResult.failure(
        out_file_name,
        provider_code,
        "Could not geotag texture",
    )


def _run_geotiff_conversion(tile, conv_cmd, out_file_name):
    for tentative in range(1, 11):
        result = run_external_command(conv_cmd)
        if result.ok:
            return result
        if tentative == 10:
            UI.lvprint(
                1,
                "ERROR: Could not convert texture",
                os.path.join(tile.build_dir, "textures", out_file_name),
                "(10 tries)",
            )
            return result
        UI.lvprint(
            1,
            "WARNING: Could not convert texture",
            os.path.join(tile.build_dir, "textures", out_file_name),
        )
        time.sleep(1)
    return result


def _geotiff_error_summary(result):
    error_summary = getattr(result, "error_summary", "")
    if error_summary:
        return f"Could not convert texture: {error_summary}"
    return "Could not convert texture"


def _remove_conversion_temp(path):
    try:
        os.remove(path)
    except OSError as exc:
        UI.vprint(3, exc)
