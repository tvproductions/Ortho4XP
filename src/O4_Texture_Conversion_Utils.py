import os
import time

from osgeo import gdal

import O4_DDS_Quality as DQA
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Geotiff_Options as GTO
import O4_Texture_Encoder as TEX
import O4_UI_Utils as UI

gdal.UseExceptions()


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
        # Optional QA observes successful DDS output without changing conversion status.
        DQA.run_enabled_dds_quality_check(tile, encode_result)
        return TEX.TextureConversionResult.from_encode_result(encode_result)
    finally:
        cleanup_conversion_temps(*cleanup_input)


def convert_geotiff_texture(tile, texture_attrs, conversion_input):
    provider_code = texture_attrs[3]
    out_file_name = conversion_input[1]
    file_to_convert, _, erase_tmp_png, png_file_name, tmp_tif = conversion_input
    bounds = _geotiff_bounds(texture_attrs)
    output_path = os.path.join(FNAMES.Geotiff_dir, out_file_name)
    tmp_tif_to_cleanup = None
    try:
        if bounds[0] - bounds[2] < 0.04:
            _run_translate_with_retry(
                output_path,
                file_to_convert,
                output_bounds=[bounds[1], bounds[2], bounds[3], bounds[0]],
                output_srs="EPSG:4326",
                tile=tile,
                out_file_name=out_file_name,
            )
        else:
            _run_geotag(bounds, file_to_convert, tmp_tif)
            tmp_tif_to_cleanup = tmp_tif
            _run_warp_with_retry(
                output_path,
                tmp_tif,
                tile=tile,
                out_file_name=out_file_name,
            )
    except _GeotagFailure:
        cleanup_conversion_temps(erase_tmp_png, png_file_name, tmp_tif)
        return _geotag_failure_result(tile, provider_code, out_file_name)
    except _GeotiffFailure as exc:
        cleanup_conversion_temps(erase_tmp_png, png_file_name, tmp_tif_to_cleanup)
        return TEX.TextureConversionResult.failure(
            out_file_name, provider_code, str(exc)
        )
    cleanup_conversion_temps(erase_tmp_png, png_file_name, tmp_tif_to_cleanup)
    return TEX.TextureConversionResult.success(out_file_name, provider_code)


def _geotiff_bounds(texture_attrs):
    til_x_left, til_y_top, zoomlevel, _provider_code = texture_attrs
    (latmax, lonmin) = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    (latmin, lonmax) = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
    (xmin, ymin) = GEO.geo_to_webm(lonmin, latmin)
    (xmax, ymax) = GEO.geo_to_webm(lonmax, latmax)
    return latmax, lonmin, latmin, lonmax, xmin, ymin, xmax, ymax


class _GeotagFailure(Exception):
    pass


class _GeotiffFailure(Exception):
    pass


def _run_geotag(bounds, file_to_convert, tmp_tif):
    _latmax, _lonmin, _latmin, _lonmax, xmin, ymin, xmax, ymax = bounds
    try:
        GTO.geotag(
            gdal, (tmp_tif, file_to_convert, [xmin, ymin, xmax, ymax], "EPSG:3857")
        )
    except Exception:
        raise _GeotagFailure("Could not geotag texture") from None


def _run_translate_with_retry(
    output_path,
    file_to_convert,
    *,
    output_bounds,
    output_srs,
    tile,
    out_file_name,
):
    for tentative in range(1, 11):
        try:
            request = (output_path, file_to_convert, output_bounds, output_srs, tile)
            GTO.translate(gdal, request)
            return
        except Exception:
            if tentative == 10:
                UI.lvprint(
                    1,
                    "ERROR: Could not convert texture",
                    os.path.join(tile.build_dir, "textures", out_file_name),
                    "(10 tries)",
                )
                raise _GeotiffFailure("Could not convert texture") from None
            UI.lvprint(
                1,
                "WARNING: Could not convert texture",
                os.path.join(tile.build_dir, "textures", out_file_name),
            )
            time.sleep(1)


def _run_warp_with_retry(output_path, tmp_tif, *, tile, out_file_name):
    for tentative in range(1, 11):
        try:
            GTO.warp(gdal, (output_path, tmp_tif, tile))
            return
        except Exception:
            if tentative == 10:
                UI.lvprint(
                    1,
                    "ERROR: Could not convert texture",
                    os.path.join(tile.build_dir, "textures", out_file_name),
                    "(10 tries)",
                )
                raise _GeotiffFailure("Could not convert texture") from None
            UI.lvprint(
                1,
                "WARNING: Could not convert texture",
                os.path.join(tile.build_dir, "textures", out_file_name),
            )
            time.sleep(1)


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


def _remove_conversion_temp(path):
    try:
        os.remove(path)
    except OSError as exc:
        UI.vprint(3, exc)
