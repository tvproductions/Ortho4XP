"""GeoTIFF creation policy helpers."""

import O4_Resampling_Policy as RP

GEOTIFF_CREATION_OPTIONS = ("COMPRESS=JPEG",)
COG_GEOTIFF_CREATION_OPTIONS = GEOTIFF_CREATION_OPTIONS + (
    "TILED=YES",
    "BLOCKXSIZE=512",
    "BLOCKYSIZE=512",
)
COG_OVERVIEW_RESAMPLING = "AVERAGE"
COG_OVERVIEW_LEVELS = [2, 4, 8, 16]


def final_creation_options(tile):
    if getattr(tile, "cog_export", False):
        return list(COG_GEOTIFF_CREATION_OPTIONS)
    return list(GEOTIFF_CREATION_OPTIONS)


def temporary_creation_options():
    return list(GEOTIFF_CREATION_OPTIONS)


def geotag(gdal_module, request):
    output_path, source_path, output_bounds, output_srs = request
    gdal_module.Translate(
        output_path,
        source_path,
        format="GTiff",
        creationOptions=temporary_creation_options(),
        outputBounds=output_bounds,
        outputSRS=output_srs,
    )


def translate(gdal_module, request):
    output_path, source_path, output_bounds, output_srs, tile = request
    gdal_module.Translate(
        output_path,
        source_path,
        format="GTiff",
        creationOptions=final_creation_options(tile),
        outputBounds=output_bounds,
        outputSRS=output_srs,
    )
    build_overviews_if_enabled(gdal_module, output_path, tile)


def warp(gdal_module, request):
    output_path, source_path, tile = request
    gdal_module.Warp(
        output_path,
        source_path,
        format="GTiff",
        creationOptions=final_creation_options(tile),
        srcSRS="EPSG:3857",
        dstSRS="EPSG:4326",
        width=4096,
        height=4096,
        resampleAlg=RP.tile_gdal_resampling(tile, "warp_resampling"),
    )
    build_overviews_if_enabled(gdal_module, output_path, tile)


def build_overviews_if_enabled(gdal_module, output_path, tile):
    if not getattr(tile, "cog_export", False):
        return
    dataset = gdal_module.Open(output_path, gdal_module.GA_Update)
    if dataset is None:
        raise RuntimeError("could not open GeoTIFF for overview generation")
    dataset.BuildOverviews(COG_OVERVIEW_RESAMPLING, COG_OVERVIEW_LEVELS)
