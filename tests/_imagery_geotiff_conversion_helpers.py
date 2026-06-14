from unittest import mock

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Texture_Conversion_Utils as TCU


def convert_geotiff_with_failed_final_conversion(testcase):
    testcase._write_cached_jpeg("TIFFAIL")
    tile = testcase._tile_for_conversion()
    expected_name = FNAMES.geotiff_file_name_from_attributes(32, 48, 16, "TIFFAIL")

    with (
        testcase._convert_texture_patches("TIFFAIL") as conversion,
        mock.patch.object(
            TCU.GEO,
            "gtile_to_wgs84",
            side_effect=[(1.0, 2.0), (0.99, 2.01)],
        ),
        mock.patch.object(TCU.GEO, "geo_to_webm", return_value=(0, 0)),
        mock.patch.object(IMG.UI, "lvprint"),
        mock.patch.object(TCU.time, "sleep"),
    ):
        conversion.gdal.Translate.side_effect = Exception("gdal translate failed")
        result = IMG.convert_texture(tile, 32, 48, 16, "TIFFAIL", type="tif")

    return result, conversion, expected_name


def convert_geotiff_with_failed_geotag(testcase):
    testcase._write_cached_jpeg("GEOTAGFAIL")
    tile = testcase._tile_for_conversion()
    expected_name = FNAMES.geotiff_file_name_from_attributes(32, 48, 16, "GEOTAGFAIL")

    with (
        testcase._convert_texture_patches(
            "GEOTAGFAIL", color_filters="FILTER"
        ) as conversion,
        mock.patch.object(
            TCU.GEO,
            "gtile_to_wgs84",
            side_effect=[(1.0, 2.0), (0.0, 3.0)],
        ),
        mock.patch.object(
            TCU.GEO,
            "geo_to_webm",
            side_effect=[(20, 0), (30, 10)],
        ),
        mock.patch.object(IMG.os, "remove") as remove,
    ):
        conversion.color_transform.side_effect = lambda image, _: image
        conversion.gdal.Translate.side_effect = Exception("gdal geotag failed")
        result = IMG.convert_texture(tile, 32, 48, 16, "GEOTAGFAIL", type="tif")

    return result, remove, conversion.tmp_dir, expected_name
