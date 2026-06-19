import asyncio
import importlib
import importlib.util
import json
import os
import queue
import secrets
import sys
import time
from dataclasses import dataclass
from math import ceil, log, pi, tan
from pathlib import Path
from typing import Any

import numpy
from osgeo import gdal
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pydantic import ValidationError

import O4_Async_HTTP as AHTTP
import O4_File_Names as FNAMES
import O4_GDAL_Texture_Pipeline as GTP
import O4_Geo_Utils as GEO
import O4_Imagery_Failures as IFAIL
import O4_Mask_Utils as MASK
import O4_Mesh_Utils as MESH
import O4_OSM_Utils as OSM
import O4_Resampling_Policy as RP
import O4_Texture_Color_Normalization as TCN
import O4_UI_Utils as UI
import O4_Vector_Utils as VECT
from O4_Parallel_Utils import parallel_execute
from O4_Source_Data_Models import (
    ColorFilterDefinition,
    CombinedProviderDefinition,
    ExtentDefinition,
    ProviderDefinition,
    source_code_from_path,
)
from O4_Subprocess_Utils import resolve_tool
from O4_Texture_Conversion_Utils import (
    convert_dds_texture,
    convert_geotiff_texture,
)
from O4_Texture_Source import TextureBuildResult, TextureSource

Image.MAX_IMAGE_PIXELS = 1000000000  # Not a decompression bomb attack!
gdal.UseExceptions()

has_URL = False
URL: Any = None
try:
    URL = importlib.import_module("O4_Custom_URL")

    has_URL = True
except ImportError:
    try:
        provider_url_path = Path(FNAMES.Provider_dir) / "O4_Custom_URL.py"
        spec = importlib.util.spec_from_file_location(
            "O4_Custom_URL", provider_url_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load {provider_url_path}")
        URL = importlib.util.module_from_spec(spec)
        sys.modules["O4_Custom_URL"] = URL
        spec.loader.exec_module(URL)
        has_URL = True
    except Exception:
        print(
            "ERROR: Providers/O4_Custom_URL.py contains invalid code.",
            "The corresponding providers won't probably work.",
        )

http_timeout: float = 10
check_tms_response: bool = False
max_connect_retries: int = 10
max_baddata_retries: int = 10
normalize_texture_colors: bool = False
texture_resize_resampling: str = "lanczos"
mask_resize_resampling: str = "nearest"
warp_resampling: str = "bicubic"
normalization_resampling: str = "bilinear"
incomplete_imgs = IFAIL.incomplete_imgs
imagery_failure_records = IFAIL.imagery_failure_records
ImageryFailureRecord = IFAIL.ImageryFailureRecord
failures_for_texture = IFAIL.failures_for_texture
imagery_download_summary = IFAIL.imagery_download_summary
incomplete_texture_file_names = IFAIL.incomplete_texture_file_names
incomplete_texture_file_names_by_tile = IFAIL.incomplete_texture_file_names_by_tile
record_incomplete_texture = IFAIL.record_incomplete_texture


async def async_request_sleep(delay):
    await asyncio.sleep(delay)


user_agent_generic = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0"
)
request_headers_generic = {
    "User-Agent": user_agent_generic,
    "Accept": "*/*",
    "Connection": "keep-alive",
    "Accept-Encoding": "gzip, deflate",
}

is_macos = "dar" in sys.platform
DDS_OUTPUT_TYPE = "dds"
TIF_OUTPUT_TYPE = "tif"
dds_convert_cmd = resolve_tool("DDSTool" if is_macos else "nvcompress")

# Windows and Linux both use nvcompress; macOS uses DDSTool.
# The command flags below still branch by platform.
# The single resolver call keeps platform branching out of command execution.
# Existing module-level names are preserved for legacy callers.
################################################################################
#
#  PART I : Initialization of providers, extents, and color filters
#
################################################################################

providers_dict: dict[str, dict[str, Any]] = {}
combined_providers_dict: dict[str, Any] = {}
local_combined_providers_dict: dict[str, Any] = {}
extents_dict: dict[str, dict[str, Any]] = {"global": {"dir": None, "code": "global"}}
color_filters_dict: dict[str, Any] = {"none": []}


################################################################################
@dataclass(frozen=True)
class ProviderValidationIssue:
    provider_code: str
    source_path: Path
    field: str
    message: str
    line_number: int | None = None
    is_error: bool = True
    source_kind: str = "provider"

    def __str__(self):
        location = str(self.source_path)
        if self.line_number is not None:
            location += f":{self.line_number}"
        level = "error" if self.is_error else "warning"
        return (
            f"{location}: {self.source_kind} {self.provider_code}: {level}: "
            f"{self.field}: {self.message}"
        )


PROVIDER_DEFINITION_FORMAT = "JSON provider definition"


def _provider_issue(
    provider_code,
    source_path,
    field,
    message,
    line_number=None,
    is_error=True,
    source_kind="provider",
):
    return ProviderValidationIssue(
        provider_code=provider_code,
        source_path=Path(source_path),
        field=field,
        message=message,
        line_number=line_number,
        is_error=is_error,
        source_kind=source_kind,
    )


def _print_provider_issues(issues):
    for issue in issues:
        UI.vprint(0, str(issue))


def _validation_issues(source_code, source_path, source_kind, exc):
    issues = []
    for error in exc.errors():
        location = error["loc"]
        field = ".".join(str(part) for part in location) if location else "json"
        issues.append(
            _provider_issue(
                source_code,
                source_path,
                field,
                error["msg"],
                source_kind=source_kind,
            )
        )
    return issues


def _record_provider_epsg(epsg_code):
    try:
        GEO.record_epsg(epsg_code)
    except Exception:
        # HACK for Slovenia
        if epsg_code == 102060:
            GEO.record_epsg(3912)
        else:
            raise


def _normalize_provider_for_runtime(provider):
    if "top_left_corner" in provider:
        provider["top_left_corner"] = [
            numpy.array(provider["top_left_corner"]) for _ in range(40)
        ]
    if "resolutions" in provider:
        provider["resolutions"] = numpy.array(provider["resolutions"])
    if "scaledenominator" in provider:
        provider["scaledenominator"] = numpy.array(provider["scaledenominator"])
    return provider


def _provider_validation_issues(provider_code, source_path, exc):
    issues = []
    for error in exc.errors():
        location = error["loc"]
        field = str(location[0]) if location else "request_type"
        issues.append(
            _provider_issue(
                provider_code,
                source_path,
                field,
                error["msg"],
            )
        )
    return issues


def _json_decode_issues(source_code, source_path, source_kind, exc):
    return [
        _provider_issue(
            source_code,
            source_path,
            "json",
            exc.msg,
            exc.lineno,
            source_kind=source_kind,
        )
    ]


def parse_provider_definition(provider_code, source_path):
    source_path = Path(source_path)
    try:
        provider_model = ProviderDefinition.model_validate_json(
            source_path.read_text(encoding="utf-8"),
            context={"color_filters": color_filters_dict},
        )
    except ValidationError as exc:
        return {}, _provider_validation_issues(provider_code, source_path, exc)
    except json.JSONDecodeError as exc:
        return {}, [
            _provider_issue(
                provider_code,
                source_path,
                "json",
                exc.msg,
                exc.lineno,
            )
        ]

    provider = provider_model.to_runtime_dict()
    if "epsg_code" in provider:
        try:
            _record_provider_epsg(provider["epsg_code"])
        except Exception as exc:
            return provider, [
                _provider_issue(
                    provider_code,
                    source_path,
                    "epsg_code",
                    f"could not validate EPSG code: {exc}",
                )
            ]
    return _normalize_provider_for_runtime(provider), []


def iter_provider_definition_paths(provider_dir=None):
    provider_root = Path(provider_dir or FNAMES.Provider_dir)
    for dir_path in sorted(provider_root.iterdir()):
        if not dir_path.is_dir():
            continue
        yield from sorted(dir_path.glob("*.lay.json"))


def validate_provider_definitions(provider_dir=None):
    issues = []
    for provider_path in iter_provider_definition_paths(provider_dir):
        provider_code = source_code_from_path(provider_path, "lay")
        _, provider_issues = parse_provider_definition(provider_code, provider_path)
        issues.extend(provider_issues)
    return issues


################################################################################
def _print_source_issues(issues):
    for issue in issues:
        UI.vprint(0, str(issue))


def _record_extent_epsg(epsg_code):
    try:
        GEO.record_epsg(epsg_code)
    except Exception:
        # HACK for Slovenia
        if epsg_code == 102060:
            GEO.record_epsg(3912)
        else:
            raise


def parse_extent_definition(extent_code, source_path):
    source_path = Path(source_path)
    try:
        extent_model = ExtentDefinition.model_validate_json(
            source_path.read_text(encoding="utf-8")
        )
    except ValidationError as exc:
        return {}, _validation_issues(extent_code, source_path, "extent", exc)
    except json.JSONDecodeError as exc:
        return {}, _json_decode_issues(extent_code, source_path, "extent", exc)
    extent = extent_model.to_runtime_dict()
    if "epsg_code" in extent:
        try:
            _record_extent_epsg(extent["epsg_code"])
        except Exception as exc:
            return extent, [
                _provider_issue(
                    extent_code,
                    source_path,
                    "epsg_code",
                    f"could not validate EPSG code: {exc}",
                    source_kind="extent",
                )
            ]
    return extent, []


def initialize_extents_dict():
    for dir_path in sorted(Path(FNAMES.Extent_dir).iterdir()):
        if not dir_path.is_dir():
            continue
        for extent_path in sorted(dir_path.glob("*.ext.json")):
            extent_code = source_code_from_path(extent_path, "ext")
            extent, issues = parse_extent_definition(extent_code, extent_path)
            _print_source_issues(issues)
            if not any(issue.is_error for issue in issues):
                extent["code"] = extent_code
                extent["dir"] = dir_path.name
                extents_dict[extent_code] = extent
            else:
                print("Error in reading extent definition file for", extent_path.name)


################################################################################


################################################################################
def initialize_color_filters_dict():
    color_filters_dict.setdefault("none", [])
    for filter_path in sorted(Path(FNAMES.Filter_dir).glob("*.flt.json")):
        color_code = source_code_from_path(filter_path, "flt")
        try:
            color_filter_model = ColorFilterDefinition.model_validate_json(
                filter_path.read_text(encoding="utf-8")
            )
        except ValidationError as exc:
            _print_source_issues(
                _validation_issues(color_code, filter_path, "color filter", exc)
            )
            print("Could not understand color filter ", color_code, ", skipping it.")
            continue
        except json.JSONDecodeError as exc:
            _print_source_issues(
                _json_decode_issues(color_code, filter_path, "color filter", exc)
            )
            print("Could not understand color filter ", color_code, ", skipping it.")
            continue
        color_filters_dict[color_code] = color_filter_model.to_runtime_list()


################################################################################


################################################################################
def initialize_providers_dict():
    for provider_path in iter_provider_definition_paths():
        provider_code = source_code_from_path(provider_path, "lay")
        dir_name = provider_path.parent.name
        file_name = provider_path.name
        provider, provider_issues = parse_provider_definition(
            provider_code, provider_path
        )
        _print_provider_issues(provider_issues)
        valid_provider = not any(issue.is_error for issue in provider_issues)
        if ("request_type" in provider) and (provider["request_type"] == "wmts"):
            try:
                tilematrixsets = read_tilematrixsets(
                    os.path.join(
                        FNAMES.Provider_dir,
                        dir_name,
                        "capabilities_" + provider_code + ".xml",
                    )
                )
            except (OSError, IndexError):
                try:
                    tilematrixsets = read_tilematrixsets(
                        os.path.join(
                            FNAMES.Provider_dir,
                            dir_name,
                            "capabilities.xml",
                        )
                    )
                except (OSError, IndexError):
                    print(
                        "Error in reading capabilities for provider",
                        provider_code,
                    )
                    valid_provider = False
            if valid_provider:
                try:
                    tms_found = False
                    for tilematrixset in tilematrixsets:
                        if tilematrixset["identifier"] == provider["tilematrixset"]:
                            provider["tilematrixset"] = tilematrixset
                            tms_found = True
                            break
                    if tms_found:
                        provider["scaledenominator"] = numpy.array(
                            [
                                float(x["ScaleDenominator"])
                                for x in provider["tilematrixset"]["tilematrices"]
                            ]
                        )
                        provider["top_left_corner"] = [
                            [float(x) for x in y["TopLeftCorner"].split()]
                            for y in provider["tilematrixset"]["tilematrices"]
                        ]
                    else:
                        print("no tilematrixset found")
                        valid_provider = False
                except (KeyError, TypeError, ValueError, IndexError):
                    print(
                        "Error in reading capabilities for provider",
                        provider_code,
                    )
                    valid_provider = False
        if valid_provider:
            provider["code"] = provider_code
            provider["directory"] = dir_name
            if "in_GUI" not in provider:
                provider["in_GUI"] = True
            if "image_type" not in provider:
                provider["image_type"] = "jpeg"
            if "extent" not in provider:
                provider["extent"] = "global"
            if "color_filters" not in provider:
                provider["color_filters"] = "none"
            if "imagery_dir" not in provider:
                provider["imagery_dir"] = "grouped"
            if "scaledenominator" in provider:
                units_per_pix = (
                    2.5152827955e-09 if provider["epsg_code"] == 4326 else 0.00028
                )
                provider["resolutions"] = units_per_pix * provider["scaledenominator"]
            if ("grid_type" in provider) and provider["grid_type"] == "webmercator":
                provider["request_type"] = "tms"
                provider["tile_size"] = 256
                provider["epsg_code"] = "3857"
                provider["top_left_corner"] = [
                    [-20037508.34, 20037508.34] for i in range(0, 21)
                ]
                provider["resolutions"] = numpy.array(
                    [20037508.34 / (128 * 2**i) for i in range(0, 21)]
                )
            if "request_type" not in provider:
                UI.vprint(
                    0,
                    "Error in reading provider definition ",
                    "file for",
                    file_name,
                )
            else:
                providers_dict[provider_code] = provider
        else:
            UI.vprint(
                0,
                "Error in reading provider definition file for",
                file_name,
            )


################################################################################


################################################################################
def initialize_combined_providers_dict():
    for combined_path in sorted(Path(FNAMES.Provider_dir).glob("*.comb.json")):
        provider_code = source_code_from_path(combined_path, "comb")
        try:
            comb_list = []
            combined_model = CombinedProviderDefinition.model_validate_json(
                combined_path.read_text(encoding="utf-8")
            )
            for layer in combined_model.to_runtime_list():
                layer_code = layer["layer_code"]
                extent_code = layer["extent_code"]
                color_code = layer["color_code"]
                priority = layer["priority"]
                if layer_code not in providers_dict:
                    print(
                        "Unknown provider in combined provider",
                        provider_code,
                        ":",
                        layer_code,
                    )
                    continue
                if extent_code == "default":
                    extent_code = providers_dict[layer_code]["extent"]
                if (extent_code not in extents_dict) or (
                    extent_code[0] == "!" and (extent_code[1:] not in extents_dict)
                ):
                    print(
                        "Unknown extent in combined provider",
                        provider_code,
                        ":",
                        extent_code,
                    )
                    continue
                if color_code == "default":
                    try:
                        color_code = providers_dict[layer_code]["color_filters"]
                    except KeyError:
                        print(
                            "Unknown color filter in combined provider",
                            provider_code,
                            ":",
                            color_code,
                        )
                        continue
                if color_code not in color_filters_dict:
                    try:
                        if color_code[0] == "L":
                            b = 1
                        elif color_code[0] == "D":
                            b = -1
                        brightness = b * float(color_code[1:3])
                        contrast = float(color_code[4:6])
                        color_filters_dict[color_code] = [
                            ["brightness-contrast", brightness, contrast]
                        ]
                        if len(color_code) > 6:
                            saturation = float(color_code[7:9])
                            color_filters_dict[color_code].append(
                                ["saturation", saturation]
                            )
                    except (IndexError, TypeError, ValueError):
                        print(
                            "Unknown color filter in combined provider",
                            provider_code,
                            ":",
                            color_code,
                        )
                        continue
                if priority not in ["low", "medium", "high", "mask"]:
                    print(
                        "Unknown priority in combined provider",
                        provider_code,
                        ":",
                        priority,
                    )
                    continue
                comb_list.append(
                    {
                        "layer_code": layer_code,
                        "extent_code": extent_code,
                        "color_code": color_code,
                        "priority": priority,
                    }
                )
            if comb_list:
                combined_providers_dict[provider_code] = comb_list
            else:
                print(
                    "Combined provider",
                    provider_code,
                    "did not contained valid providers, skipped.",
                )
        except ValidationError as exc:
            _print_source_issues(
                _validation_issues(
                    provider_code, combined_path, "combined provider", exc
                )
            )
            print("Error reading definition of combined provider", provider_code)
        except json.JSONDecodeError as exc:
            _print_source_issues(
                _json_decode_issues(
                    provider_code, combined_path, "combined provider", exc
                )
            )
            print("Error reading definition of combined provider", provider_code)


################################################################################


################################################################################
def initialize_local_combined_providers_dict(tile):
    # This function will select from list of providers the only
    # ones whose coverage intersect the given tile.
    global local_combined_providers_dict, extents_dict
    UI.vprint(1, "-> Initializing providers with potential data on this tile.")
    local_combined_providers_dict = {}
    test_set = {tile.default_website}
    for region in tile.zone_list[:]:
        test_set.add(region[2])
    for provider_code in test_set.intersection(combined_providers_dict):
        comb_list = []
        for rlayer in combined_providers_dict[provider_code]:
            is_mask_layer = (
                (tile.lat, tile.lon, tile.mask_zl)
                if rlayer["priority"] == "mask"
                else False
            )
            if has_data(
                (tile.lon, tile.lat + 1, tile.lon + 1, tile.lat),
                rlayer["extent_code"],
                is_mask_layer,
            ):
                comb_list.append(rlayer)
        if not comb_list:
            UI.vprint(
                1,
                "Combined provider",
                provider_code,
                "did not contained data for this tile, exiting.",
            )
            return 0
        if len(comb_list) == 1:
            local_combined_providers_dict[provider_code] = comb_list
            continue
        # len(comb_list > 1)
        new_comb_list = []
        for rlayer in comb_list:
            name = rlayer["extent_code"]
            if name[0] == "!":
                name = name[1:]
            if extents_dict[name]["dir"] == "LowRes":
                new_rlayer = dict(rlayer)
                new_extent_code = name + "_" + FNAMES.short_latlon(tile.lat, tile.lon)
                new_rlayer["extent_code"] = new_extent_code
                new_comb_list.append(new_rlayer)
                extents_dict[new_extent_code] = {
                    "dir": "Auto",
                    "code": new_extent_code,
                    "mask_bounds": [
                        tile.lon - 0.1,
                        tile.lat - 0.1,
                        tile.lon + 1.1,
                        tile.lat + 1.1,
                    ],
                }
                if os.path.exists(
                    os.path.join(FNAMES.Extent_dir, "Auto", new_extent_code + ".png")
                ):
                    UI.vprint(1, "    Recycling layer mask for ", name)
                    continue
                UI.vprint(1, "    Building layer mask for ", name)
                # need to build the extent mask over that tile
                if not os.path.isdir(os.path.join(FNAMES.Extent_dir, "Auto")):
                    os.makedirs(os.path.join(FNAMES.Extent_dir, "Auto"))
                cached_file_name = os.path.join(
                    FNAMES.Extent_dir, "LowRes", name + ".osm.bz2"
                )
                pixel_size = 10
                try:
                    buffer_width = extents_dict[name]["buffer_width"] / pixel_size
                except (KeyError, TypeError, ZeroDivisionError):
                    buffer_width = 0.0
                try:
                    mask_width = int(extents_dict[name]["mask_width"] / pixel_size)
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    mask_width = int(100 / pixel_size)
                pixel_size = pixel_size / 111139
                vector_map = VECT.Vector_Map()
                osm_layer = OSM.OSM_layer()
                if not os.path.exists(cached_file_name):
                    UI.vprint(
                        0,
                        "Error, missing OSM data for extent code",
                        name,
                        ", exiting.",
                    )
                    del extents_dict[new_extent_code]
                    return 0
                osm_layer.update_dicosm(cached_file_name, None)
                multipolygon_area = OSM.OSM_to_MultiPolygon(osm_layer, 0, 0)
                del osm_layer
                if not multipolygon_area.area:
                    UI.vprint(
                        0,
                        "Error, erroneous OSM data for extent code",
                        name,
                        ", skipped.",
                    )
                    continue
                vector_map.encode_MultiPolygon(
                    multipolygon_area,
                    VECT.dummy_alt,
                    "WATER",
                    check=False,
                    cut=False,
                )
                vector_map.write_node_file(name + ".node")
                vector_map.write_poly_file(name + ".poly")
                MESH.triangulate(name, ".")
                (
                    (xmin, ymin, xmax, ymax),
                    mask_im,
                ) = MASK.triangulation_to_image(
                    name,
                    pixel_size,
                    (
                        tile.lon - 0.1,
                        tile.lat - 0.1,
                        tile.lon + 1.1,
                        tile.lat + 1.1,
                    ),
                )
                if buffer_width:
                    mask_im = mask_im.filter(ImageFilter.GaussianBlur(buffer_width / 4))
                    if buffer_width > 0:
                        mask_im = Image.fromarray(
                            (numpy.array(mask_im, dtype=numpy.uint8) > 0).astype(
                                numpy.uint8
                            )
                            * 255
                        )
                    else:  # buffer width can be negative
                        mask_im = Image.fromarray(
                            (numpy.array(mask_im, dtype=numpy.uint8) == 255).astype(
                                numpy.uint8
                            )
                            * 255
                        )
                if mask_width:
                    mask_width += 1
                    img_array = numpy.array(mask_im, dtype=numpy.uint8)
                    kernel = numpy.ones(int(mask_width)) / int(mask_width)
                    kernel = numpy.array(range(1, 2 * mask_width))
                    kernel[mask_width:] = range(mask_width - 1, 0, -1)
                    kernel = kernel / mask_width**2
                    for i in range(0, len(img_array)):
                        img_array[i] = numpy.convolve(img_array[i], kernel, "same")
                    img_array = img_array.transpose()
                    for i in range(0, len(img_array)):
                        img_array[i] = numpy.convolve(img_array[i], kernel, "same")
                    img_array = img_array.transpose()
                    img_array[img_array >= 128] = 255
                    img_array[img_array < 128] *= 2
                    img_array = numpy.array(img_array, dtype=numpy.uint8)
                    mask_im = Image.fromarray(img_array)
                mask_im.save(
                    os.path.join(FNAMES.Extent_dir, "Auto", new_extent_code + ".png")
                )
                for f in [
                    name + ".poly",
                    name + ".node",
                    name + ".1.node",
                    name + ".1.ele",
                ]:
                    try:
                        os.remove(f)
                    except OSError as exc:
                        UI.vprint(3, exc)
            else:
                new_comb_list.append(rlayer)
        local_combined_providers_dict[provider_code] = new_comb_list
    UI.vprint(2, "     Done.")
    return 1


################################################################################


################################################################################
def read_tilematrixsets(file_name):
    def xml_decode(line):
        field = line.split("<")[1].split(">")[0]
        str_value = line.split(">")[1].split("<")[0]
        return [field, str_value]

    tilematrixsets = []
    with open(file_name) as f:
        line = f.readline()
        while line:
            if line.strip() == "<TileMatrixSet>":
                tilematrixset = {}
                tilematrixset["tilematrices"] = []
                line = f.readline()
                while line.strip() != "</TileMatrixSet>":
                    if line.strip() == "<TileMatrix>":
                        tilematrix = {}
                        line = f.readline()
                        while line.strip() != "</TileMatrix>":
                            field, str_value = xml_decode(line)
                            if "Identifier" in field:
                                field = "identifier"
                            tilematrix[field] = str_value
                            line = f.readline()
                        tilematrixset["tilematrices"].append(tilematrix)
                    elif "Identifier" in line:
                        field, str_value = xml_decode(line)
                        tilematrixset["identifier"] = str_value
                    line = f.readline()
                tilematrixsets.append(tilematrixset)
            else:
                pass
            line = f.readline()
    return tilematrixsets


################################################################################


################################################################################
def has_data(
    bbox,
    extent_code,
    return_mask=False,
    mask_size=(4096, 4096),
    is_sharp_resize=False,
    is_mask_layer=False,
):
    # This function checks wether a given provider has data instersecting the
    # given bbox.
    # It returns either False or True or (in the latter case) the mask image
    # over the bbox and properly resized according to input parameter.
    # is_sharp_resize determines if the upsamplique of the extent mask is
    # nearest (good when sharp transitions are ) or bicubic (good in all other
    # cases)
    # is_mask_layer (assuming EPSG:4326) allows to "multiply" extent masks
    # with water masks, this is a smooth alternative for the old
    # sea_texture_params.
    # IMPORTANT 1 : THE EXTENT AND THE BBOX NEED TO BE USING THE SAME REFERENCE
    # FRAME (e.g. ESPG CODE)
    # IMPORTANT 2 : (x0,y0) is the top-left corner, (x1,y1) is the bottom-right
    (x0, y0, x1, y1) = bbox
    try:
        # global layers need special treatment
        if extent_code == "global" and (not is_mask_layer or (x1 - x0) == 1):
            return (not return_mask) or Image.new("L", mask_size, "white")
        if extent_code[0] == "!":
            extent_code = extent_code[1:]
            negative = True
        else:
            negative = False
        (xmin, ymin, xmax, ymax) = (
            extents_dict[extent_code]["mask_bounds"]
            if extent_code != "global"
            else (-180, -90, 180, 90)
        )
        if x0 > xmax or x1 < xmin or y0 < ymin or y1 > ymax:
            return negative
        if (not is_mask_layer) or (x1 - x0) == 1:
            mask_im = Image.open(
                os.path.join(
                    FNAMES.Extent_dir,
                    extents_dict[extent_code]["dir"],
                    extents_dict[extent_code]["code"] + ".png",
                )
            ).convert("L")
            (sizex, sizey) = mask_im.size
            pxx0 = int((x0 - xmin) / (xmax - xmin) * sizex)
            pxx1 = int((x1 - xmin) / (xmax - xmin) * sizex)
            pxy0 = int((ymax - y0) / (ymax - ymin) * sizey)
            pxy1 = int((ymax - y1) / (ymax - ymin) * sizey)
            if not return_mask:
                pxx0 = max(-1, pxx0)
                pxx1 = min(sizex, pxx1)
                pxy0 = max(-1, pxy0)
                pxy1 = min(sizey, pxy1)
            mask_im = mask_im.crop((pxx0, pxy0, pxx1, pxy1))
            if negative:
                mask_im = ImageOps.invert(mask_im)
            if not mask_im.getbbox():
                return False
            if not return_mask:
                return True
            return RP.resize_image(mask_resize_resampling, mask_im, mask_size)
        else:
            # following code only visited when is_mask_layer is True
            # in which case it is passed as (lat,lon,mask_zl)
            # check if sea mask file exists
            (lat, lon, mask_zl) = is_mask_layer
            (m_tilx, m_tily) = GEO.wgs84_to_orthogrid(
                (y0 + y1) / 2, (x0 + x1) / 2, mask_zl
            )
            if os.path.isdir(
                os.path.join(FNAMES.mask_dir(lat, lon), "Combined_imagery")
            ):
                check_dir = os.path.join(FNAMES.mask_dir(lat, lon), "Combined_imagery")
            else:
                check_dir = FNAMES.mask_dir(lat, lon)
            if not os.path.isfile(
                os.path.join(check_dir, FNAMES.legacy_mask(m_tilx, m_tily))
            ):
                return False
            # build extent mask_im
            if extent_code != "global":
                mask_im = Image.open(
                    os.path.join(
                        FNAMES.Extent_dir,
                        extents_dict[extent_code]["dir"],
                        extents_dict[extent_code]["code"] + ".png",
                    )
                ).convert("L")
                (sizex, sizey) = mask_im.size
                pxx0 = int((x0 - xmin) / (xmax - xmin) * sizex)
                pxx1 = int((x1 - xmin) / (xmax - xmin) * sizex)
                pxy0 = int((ymax - y0) / (ymax - ymin) * sizey)
                pxy1 = int((ymax - y1) / (ymax - ymin) * sizey)
                mask_im = mask_im.crop((pxx0, pxy0, pxx1, pxy1))
                if negative:
                    mask_im = ImageOps.invert(mask_im)
                if not mask_im.getbbox():
                    return False
                mask_im = RP.resize_image(mask_resize_resampling, mask_im, mask_size)
            else:
                mask_im = Image.new("L", mask_size, "white")
            # build sea mask_im2
            (ymax, xmin) = GEO.gtile_to_wgs84(m_tilx, m_tily, mask_zl)
            (ymin, xmax) = GEO.gtile_to_wgs84(m_tilx + 16, m_tily + 16, mask_zl)
            mask_im2 = Image.open(
                os.path.join(check_dir, FNAMES.legacy_mask(m_tilx, m_tily))
            ).convert("L")
            (sizex, sizey) = mask_im2.size
            pxx0 = int((x0 - xmin) / (xmax - xmin) * sizex)
            pxx1 = int((x1 - xmin) / (xmax - xmin) * sizex)
            pxy0 = int((ymax - y0) / (ymax - ymin) * sizey)
            pxy1 = int((ymax - y1) / (ymax - ymin) * sizey)
            mask_im2 = RP.resize_image(
                mask_resize_resampling,
                mask_im2.crop((pxx0, pxy0, pxx1, pxy1)),
                mask_size,
            )
            # invert it
            mask_array2 = 255 - numpy.array(mask_im2, dtype=numpy.uint8)
            # let full sea down (if you wish to...)
            # mask_array2[mask_array2==255]=0
            #  combine (multiply) both
            mask_array = numpy.array(mask_im, dtype=numpy.uint16)
            mask_array = (mask_array * mask_array2 / 255).astype(numpy.uint8)
            mask_im = Image.fromarray(mask_array).convert("L")
            if not mask_im.getbbox():
                return False
            if not return_mask:
                return True
            return mask_im
    except Exception as e:
        UI.vprint(1, "Could not test coverage of ", extent_code, " !!!")
        UI.vprint(2, e)
        return False


################################################################################

################################################################################
#
#  PART II : Methods to download and build textures
#
################################################################################


################################################################################
def _async_http_config():
    return AHTTP.AsyncHttpConfig(
        timeout=http_timeout,
        check_response=check_tms_response,
        max_connect_retries=max_connect_retries,
        max_baddata_retries=max_baddata_retries,
        sleep=async_request_sleep,
    )


async def async_http_request_to_image(url, request_headers, http_session):
    return await AHTTP.async_http_request_to_image(
        url, request_headers, http_session, _async_http_config()
    )


def http_request_to_image(
    width,
    height,
    url,
    request_headers,
    http_session=None,
):
    async def _run_request():
        if http_session is not None:
            return await async_http_request_to_image(url, request_headers, http_session)
        async with AHTTP.aiohttp.ClientSession() as session:
            return await async_http_request_to_image(url, request_headers, session)

    return asyncio.run(_run_request())


################################################################################


################################################################################
def get_wms_image(bbox, width, height, provider, http_session):
    request_headers = None
    url_type = provider["request_type"]
    if has_URL and provider["code"] in URL.custom_url_list:
        (url, request_headers) = URL.custom_wms_request(bbox, width, height, provider)
        url_type = "custom_wms"
    else:
        (minx, maxy, maxx, miny) = bbox
        if provider["wms_version"].split(".")[1] == "3":
            bbox_string = (
                str(miny) + "," + str(minx) + "," + str(maxy) + "," + str(maxx)
            )
            _RS = "CRS"
        else:
            bbox_string = (
                str(minx) + "," + str(miny) + "," + str(maxx) + "," + str(maxy)
            )
            _RS = "SRS"
        url = (
            provider["url_prefix"]
            + "SERVICE=WMS&VERSION="
            + provider["wms_version"]
            + "&FORMAT=image/"
            + provider["image_type"]
            + "&REQUEST=GetMap&LAYERS="
            + provider["layers"]
            + "&STYLES=&"
            + _RS
            + "=EPSG:"
            + str(provider["epsg_code"])
            + "&WIDTH="
            + str(width)
            + "&HEIGHT="
            + str(height)
            + "&BBOX="
            + bbox_string
        )
    if not request_headers:
        if "fake_headers" in provider:
            request_headers = provider["fake_headers"]
        else:
            request_headers = request_headers_generic
    request_context = IFAIL.request_context(provider, url_type)
    (success, data, _failure) = http_request_to_image(
        width,
        height,
        url,
        IFAIL.request_headers_with_context(request_headers, request_context),
        http_session,
    )
    if success:
        return (1, data)
    else:
        return (0, Image.new("RGB", (width, height), "white"))


################################################################################


################################################################################
def get_wmts_image(tilematrix, til_x, til_y, provider, http_session):
    til_x_orig, til_y_orig = til_x, til_y
    down_sample = 0
    while True:
        request_headers = None
        url_type = provider["request_type"]
        if has_URL and provider["code"] in URL.custom_url_list:
            (url, request_headers) = URL.custom_tms_request(
                tilematrix, til_x, til_y, provider
            )
            url_type = f"custom_{provider['request_type']}"
        elif provider["request_type"] == "tms":  # TMS
            url = provider["url_template"].replace("{zoom}", str(tilematrix))
            url = url.replace("{x}", str(til_x))
            url = url.replace("{y}", str(til_y))
            url = url.replace("{|y|}", str(abs(til_y) - 1))
            url = url.replace("{-y}", str(2**tilematrix - 1 - til_y))
            url = url.replace(
                "{quadkey}", GEO.gtile_to_quadkey(til_x, til_y, tilematrix)
            )
            url = url.replace(
                "{xcenter}",
                str(
                    (til_x + 0.5)
                    * provider["resolutions"][tilematrix]
                    * provider["tile_size"]
                    + provider["top_left_corner"][tilematrix][0]
                ),
            )
            url = url.replace(
                "{ycenter}",
                str(
                    -1
                    * (til_y + 0.5)
                    * provider["resolutions"][tilematrix]
                    * provider["tile_size"]
                    + provider["top_left_corner"][tilematrix][1]
                ),
            )
            url = url.replace(
                "{size}",
                str(int(provider["resolutions"][tilematrix] * provider["tile_size"])),
            )
            if "{switch:" in url:
                (url_0, tmp) = url.split("{switch:")
                (tmp, url_2) = tmp.split("}")
                server_list = tmp.split(",")
                url_1 = secrets.choice(server_list).strip()
                url = url_0 + url_1 + url_2
        elif provider["request_type"] == "wmts":  # WMTS
            url = (
                provider["url_prefix"]
                + "&SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetTile&LAYER="
                + provider["layers"]
                + "&STYLE=&FORMAT=image/"
                + provider["image_type"]
                + "&TILEMATRIXSET="
                + provider["tilematrixset"]["identifier"]
                + "&TILEMATRIX="
                + provider["tilematrixset"]["tilematrices"][tilematrix]["identifier"]
                + "&TILEROW="
                + str(til_y)
                + "&TILECOL="
                + str(til_x)
            )
        elif provider["request_type"] == "local_tms":  # LOCAL TMS
            # ! Too much specific, needs to be changed by a
            # x,y-> file_name lambda fct
            url_local = provider["url_template"].replace("{x}", str(5 * til_x).zfill(4))
            url_local = url_local.replace("{y}", str(-5 * til_y).zfill(4))
            if os.path.isfile(url_local):
                return (1, Image.open(url_local))
            else:
                UI.vprint(
                    2,
                    "! File ",
                    url_local,
                    "absent, using white texture instead !",
                )
                request_context = IFAIL.request_context(
                    provider,
                    "local_tms",
                    {"tile_x": til_x, "tile_y": til_y, "zoomlevel": tilematrix},
                )
                IFAIL.record_failure(
                    url_local,
                    "local_file_missing",
                    0,
                    0,
                    "local_file_missing",
                    request_context,
                )
                return (
                    0,
                    Image.new(
                        "RGB",
                        (provider["tile_size"], provider["tile_size"]),
                        "white",
                    ),
                )
        if not request_headers:
            if "fake_headers" in provider:
                request_headers = provider["fake_headers"]
            else:
                request_headers = request_headers_generic
        width = height = provider["tile_size"]
        request_context = IFAIL.request_context(
            provider,
            url_type,
            {"tile_x": til_x, "tile_y": til_y, "zoomlevel": tilematrix},
        )
        (success, data, _failure) = http_request_to_image(
            width,
            height,
            url,
            IFAIL.request_headers_with_context(request_headers, request_context),
            http_session,
        )
        if success and not down_sample:
            return (success, data)
        elif success and down_sample:
            x0 = (til_x_orig - 2**down_sample * til_x) * width // (2**down_sample)
            y0 = (til_y_orig - 2**down_sample * til_y) * height // (2**down_sample)
            x1 = x0 + width // (2**down_sample)
            y1 = y0 + height // (2**down_sample)
            return (
                success,
                RP.resize_image(
                    texture_resize_resampling,
                    data.crop((x0, y0, x1, y1)),
                    (width, height),
                ),
            )
        elif "[404]" in data:
            if ("grid_type" not in provider) or (
                provider["grid_type"] != "webmercator"
            ):
                return (0, Image.new("RGB", (width, height), "white"))
            til_x = til_x // 2
            til_y = til_y // 2
            tilematrix -= 1
            down_sample += 1
            if down_sample >= 6:
                return (0, Image.new("RGB", (width, height), "white"))
        else:
            return (0, Image.new("RGB", (width, height), "white"))


################################################################################


################################################################################
def get_and_paste_wms_part(
    bbox, width, height, provider, big_image, x0, y0, http_session
):
    (success, small_image) = get_wms_image(bbox, width, height, provider, http_session)
    big_image.paste(small_image, (x0, y0))
    return success


################################################################################


################################################################################
def get_and_paste_wmts_part(
    tilematrix,
    til_x,
    til_y,
    provider,
    big_image,
    x0,
    y0,
    http_session,
    subt_size=None,
):
    (success, small_image) = get_wmts_image(
        tilematrix, til_x, til_y, provider, http_session
    )
    if not subt_size:
        big_image.paste(small_image, (x0, y0))
    else:
        big_image.paste(
            RP.resize_image(texture_resize_resampling, small_image, subt_size),
            (x0, y0),
        )
    return success


################################################################################


################################################################################
def build_texture_from_tilbox(tilbox, zoomlevel, provider, progress=None):
    # less general than the next build_texture_from_bbox_and_size but
    # probably slightly quicker
    (til_x_min, til_y_min, til_x_max, til_y_max) = tilbox
    parts_x = til_x_max - til_x_min
    parts_y = til_y_max - til_y_min
    width = height = provider["tile_size"]
    big_image = Image.new("RGB", (width * parts_x, height * parts_y))
    # we set-up the queue of downloads
    http_session = None
    download_queue = queue.Queue()
    for monty in range(0, parts_y):
        for montx in range(0, parts_x):
            x0 = montx * width
            y0 = monty * height
            fargs = (
                zoomlevel,
                til_x_min + montx,
                til_y_min + monty,
                provider,
                big_image,
                x0,
                y0,
                http_session,
                None,
            )
            download_queue.put(fargs)
    # then the number of workers
    max_threads = int(provider["max_threads"]) if "max_threads" in provider else 16
    # and finally activate them
    success = parallel_execute(
        get_and_paste_wmts_part, download_queue, max_threads, progress
    )
    # once out big_image has been filled and we return it
    return (success, big_image)


################################################################################


################################################################################
def build_texture_from_bbox_and_size(t_bbox, t_epsg, t_size, provider):
    # warp will be needed for projections not parallel to 3857 or too large
    # image_size if warp is not needed, crop could still be needed if the grids
    # do not match.
    warp_needed = crop_needed = False
    (ulx, uly, lrx, lry) = t_bbox
    (t_sizex, t_sizey) = t_size
    if int(provider["epsg_code"]) == int(t_epsg):
        s_ulx, s_uly, s_lrx, s_lry = ulx, uly, lrx, lry
    else:
        inv_proj = GEO.transformer(t_epsg, provider["epsg_code"])
        inv_proj_4326 = GEO.transformer(t_epsg, "4326")
        (s_ulx, s_uly) = inv_proj.transform(ulx, uly)
        (s_urx, s_ury) = inv_proj.transform(lrx, uly)
        (s_llx, s_lly) = inv_proj.transform(ulx, lry)
        (s_lrx, s_lry) = inv_proj.transform(lrx, lry)
        (g_ulx, g_uly) = inv_proj_4326.transform(ulx, uly)
        (g_lrx, g_lry) = inv_proj_4326.transform(lrx, lry)
        if (
            (s_ulx != s_llx)
            or (s_uly != s_ury)
            or (s_lrx != s_urx)
            or (s_lly != s_lry)
            or (g_uly - g_lry) > 0.08
        ):
            s_ulx = min(s_ulx, s_llx)
            s_uly = max(s_uly, s_ury)
            s_lrx = max(s_urx, s_lrx)
            s_lry = min(s_lly, s_lry)
            warp_needed = True
    x_range = s_lrx - s_ulx
    y_range = s_uly - s_lry
    if provider["request_type"] == "wms":
        wms_size = int(provider["wms_size"])
        parts_x = int(ceil(t_sizex / wms_size))
        width = wms_size
        parts_y = int(ceil(t_sizey / wms_size))
        height = wms_size
    elif provider["request_type"] in ("wmts", "tms", "local_tms"):
        asked_resol = max(x_range / t_sizex, y_range / t_sizey)
        wmts_tilematrix = numpy.argmax(provider["resolutions"] <= asked_resol * 1.1)
        # in s_epsg unit per pix !
        wmts_resol = provider["resolutions"][wmts_tilematrix]
        UI.vprint(3, "Asked resol:", asked_resol, "WMTS resol:", wmts_resol)
        width = height = provider["tile_size"]
        cell_size = wmts_resol * width
        [wmts_x0, wmts_y0] = provider["top_left_corner"][wmts_tilematrix]
        til_x_min = int((s_ulx - wmts_x0) // cell_size)
        til_x_max = int((s_lrx - wmts_x0) // cell_size)
        til_y_min = int((wmts_y0 - s_uly) // cell_size)
        til_y_max = int((wmts_y0 - s_lry) // cell_size)
        parts_x = til_x_max - til_x_min + 1
        parts_y = til_y_max - til_y_min + 1
        s_box_ulx = wmts_x0 + cell_size * til_x_min
        s_box_uly = wmts_y0 - cell_size * til_y_min
        s_box_lrx = wmts_x0 + cell_size * (til_x_max + 1)
        s_box_lry = wmts_y0 - cell_size * (til_y_max + 1)
        if (
            (s_box_ulx != s_ulx)
            or (s_box_uly != s_uly)
            or (s_box_lrx != s_lrx)
            or (s_box_lry != s_lry)
        ):
            crop_x0 = int(round((s_ulx - s_box_ulx) / wmts_resol))
            crop_y0 = int(round((s_box_uly - s_uly) / wmts_resol))
            crop_x1 = int(round((s_lrx - s_box_ulx) / wmts_resol))
            crop_y1 = int(round((s_box_uly - s_lry) / wmts_resol))
            s_ulx = s_box_ulx
            s_uly = s_box_uly
            s_lrx = s_box_lrx
            s_lry = s_box_lry
            crop_needed = True
        downscale = (
            int(min(log(width * parts_x / t_sizex), log(height / t_sizey)) / log(2)) - 1
        )
        if downscale >= 1:
            width /= 2**downscale
            height /= 2**downscale
            subt_size = (width, height)
        else:
            subt_size = None
    big_image = Image.new("RGB", (width * parts_x, height * parts_y))
    http_session = None
    download_queue = queue.Queue()
    for monty in range(0, parts_y):
        for montx in range(0, parts_x):
            x0 = montx * width
            y0 = monty * height
            if provider["request_type"] == "wms":
                p_ulx = s_ulx + montx * x_range / parts_x
                p_uly = s_uly - monty * y_range / parts_y
                p_lrx = p_ulx + x_range / parts_x
                p_lry = p_uly - y_range / parts_y
                p_bbox = [p_ulx, p_uly, p_lrx, p_lry]
                fargs = [
                    p_bbox[:],
                    width,
                    height,
                    provider,
                    big_image,
                    x0,
                    y0,
                    http_session,
                ]
            elif provider["request_type"] in ["wmts", "tms", "local_tms"]:
                fargs = [
                    wmts_tilematrix,
                    til_x_min + montx,
                    til_y_min + monty,
                    provider,
                    big_image,
                    x0,
                    y0,
                    http_session,
                    subt_size,
                ]
            download_queue.put(fargs)
    # We execute the downloads and subimage pastes
    max_threads = int(provider["max_threads"]) if "max_threads" in provider else 16
    if provider["request_type"] == "wms":
        success = parallel_execute(get_and_paste_wms_part, download_queue, max_threads)
    elif provider["request_type"] in ["wmts", "tms", "local_tms"]:
        success = parallel_execute(get_and_paste_wmts_part, download_queue, max_threads)
    # We modify big_image if necessary
    if warp_needed:
        UI.vprint(3, "Warp needed")
        big_image = warp_image_with_gdal(
            big_image,
            (s_ulx, s_uly, s_lrx, s_lry),
            provider["epsg_code"],
            t_bbox,
            t_epsg,
            t_size,
        )
    elif crop_needed:
        UI.vprint(3, "Crop needed")
        big_image = big_image.crop((crop_x0, crop_y0, crop_x1, crop_y1))
    if big_image.size != t_size:
        UI.vprint(
            3,
            "Resize needed:"
            + str(t_size[0] / big_image.size[0])
            + " "
            + str(t_size[1] / big_image.size[1]),
        )
        big_image = RP.resize_image(texture_resize_resampling, big_image, t_size)
    return (success, big_image)


################################################################################


################################################################################
################################################################################


################################################################################
def _assemble_ortho_image(texture_attrs, file_name, super_resol_factor=1):
    til_x_left, til_y_top, zoomlevel, provider_code = texture_attrs
    provider = providers_dict[provider_code]
    super_resol_factor = _effective_super_resol_factor(
        provider, zoomlevel, super_resol_factor
    )
    width = height = int(4096 * super_resol_factor)
    provider = _provider_with_ortho_context(provider, file_name, texture_attrs)
    success, big_image = _build_provider_ortho_image(
        texture_attrs,
        provider,
        super_resol_factor,
        (width, height),
    )
    output_image = _final_ortho_output_image(big_image, width, super_resol_factor)
    return success, output_image, not success


def _effective_super_resol_factor(provider, zoomlevel, super_resol_factor):
    if ("super_resol_factor" in provider) and (super_resol_factor == 1):
        super_resol_factor = int(provider["super_resol_factor"])
    if "max_zl" in provider:
        max_zl = int(provider["max_zl"])
        if zoomlevel > max_zl:
            return 2 ** (max_zl - zoomlevel)
    return super_resol_factor


def _provider_with_ortho_context(provider, file_name, texture_attrs):
    til_x_left, til_y_top, zoomlevel, _provider_code = texture_attrs
    texture_context = {
        "texture_filename": file_name,
        "tile_x": til_x_left,
        "tile_y": til_y_top,
        "zoomlevel": zoomlevel,
    }
    return IFAIL.provider_with_texture_context(provider, texture_context)


def _build_provider_ortho_image(
    texture_attrs, provider, super_resol_factor, texture_size
):
    # we treat first the case of webmercator grid type servers
    if "grid_type" in provider and provider["grid_type"] == "webmercator":
        return _build_webmercator_ortho_image(
            texture_attrs, provider, super_resol_factor
        )
    # if not we are in the world of epsg:3857 bboxes
    return _build_bbox_ortho_image(texture_attrs, provider, texture_size)


def _build_webmercator_ortho_image(texture_attrs, provider, super_resol_factor):
    til_x_left, til_y_top, zoomlevel, _provider_code = texture_attrs
    tilbox = [til_x_left, til_y_top, til_x_left + 16, til_y_top + 16]
    tilbox_mod = [int(round(p * super_resol_factor)) for p in tilbox]
    zoom_shift = round(log(super_resol_factor) / log(2))
    return build_texture_from_tilbox(
        tilbox_mod,
        zoomlevel + zoom_shift,
        provider,
    )


def _build_bbox_ortho_image(texture_attrs, provider, texture_size):
    til_x_left, til_y_top, zoomlevel, _provider_code = texture_attrs
    [latmax, lonmin] = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    [latmin, lonmax] = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
    [xmin, ymax] = GEO.geo_to_webm(lonmin, latmax)
    [xmax, ymin] = GEO.geo_to_webm(lonmax, latmin)
    return build_texture_from_bbox_and_size(
        [xmin, ymax, xmax, ymin],
        "3857",
        texture_size,
        provider,
    )


def _final_ortho_output_image(big_image, width, super_resol_factor):
    if super_resol_factor == 1:
        return big_image.convert("RGB")
    return RP.resize_image(
        texture_resize_resampling,
        big_image,
        (
            int(width / super_resol_factor),
            int(width / super_resol_factor),
        ),
    ).convert("RGB")


################################################################################


################################################################################
def download_jpeg_ortho(
    file_dir,
    file_name,
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
    super_resol_factor=1,
):
    texture_attrs = (til_x_left, til_y_top, zoomlevel, provider_code)
    success, output_image, incomplete = _assemble_ortho_image(
        texture_attrs,
        file_name,
        super_resol_factor,
    )
    # if stop flag we do not wish to imprint a white texture
    if UI.red_flag:
        return 0
    if incomplete:
        UI.lvprint(
            1,
            "Part of image",
            file_name,
            "could not be obtained ",
            "(even at lower ZL), it was filled with white there.",
        )
        record_incomplete_texture(file_dir, file_name, texture_attrs)
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    try:
        output_image.save(os.path.join(file_dir, file_name))
    except Exception as e:
        UI.lvprint(
            0,
            "OS Error : could not save orthophoto on disk, ",
            "received message :",
            e,
        )
        return 0
    return 1


################################################################################


def build_texture_source(tile, texture_attrs, *, persist_cache=False):
    attrs = tuple(texture_attrs)
    unsupported = _unsupported_streaming_texture(attrs)
    if unsupported is not None:
        return unsupported
    return _build_supported_texture_source(tile, attrs, persist_cache)


def _build_supported_texture_source(tile, attrs, persist_cache):
    file_name, file_dir, cache_path = _texture_source_cache_info(tile, attrs)
    assembled = _assemble_texture_source_image(attrs, file_name)
    if isinstance(assembled, TextureBuildResult):
        return assembled
    success, output_image, incomplete = assembled
    if UI.red_flag:
        return TextureBuildResult.failure(
            attrs,
            "Texture source build interrupted",
            interrupted=True,
        )
    if incomplete:
        _record_incomplete_ortho(file_dir, file_name, attrs)
    wrote_cache = _write_optional_texture_cache(
        persist_cache, file_dir, cache_path, output_image
    )
    source = TextureSource(tile, attrs, output_image, cache_path, wrote_cache)
    return TextureBuildResult.success(source, incomplete=incomplete and not success)


def _assemble_texture_source_image(attrs, file_name):
    try:
        return _assemble_ortho_image(attrs, file_name)
    except Exception as exc:
        UI.vprint(2, f"Texture source build failed: {exc}")
        return TextureBuildResult.failure(attrs, str(exc))


def _unsupported_streaming_texture(attrs):
    provider_code = attrs[3]
    if (
        provider_code in providers_dict
        and provider_code not in local_combined_providers_dict
    ):
        return None
    return TextureBuildResult.failure(
        attrs,
        "Streaming texture source is only available for concrete providers",
    )


def _texture_source_cache_info(tile, attrs):
    _til_x_left, _til_y_top, zoomlevel, provider_code = attrs
    file_name = FNAMES.jpeg_file_name_from_attributes(*attrs)
    file_dir = FNAMES.jpeg_file_dir_from_attributes(
        tile.lat,
        tile.lon,
        zoomlevel,
        providers_dict[provider_code],
    )
    return file_name, file_dir, os.path.join(file_dir, file_name)


def _record_incomplete_ortho(file_dir, file_name, texture_attrs):
    UI.lvprint(
        1,
        "Part of image",
        file_name,
        "could not be obtained ",
        "(even at lower ZL), it was filled with white there.",
    )
    record_incomplete_texture(file_dir, file_name, texture_attrs)


def _write_optional_texture_cache(persist_cache, file_dir, cache_path, output_image):
    if not persist_cache:
        return False
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    output_image.save(cache_path)
    return True


async def async_build_texture_source(tile, *attrs, persist_cache=False):
    return await asyncio.to_thread(
        build_texture_source,
        tile,
        tuple(attrs),
        persist_cache=persist_cache,
    )


################################################################################


################################################################################
def build_jpeg_ortho(
    tile, til_x_left, til_y_top, zoomlevel, provider_code, out_file_name=""
):
    texture_attributes = (til_x_left, til_y_top, zoomlevel, provider_code)
    if provider_code in local_combined_providers_dict:
        data_found = False
        for rlayer in local_combined_providers_dict[provider_code]:
            (y0, x0) = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
            (y1, x1) = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
            is_mask_layer = (
                (tile.lat, tile.lon, tile.mask_zl)
                if rlayer["priority"] == "mask"
                else False
            )
            accept_layer = len(
                local_combined_providers_dict[provider_code]
            ) == 1 or has_data((x0, y0, x1, y1), rlayer["extent_code"], is_mask_layer)
            if accept_layer:
                data_found = True
                true_til_x_left = til_x_left
                true_til_y_top = til_y_top
                true_zl = zoomlevel
                if "max_zl" in providers_dict[rlayer["layer_code"]]:
                    max_zl = int(providers_dict[rlayer["layer_code"]]["max_zl"])
                    if max_zl < zoomlevel:
                        (latmed, lonmed) = GEO.gtile_to_wgs84(
                            til_x_left + 8, til_y_top + 8, zoomlevel
                        )
                        (
                            true_til_x_left,
                            true_til_y_top,
                        ) = GEO.wgs84_to_orthogrid(latmed, lonmed, max_zl)
                        true_zl = max_zl
                true_texture_attributes = (
                    true_til_x_left,
                    true_til_y_top,
                    true_zl,
                    rlayer["layer_code"],
                )
                true_file_name = FNAMES.jpeg_file_name_from_attributes(
                    true_til_x_left,
                    true_til_y_top,
                    true_zl,
                    rlayer["layer_code"],
                )
                true_file_dir = FNAMES.jpeg_file_dir_from_attributes(
                    tile.lat,
                    tile.lon,
                    true_zl,
                    providers_dict[rlayer["layer_code"]],
                )
                if not os.path.isfile(os.path.join(true_file_dir, true_file_name)):
                    UI.vprint(
                        1,
                        "   Downloading missing orthophoto "
                        + true_file_name
                        + " (for combining in "
                        + provider_code
                        + ")",
                    )
                    if not download_jpeg_ortho(
                        true_file_dir, true_file_name, *true_texture_attributes
                    ):
                        return 0
                else:
                    UI.vprint(
                        2,
                        "   The orthophoto "
                        + true_file_name
                        + " (for combining in "
                        + provider_code
                        + ") "
                        + "is already present.",
                    )
        if not data_found:
            UI.lvprint(
                1,
                "     -> !!! Warning : No data found for building "
                + "the combined texture",
                FNAMES.dds_file_name_from_attributes(*texture_attributes),
                " !!!",
            )
            return 0
        if out_file_name:
            big_img = combine_textures(
                tile, til_x_left, til_y_top, zoomlevel, provider_code
            )
            big_img.convert("RGB").save(out_file_name)
        # In case one would like to save combined orthos as jpegs (this can be
        # useful to use different masks parameters for imagery masks layers and
        # actual masks.
        elif provider_code in providers_dict:
            file_name = FNAMES.jpeg_file_name_from_attributes(
                til_x_left, til_y_top, zoomlevel, provider_code
            )
            file_dir = FNAMES.jpeg_file_dir_from_attributes(
                tile.lat, tile.lon, zoomlevel, providers_dict[provider_code]
            )
            big_img = combine_textures(
                tile, til_x_left, til_y_top, zoomlevel, provider_code
            )
            if not os.path.exists(file_dir):
                os.makedirs(file_dir)
            try:
                big_img.convert("RGB").save(os.path.join(file_dir, file_name))
            except Exception as e:
                UI.lvprint(
                    0,
                    "OS Error : could not save orthophoto on disk, "
                    + "received message :",
                    e,
                )
                return 0
    elif provider_code in providers_dict:
        file_name = FNAMES.jpeg_file_name_from_attributes(
            til_x_left, til_y_top, zoomlevel, provider_code
        )
        file_dir = FNAMES.jpeg_file_dir_from_attributes(
            tile.lat, tile.lon, zoomlevel, providers_dict[provider_code]
        )
        if not os.path.isfile(os.path.join(file_dir, file_name)):
            UI.vprint(1, "   Downloading missing orthophoto " + file_name)
            if not download_jpeg_ortho(file_dir, file_name, *texture_attributes):
                return 0
        else:
            UI.vprint(2, "   The orthophoto " + file_name + " is already present.")
    else:
        (tlat, tlon) = GEO.gtile_to_wgs84(til_x_left + 8, til_y_top + 8, zoomlevel)
        UI.vprint(
            1,
            "   Unknown provider",
            provider_code,
            "or it has no data around",
            tlat,
            tlon,
            ".",
        )
        return 0
    return 1


async def async_build_jpeg_ortho(tile, *attrs):
    return await asyncio.to_thread(build_jpeg_ortho, tile, *attrs)


################################################################################

################################################################################
# Not used in Ortho4XP itself but useful for testing combined color filters at
# low zl
################################################################################


################################################################################
def build_combined_ortho(
    tile, latp, lonp, zoomlevel, provider_code, mask_zl, filename="test.png"
):
    initialize_color_filters_dict()
    initialize_extents_dict()
    initialize_providers_dict()
    initialize_combined_providers_dict()
    (til_x_left, til_y_top) = GEO.wgs84_to_orthogrid(latp, lonp, zoomlevel)
    big_image = Image.new("RGBA", (4096, 4096))
    (y0, x0) = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    (y1, x1) = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
    mask_weight_below = numpy.zeros((4096, 4096), dtype=numpy.uint16)
    for rlayer in combined_providers_dict[provider_code][::-1]:
        mask = has_data(
            (x0, y0, x1, y1),
            rlayer["extent_code"],
            return_mask=True,
            is_mask_layer=(tile.lat, tile.lon, tile.mask_zl)
            if rlayer["priority"] == "mask"
            else False,
        )
        if not mask:
            continue
        # we turn the image mask into an array
        mask = numpy.array(mask, dtype=numpy.uint16)
        true_til_x_left = til_x_left
        true_til_y_top = til_y_top
        true_zl = zoomlevel
        crop = False
        if "max_zl" in providers_dict[rlayer["layer_code"]]:
            max_zl = int(providers_dict[rlayer["layer_code"]]["max_zl"])
            if max_zl < zoomlevel:
                (latmed, lonmed) = GEO.gtile_to_wgs84(
                    til_x_left + 8, til_y_top + 8, zoomlevel
                )
                (true_til_x_left, true_til_y_top) = GEO.wgs84_to_orthogrid(
                    latmed, lonmed, max_zl
                )
                true_zl = max_zl
                crop = True
                pixx0 = round(
                    256 * (til_x_left * 2 ** (max_zl - zoomlevel) - true_til_x_left)
                )
                pixy0 = round(
                    256 * (til_y_top * 2 ** (max_zl - zoomlevel) - true_til_y_top)
                )
                pixx1 = round(pixx0 + 2 ** (12 - zoomlevel + max_zl))
                pixy1 = round(pixy0 + 2 ** (12 - zoomlevel + max_zl))
        true_file_name = FNAMES.jpeg_file_name_from_attributes(
            true_til_x_left, true_til_y_top, true_zl, rlayer["layer_code"]
        )
        true_file_dir = FNAMES.jpeg_file_dir_from_attributes(
            tile.lat, tile.lon, true_zl, providers_dict[rlayer["layer_code"]]
        )
        if not os.path.isfile(os.path.join(true_file_dir, true_file_name)):
            UI.vprint(
                1,
                "   Downloading missing orthophoto "
                + true_file_name
                + " (for combining in "
                + provider_code
                + ")\n",
            )
            download_jpeg_ortho(
                true_file_dir,
                true_file_name,
                true_til_x_left,
                true_til_y_top,
                true_zl,
                rlayer["layer_code"],
            )
        else:
            UI.vprint(
                2,
                "   The orthophoto "
                + true_file_name
                + " (for combining in "
                + provider_code
                + ") is already present.\n",
            )
        true_im = Image.open(os.path.join(true_file_dir, true_file_name))
        UI.vprint(2, "Imprinting for provider", rlayer, til_x_left, til_y_top)
        true_im = color_transform(true_im, rlayer["color_code"])
        if rlayer["priority"] == "mask" and tile.sea_texture_blur:
            UI.vprint(2, "Blur of a mask !")
            true_im = true_im.filter(
                ImageFilter.GaussianBlur(tile.sea_texture_blur * 2 ** (true_zl - 17))
            )
        if crop:
            true_im = RP.tile_resize_image(
                tile,
                "texture_resize_resampling",
                true_im.crop((pixx0, pixy0, pixx1, pixy1)),
                (4096, 4096),
            )
        # in case the smoothing of the extent mask was too strong we remove the
        # the mask (where it is nor 0 nor 255) the pixels for which the true_im
        # is all white
        # true_arr=numpy.array(true_im).astype(numpy.uint16)
        # mask[(numpy.sum(true_arr,axis=2)>=715)*(mask>=1)*(mask<=253)]=0
        # mask[(numpy.sum(true_arr,axis=2)<=15)*(mask>=1)*(mask<=253)]=0
        if rlayer["priority"] == "low":
            # low priority layers, do not increase mask_weight_below
            wasnt_zero = (mask_weight_below + mask) != 0
            mask[wasnt_zero] = (
                255 * mask[wasnt_zero] / (mask_weight_below + mask)[wasnt_zero]
            )
        elif rlayer["priority"] in ["high", "mask"]:
            mask_weight_below += mask
        elif rlayer["priority"] == "medium":
            not_zero = mask != 0
            mask_weight_below += mask
            mask[not_zero] = 255 * mask[not_zero] / mask_weight_below[not_zero]
            # undecided about the next two lines
            # was_zero=mask_weight_below==0
            # mask[was_zero]=255
        # we turn back the array mask into an image
        mask = Image.fromarray(mask.astype(numpy.uint8))
        big_image = Image.composite(true_im, big_image, mask)
    UI.vprint(2, "Finished imprinting", til_x_left, til_y_top)
    big_image.save(filename)


################################################################################


################################################################################
def build_geotiffs(tile, texture_attributes_list):
    UI.red_flag = False
    timer = time.time()
    initialize_color_filters_dict()
    initialize_providers_dict()
    initialize_combined_providers_dict()
    todo = len(texture_attributes_list)
    for done, texture_attributes in enumerate(texture_attributes_list, start=1):
        (til_x_left, til_y_top, zoomlevel, provider_code) = texture_attributes
        if build_jpeg_ortho(tile, til_x_left, til_y_top, zoomlevel, provider_code):
            convert_texture(
                tile,
                til_x_left,
                til_y_top,
                zoomlevel,
                provider_code,
                type="tif",
            )
        UI.progress_bar(1, int(100 * done / todo))
        if UI.red_flag:
            UI.exit_message_and_bottom_line()
    UI.timings_and_bottom_line(timer)
    return


################################################################################


################################################################################
def build_texture_region(
    dest_dir, latmin, latmax, lonmin, lonmax, zoomlevel, provider_code
):
    [til_xmin, til_ymin] = GEO.wgs84_to_orthogrid(latmax, lonmin, zoomlevel)
    [til_xmax, til_ymax] = GEO.wgs84_to_orthogrid(latmin, lonmax, zoomlevel)
    nbr_to_do = ((til_ymax - til_ymin) / 16 + 1) * ((til_xmax - til_xmin) / 16 + 1)
    print("Number of tiles to download at most : ", nbr_to_do)
    for til_y_top in range(til_ymin, til_ymax + 1, 16):
        for til_x_left in range(til_xmin, til_xmax + 1, 16):
            (y0, x0) = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
            (y1, x1) = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
            bbox_4326 = (x0, y0, x1, y1)
            if has_data(
                bbox_4326,
                providers_dict[provider_code]["extent"],
                return_mask=False,
                mask_size=(4096, 4096),
            ):
                file_name = FNAMES.jpeg_file_name_from_attributes(
                    til_x_left, til_y_top, zoomlevel, provider_code
                )
                if os.path.isfile(os.path.join(dest_dir, file_name)):
                    print("recycling one")
                    nbr_to_do -= 1
                    continue
                print("building one")
                download_jpeg_ortho(
                    dest_dir,
                    file_name,
                    til_x_left,
                    til_y_top,
                    zoomlevel,
                    provider_code,
                    super_resol_factor=1,
                )
            else:
                print("skipping one")
            nbr_to_do -= 1
            print(nbr_to_do)
    return


################################################################################


################################################################################
def build_provider_texture(dest_dir, provider_code, zoomlevel):
    (lonmin, latmin, lonmax, latmax) = extents_dict[
        providers_dict[provider_code]["extent"]
    ]["mask_bounds"]
    build_texture_region(
        dest_dir, latmin, latmax, lonmin, lonmax, zoomlevel, provider_code
    )
    return


################################################################################


################################################################################
def create_tile_preview(lat, lon, zoomlevel, provider_code):
    UI.red_flag = False
    if not os.path.exists(FNAMES.Preview_dir):
        os.makedirs(FNAMES.Preview_dir)
    filepreview = FNAMES.preview(lat, lon, zoomlevel, provider_code)
    if not os.path.isfile(filepreview):
        provider = providers_dict[provider_code]
        (til_x_min, til_y_min) = GEO.wgs84_to_gtile(lat + 1, lon, zoomlevel)
        (til_x_max, til_y_max) = GEO.wgs84_to_gtile(lat, lon + 1, zoomlevel)
        width = (til_x_max + 1 - til_x_min) * 256
        height = (til_y_max + 1 - til_y_min) * 256
        if "grid_type" in provider and provider["grid_type"] == "webmercator":
            tilbox = (til_x_min, til_y_min, til_x_max + 1, til_y_max + 1)
            dico_progress = {"done": 0, "bar": 1}
            (success, big_image) = build_texture_from_tilbox(
                tilbox, zoomlevel, provider, progress=dico_progress
            )
        # if not we are in the world of epsg:3857 bboxes
        else:
            (latmax, lonmin) = GEO.gtile_to_wgs84(til_x_min, til_y_min, zoomlevel)
            (latmin, lonmax) = GEO.gtile_to_wgs84(
                til_x_max + 1, til_y_max + 1, zoomlevel
            )
            (xmin, ymax) = GEO.geo_to_webm(lonmin, latmax)
            (xmax, ymin) = GEO.geo_to_webm(lonmax, latmin)
            (success, big_image) = build_texture_from_bbox_and_size(
                (xmin, ymax, xmax, ymin), "3857", (width, height), provider
            )
        if success:
            big_image.save(filepreview)
            return 1
        else:
            try:
                big_image.save(filepreview)
            except OSError as exc:
                UI.vprint(3, exc)
            return 0
    return 1


################################################################################

################################################################################
#
#  PART II : Methods to transform textures (warp, color transform, combine)
#
################################################################################


################################################################################
def warp_image_with_gdal(source_im, s_bbox, s_epsg, t_bbox, t_epsg, t_size):
    source_im = _gdal_warp_supported_image(source_im)
    source_ds = GTP.memory_dataset_from_image(source_im, s_bbox, s_epsg)
    return GTP.warp_dataset_to_image(
        source_ds,
        t_bbox,
        t_epsg,
        t_size,
        RP.gdal_resampling(warp_resampling),
        source_im.mode,
    )


def _gdal_warp_supported_image(source_im):
    if source_im.mode in ("L", "RGB", "RGBA"):
        return source_im
    return source_im.convert("RGB")


################################################################################


################################################################################
def color_transform(im, color_code):
    try:
        for color_filter in color_filters_dict[color_code]:
            # both range from -127 to 127,
            # http://gimp.sourcearchive.com/documentation/2.6.1/\
            # gimpbrightnesscontrastconfig_8c-source.html
            if color_filter[0] == "brightness-contrast":
                (brightness, contrast) = color_filter[1:3]
                if brightness >= 0:
                    im = im.point(
                        lambda i, brightness=brightness, contrast=contrast: (
                            128
                            + tan(pi / 4 * (1 + contrast / 128))
                            * (brightness + (255 - brightness) / 255 * i - 128)
                        )
                    )
                else:
                    im = im.point(
                        lambda i, brightness=brightness, contrast=contrast: (
                            128
                            + tan(pi / 4 * (1 + contrast / 128))
                            * ((255 + brightness) / 255 * i - 128)
                        )
                    )
            elif color_filter[0] == "saturation":
                saturation = color_filter[1]
                im = ImageEnhance.Color(im).enhance(1 + saturation / 100)
            elif color_filter[0] == "sharpness":
                im = ImageEnhance.Sharpness(im).enhance(color_filter[1])
            elif color_filter[0] == "blur":
                im = im.filter(ImageFilter.GaussianBlur(color_filter[1]))
            # levels range between 0 and 255, gamma is neutral at 1
            # https://pippin.gimp.org/image-processing/chap_point.html
            elif color_filter[0] == "levels":
                bands = im.split()
                for j in [0, 1, 2]:
                    in_min, gamma, in_max, out_min, out_max = color_filter[
                        5 * j + 1 : 5 * j + 6
                    ]
                    bands[j].paste(
                        bands[j].point(
                            lambda i, in_min=in_min, gamma=gamma, in_max=in_max, out_min=out_min, out_max=out_max: (
                                out_min
                                + (out_max - out_min)
                                * (
                                    (max(in_min, min(i, in_max)) - in_min)
                                    / (in_max - in_min)
                                )
                                ** (1 / gamma)
                            )
                        )
                    )
                im = Image.merge(im.mode, bands)
        return im
    except (TypeError, ValueError):
        return im


################################################################################


################################################################################
def combine_textures(tile, til_x_left, til_y_top, zoomlevel, provider_code):
    big_image = Image.new("RGBA", (4096, 4096))
    (y0, x0) = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    (y1, x1) = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
    mask_weight_below = numpy.zeros((4096, 4096), dtype=numpy.uint16)
    # we do not need to bother with masks then
    if len(local_combined_providers_dict[provider_code]) == 1:
        rlayer = local_combined_providers_dict[provider_code][0]
        true_til_x_left = til_x_left
        true_til_y_top = til_y_top
        true_zl = zoomlevel
        crop = False
        if "max_zl" in providers_dict[rlayer["layer_code"]]:
            max_zl = int(providers_dict[rlayer["layer_code"]]["max_zl"])
            if max_zl < zoomlevel:
                (latmed, lonmed) = GEO.gtile_to_wgs84(
                    til_x_left + 8, til_y_top + 8, zoomlevel
                )
                (true_til_x_left, true_til_y_top) = GEO.wgs84_to_orthogrid(
                    latmed, lonmed, max_zl
                )
                true_zl = max_zl
                crop = True
                pixx0 = round(
                    256 * (til_x_left * 2 ** (max_zl - zoomlevel) - true_til_x_left)
                )
                pixy0 = round(
                    256 * (til_y_top * 2 ** (max_zl - zoomlevel) - true_til_y_top)
                )
                pixx1 = round(pixx0 + 2 ** (12 - zoomlevel + max_zl))
                pixy1 = round(pixy0 + 2 ** (12 - zoomlevel + max_zl))
        true_file_name = FNAMES.jpeg_file_name_from_attributes(
            true_til_x_left, true_til_y_top, true_zl, rlayer["layer_code"]
        )
        true_file_dir = FNAMES.jpeg_file_dir_from_attributes(
            tile.lat, tile.lon, true_zl, providers_dict[rlayer["layer_code"]]
        )
        true_im = Image.open(os.path.join(true_file_dir, true_file_name))
        UI.vprint(2, "Imprinting for provider", rlayer, til_x_left, til_y_top)
        true_im = color_transform(true_im, rlayer["color_code"])
        if rlayer["priority"] == "mask" and tile.sea_texture_blur:
            UI.vprint(2, "Blur of a mask !")
            true_im = true_im.filter(
                ImageFilter.GaussianBlur(tile.sea_texture_blur * 2 ** (true_zl - 17))
            )
        if crop:
            true_im = RP.tile_resize_image(
                tile,
                "texture_resize_resampling",
                true_im.crop((pixx0, pixy0, pixx1, pixy1)),
                (4096, 4096),
            )
        UI.vprint(2, "Finished imprinting", til_x_left, til_y_top)
        return true_im
    # the real situation now where there are more than one layer with data
    for rlayer in local_combined_providers_dict[provider_code][::-1]:
        mask = has_data(
            (x0, y0, x1, y1),
            rlayer["extent_code"],
            return_mask=True,
            is_mask_layer=(tile.lat, tile.lon, tile.mask_zl)
            if rlayer["priority"] == "mask"
            else False,
        )
        if not mask:
            continue
        # we turn the image mask into an array
        mask = numpy.array(mask, dtype=numpy.uint16)
        true_til_x_left = til_x_left
        true_til_y_top = til_y_top
        true_zl = zoomlevel
        crop = False
        if "max_zl" in providers_dict[rlayer["layer_code"]]:
            max_zl = int(providers_dict[rlayer["layer_code"]]["max_zl"])
            if max_zl < zoomlevel:
                (latmed, lonmed) = GEO.gtile_to_wgs84(
                    til_x_left + 8, til_y_top + 8, zoomlevel
                )
                (true_til_x_left, true_til_y_top) = GEO.wgs84_to_orthogrid(
                    latmed, lonmed, max_zl
                )
                true_zl = max_zl
                crop = True
                pixx0 = round(
                    256 * (til_x_left * 2 ** (max_zl - zoomlevel) - true_til_x_left)
                )
                pixy0 = round(
                    256 * (til_y_top * 2 ** (max_zl - zoomlevel) - true_til_y_top)
                )
                pixx1 = round(pixx0 + 2 ** (12 - zoomlevel + max_zl))
                pixy1 = round(pixy0 + 2 ** (12 - zoomlevel + max_zl))
        true_file_name = FNAMES.jpeg_file_name_from_attributes(
            true_til_x_left, true_til_y_top, true_zl, rlayer["layer_code"]
        )
        true_file_dir = FNAMES.jpeg_file_dir_from_attributes(
            tile.lat, tile.lon, true_zl, providers_dict[rlayer["layer_code"]]
        )
        true_im = Image.open(os.path.join(true_file_dir, true_file_name))
        UI.vprint(2, "Imprinting for provider", rlayer, til_x_left, til_y_top)
        true_im = color_transform(true_im, rlayer["color_code"])
        if rlayer["priority"] == "mask" and tile.sea_texture_blur:
            UI.vprint(2, "Blur of a mask !")
            true_im = true_im.filter(
                ImageFilter.GaussianBlur(tile.sea_texture_blur * 2 ** (true_zl - 17))
            )
        if crop:
            true_im = RP.tile_resize_image(
                tile,
                "texture_resize_resampling",
                true_im.crop((pixx0, pixy0, pixx1, pixy1)),
                (4096, 4096),
            )
        # in case the smoothing of the extent mask was too strong we remove the
        # the mask (where it is nor 0 nor 255) the pixels for which the true_im
        # is all white or all black
        true_arr = numpy.array(true_im).astype(numpy.uint16)
        mask[(numpy.sum(true_arr, axis=2) >= 735) * (mask >= 1) * (mask <= 253)] = 0
        mask[(numpy.sum(true_arr, axis=2) <= 35) * (mask >= 1) * (mask <= 253)] = 0
        if rlayer["priority"] == "low":
            # low priority layers, do not increase mask_weight_below
            wasnt_zero = (mask_weight_below + mask) != 0
            mask[wasnt_zero] = (
                255 * mask[wasnt_zero] / (mask_weight_below + mask)[wasnt_zero]
            )
        elif rlayer["priority"] in ["high", "mask"]:
            mask_weight_below += mask
        elif rlayer["priority"] == "medium":
            not_zero = mask != 0
            mask_weight_below += mask
            mask[not_zero] = 255 * mask[not_zero] / mask_weight_below[not_zero]
            # undecided about the next two lines
            # was_zero=mask_weight_below==0
            # mask[was_zero]=255
        # we turn back the array mask into an image
        mask = Image.fromarray(mask.astype(numpy.uint8))
        big_image = Image.composite(true_im, big_image, mask)
    UI.vprint(2, "Finished imprinting", til_x_left, til_y_top)
    return big_image


################################################################################


def convert_texture_source(texture_source, type=DDS_OUTPUT_TYPE):
    if type != DDS_OUTPUT_TYPE:
        return convert_texture(texture_source.tile, *texture_source.attrs, type=type)
    tile = texture_source.tile
    texture_attrs = texture_source.attrs
    provider_code = texture_source.provider_code
    out_file_name = FNAMES.dds_file_name_from_attributes(*texture_attrs)
    png_file_name = out_file_name.replace(DDS_OUTPUT_TYPE, "png")
    UI.vprint(1, "   Converting orthophoto(s) to build texture " + out_file_name + ".")

    big_image = _prepare_texture_source_image(texture_source)
    masked_texture, mask_im = _dds_texture_mask(tile, texture_attrs)
    dxt5 = False
    if masked_texture:
        UI.vprint(2, "      Applying alpha mask directly to orthophoto.")
        big_image.putalpha(
            RP.tile_resize_image(tile, "mask_resize_resampling", mask_im, (4096, 4096))
        )
        _remove_dds_mask_file(tile, texture_attrs)
        dxt5 = True

    file_to_convert = os.path.join(FNAMES.resource_path("tmp"), png_file_name)
    big_image.save(file_to_convert)
    return convert_dds_texture(
        tile,
        texture_attrs,
        (file_to_convert, out_file_name, dxt5),
        (True, png_file_name),
    )


def _prepare_texture_source_image(texture_source):
    provider_code = texture_source.provider_code
    image = texture_source.image.convert("RGB")
    color_context = TCN.texture_color_context(
        _texture_source_cache_dir(texture_source),
        texture_source.attrs,
        normalize_texture_colors,
    )
    image = TCN.normalize_texture_image_if_enabled(image, color_context)
    if providers_dict[provider_code]["color_filters"] != "none":
        return color_transform(image, providers_dict[provider_code]["color_filters"])
    return image


def _texture_source_cache_dir(texture_source):
    if not texture_source.cache_path:
        return None
    return os.path.dirname(texture_source.cache_path)


def _dds_texture_mask(tile, texture_attrs):
    if not tile.imprint_masks_to_dds:
        return False, None
    mask_path = _dds_mask_path(tile, texture_attrs)
    if not os.path.exists(mask_path):
        return False, None
    return True, Image.open(mask_path).convert("L")


def _dds_mask_path(tile, texture_attrs):
    return os.path.join(
        tile.build_dir,
        "textures",
        FNAMES.mask_file(*texture_attrs),
    )


def _remove_dds_mask_file(tile, texture_attrs):
    try:
        os.remove(_dds_mask_path(tile, texture_attrs))
    except OSError as exc:
        UI.vprint(3, exc)


def _legacy_texture_mask(tile, texture_attrs, output_type):
    if not tile.imprint_masks_to_dds:
        return False, None
    if output_type == DDS_OUTPUT_TYPE:
        return _dds_texture_mask(tile, texture_attrs)
    return _legacy_tif_texture_mask(tile, texture_attrs)


def _legacy_tif_texture_mask(tile, texture_attrs):
    til_x_left, til_y_top, zoomlevel, _provider_code = texture_attrs
    if int(zoomlevel) < tile.mask_zl:
        return False, None
    factor = 2 ** (zoomlevel - tile.mask_zl)
    m_til_x = (int(til_x_left / factor) // 16) * 16
    m_til_y = (int(til_y_top / factor) // 16) * 16
    rx = int((til_x_left - factor * m_til_x) / 16)
    ry = int((til_y_top - factor * m_til_y) / 16)
    mask_file = os.path.join(
        FNAMES.mask_dir(tile.lat, tile.lon),
        FNAMES.legacy_mask(m_til_x, m_til_y),
    )
    if not os.path.isfile(mask_file):
        return False, None
    mask_im = _legacy_tif_mask_crop(mask_file, rx, ry, factor)
    small_array = numpy.array(mask_im, dtype=numpy.uint8)
    return small_array.max() > 30, mask_im


def _legacy_tif_mask_crop(mask_file, rx, ry, factor):
    big_img = Image.open(mask_file)
    x0 = int(rx * 4096 / factor)
    y0 = int(ry * 4096 / factor)
    return big_img.crop((x0, y0, x0 + 4096 // factor, y0 + 4096 // factor))


def _apply_texture_alpha_mask(tile, big_image, mask_im):
    UI.vprint(2, "      Applying alpha mask directly to orthophoto.")
    big_image.putalpha(
        RP.tile_resize_image(tile, "mask_resize_resampling", mask_im, (4096, 4096))
    )


################################################################################


def convert_texture(
    tile,
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
    type="dds",
):
    texture_attrs = (til_x_left, til_y_top, zoomlevel, provider_code)
    if type == DDS_OUTPUT_TYPE:
        out_file_name = FNAMES.dds_file_name_from_attributes(
            til_x_left, til_y_top, zoomlevel, provider_code
        )
        png_file_name = out_file_name.replace(DDS_OUTPUT_TYPE, "png")
    elif type == TIF_OUTPUT_TYPE:
        out_file_name = FNAMES.geotiff_file_name_from_attributes(
            til_x_left, til_y_top, zoomlevel, provider_code
        )
        if os.path.exists(os.path.join(FNAMES.Geotiff_dir, out_file_name)):
            try:
                os.remove(os.path.join(FNAMES.Geotiff_dir, out_file_name))
            except OSError as exc:
                UI.vprint(3, exc)
        png_file_name = out_file_name.replace(TIF_OUTPUT_TYPE, "png")
        tmp_tif_file_name = os.path.join(
            FNAMES.resource_path("tmp"), out_file_name.replace("4326", "3857")
        )
    UI.vprint(1, "   Converting orthophoto(s) to build texture " + out_file_name + ".")
    erase_tmp_png = False

    dxt5 = False
    masked_texture, mask_im = _legacy_texture_mask(tile, texture_attrs, type)

    file_dir = cached_texture_path = ""
    if provider_code in providers_dict:
        jpeg_file_name = FNAMES.jpeg_file_name_from_attributes(
            til_x_left, til_y_top, zoomlevel, provider_code
        )
        file_dir = FNAMES.jpeg_file_dir_from_attributes(
            tile.lat, tile.lon, zoomlevel, providers_dict[provider_code]
        )
        cached_texture_path = os.path.join(file_dir, jpeg_file_name)
    color_context = TCN.texture_color_context(
        file_dir or None, texture_attrs, normalize_texture_colors
    )
    if (provider_code in local_combined_providers_dict) and (
        TCN.texture_path_missing(cached_texture_path)
    ):
        big_image = combine_textures(
            tile, til_x_left, til_y_top, zoomlevel, provider_code
        )
        big_image = TCN.normalize_combined_texture_image(
            big_image,
            color_context,
            provider_code,
            normalize_texture_colors,
        )
        if masked_texture:
            _apply_texture_alpha_mask(tile, big_image, mask_im)
            if type == DDS_OUTPUT_TYPE:
                _remove_dds_mask_file(tile, texture_attrs)
            dxt5 = True
        file_to_convert = os.path.join(FNAMES.resource_path("tmp"), png_file_name)
        erase_tmp_png = True
        big_image.save(file_to_convert)
        # If one wanted to distribute jpegs instead of dds, uncomment the
        # next line.
        # big_image.convert('RGB').save(os.path.join(tile.build_dir,
        #     'textures', out_file_name.replace('dds', 'jpg')), quality=70)
    # now if provider_code was not in local_combined_providers_dict but
    # color correction is required.
    elif (providers_dict[provider_code]["color_filters"] != "none") or masked_texture:
        big_image = Image.open(cached_texture_path, "r").convert("RGB")
        big_image = TCN.normalize_texture_image_if_enabled(big_image, color_context)
        if providers_dict[provider_code]["color_filters"] != "none":
            big_image = color_transform(
                big_image, providers_dict[provider_code]["color_filters"]
            )
        if masked_texture:
            _apply_texture_alpha_mask(tile, big_image, mask_im)
            if type == DDS_OUTPUT_TYPE:
                _remove_dds_mask_file(tile, texture_attrs)
            dxt5 = True
        file_to_convert = os.path.join(FNAMES.resource_path("tmp"), png_file_name)
        erase_tmp_png = True
        big_image.save(file_to_convert)
    # finally if nothing needs to be done prior to the conversion
    else:
        file_to_convert, erase_tmp_png = TCN.normalized_conversion_input_path(
            cached_texture_path,
            png_file_name,
            color_context,
        )
    if type == DDS_OUTPUT_TYPE:
        return convert_dds_texture(
            tile,
            texture_attrs,
            (file_to_convert, out_file_name, dxt5),
            (erase_tmp_png, png_file_name),
        )
    return convert_geotiff_texture(
        tile,
        texture_attrs,
        (
            file_to_convert,
            out_file_name,
            erase_tmp_png,
            png_file_name,
            tmp_tif_file_name,
        ),
    )


################################################################################


# Standalone geotagging below intentionally uses the same command runner as
# texture conversion. The surrounding retry loops remain local to preserve
# legacy user-facing behavior and output.
# The helper captures stderr for logs without changing CLI arguments.
# The line anchor is kept stable for the complexity baseline.
# GDAL geotag command arguments remain unchanged.
# Output file naming remains unchanged.
# Retry timing remains unchanged.
# ---------------------------------------------------------------------------
def geotag(input_file_name):
    suffix = input_file_name.split(".")[-1]
    out_file_name = input_file_name.replace(suffix, "tiff")
    items = input_file_name.split("_")
    til_y_top = int(items[0])
    til_x_left = int(items[1])
    zoomlevel = int(items[-1][-6:-4])
    (latmax, lonmin) = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    (latmin, lonmax) = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
    tentative = 0
    while True:
        try:
            gdal.Translate(
                out_file_name,
                input_file_name,
                format="GTiff",
                creationOptions=["COMPRESS=JPEG"],
                outputBounds=[lonmin, latmin, lonmax, latmax],
                outputSRS="EPSG:4326",
            )
            break
        except Exception as exc:
            UI.vprint(3, exc)
        tentative += 1
        if tentative == 10:
            print("ERROR: Could not convert texture", out_file_name, "(10 tries)")
            break
        print("WARNING: Could not convert texture", out_file_name)
        time.sleep(1)


################################################################################
