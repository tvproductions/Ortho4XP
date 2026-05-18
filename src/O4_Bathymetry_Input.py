"""Public bathymetry input API for TODO-014 XP12 Global Scenery rasters.

Implementation is split across focused modules:

* ``O4_Bathymetry_Models`` holds error and payload dataclasses.
* ``O4_Bathymetry_Source`` resolves and reads XP12 Global Scenery DSFs.
* ``O4_Bathymetry_DSF_Bytes`` extracts raw DEMN/DEMS atoms from DSF bytes.
* ``O4_Bathymetry_Raster_Parser`` validates raster names, metadata, and data.

Keep this facade stable for callers in ``O4_DSF_Utils`` and tests.
"""

from O4_Bathymetry_DSF_Bytes import extract_validated_rasters_from_dsf_bytes
from O4_Bathymetry_Models import (
    BathymetryErrorContext,
    BathymetryInputError,
    GlobalSceneryRasterSource,
    RasterInfo,
    RasterPayload,
    ValidatedRasterBytes,
)
from O4_Bathymetry_Raster_Parser import validate_raster_payload
from O4_Bathymetry_Source import (
    extract_validated_global_scenery_rasters as _extract_validated_global_scenery_rasters,
)


def extract_validated_global_scenery_rasters(
    lat,
    lon,
    *,
    primary_overlay_src,
    alternate_overlay_src,
    tmp_dir,
    unzip_executable,
    run_external_tool,
):
    source = GlobalSceneryRasterSource(
        lat,
        lon,
        primary_overlay_src,
        alternate_overlay_src,
        tmp_dir,
        unzip_executable,
        run_external_tool,
    )
    return _extract_validated_global_scenery_rasters(source)


__all__ = [
    "BathymetryErrorContext",
    "BathymetryInputError",
    "GlobalSceneryRasterSource",
    "RasterInfo",
    "RasterPayload",
    "ValidatedRasterBytes",
    "extract_validated_global_scenery_rasters",
    "extract_validated_rasters_from_dsf_bytes",
    "validate_raster_payload",
]
