import os
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Texture_Color_Normalization as TCN
import O4_Texture_Conversion_Utils as TCU


class ImageryColorNormalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_enabled = IMG.normalize_texture_colors
        self.addCleanup(self._restore_state)

    def _restore_state(self):
        IMG.normalize_texture_colors = self.original_enabled

    def _color_for_edge(self, edge):
        return {
            "north": (100, 110, 120),
            "south": (120, 110, 100),
            "west": (80, 100, 120),
            "east": (120, 100, 80),
        }[edge]

    def _color_context(self, provider_code="BI", enabled=True):
        return TCN.TextureColorContext(
            self.temp_dir.name,
            32,
            48,
            16,
            provider_code,
            enabled,
        )


class ConvertTexturePatchMixin(ImageryColorNormalizationTestCase):
    def _tile_for_conversion(self):
        build_dir = os.path.join(self.temp_dir.name, "build")
        os.makedirs(os.path.join(build_dir, "textures"), exist_ok=True)
        return SimpleNamespace(
            build_dir=build_dir,
            imprint_masks_to_dds=False,
            lat=1,
            lon=2,
        )

    def _write_cached_jpeg(self, provider_code):
        path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 48, 16, provider_code),
        )
        Image.new("RGB", (16, 16), (90, 80, 70)).save(path)
        return path

    def _convert_texture_patches(self, provider_code, **options):
        settings = _ConversionPatchSettings.from_options(options)
        tmp_dir = self._conversion_tmp_dir()
        patches = _conversion_patches(
            settings, provider_code, self.temp_dir.name, tmp_dir
        )
        return ConvertTexturePatchContext(patches, SimpleNamespace(ok=True), tmp_dir)

    def _conversion_tmp_dir(self):
        tmp_dir = os.path.join(self.temp_dir.name, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir


class _ConversionPatchSettings:
    def __init__(self, color_filters, provider_in_cache, combined_provider):
        self.color_filters = color_filters
        self.provider_in_cache = provider_in_cache
        self.combined_provider = combined_provider

    @classmethod
    def from_options(cls, options):
        return cls(
            options.get("color_filters", "none"),
            options.get("provider_in_cache", True),
            options.get("combined_provider", False),
        )

    def providers(self, provider_code):
        if not self.provider_in_cache:
            return {}
        provider = {"code": provider_code, "color_filters": self.color_filters}
        return {provider_code: provider}

    def combined_providers(self, provider_code):
        if not self.combined_provider:
            return {}
        return {provider_code: [{"code": provider_code}]}


def _conversion_core_patch():
    return mock.patch.multiple(
        IMG,
        is_macos=False,
        color_transform=mock.DEFAULT,
        combine_textures=mock.DEFAULT,
    )


def _conversion_patches(settings, provider_code, jpeg_dir, tmp_dir):
    return SimpleNamespace(
        core=_conversion_core_patch(),
        gdal_mock=mock.patch.object(TCU, "gdal"),
        encode=mock.patch.object(TCU.TEX, "encode_texture"),
        normalize=mock.patch.object(TCN, "normalize_texture_image_if_enabled"),
        data=[
            mock.patch.dict(
                IMG.providers_dict, settings.providers(provider_code), clear=True
            ),
            mock.patch.dict(
                IMG.local_combined_providers_dict,
                settings.combined_providers(provider_code),
                clear=True,
            ),
            mock.patch.object(
                FNAMES, "jpeg_file_dir_from_attributes", return_value=jpeg_dir
            ),
            mock.patch.object(FNAMES, "resource_path", return_value=tmp_dir),
        ],
        vprint=mock.patch.object(IMG.UI, "vprint"),
    )


def _texture_encode_result():
    return TCU.TEX.TextureEncodeResult(
        request=TCU.TEX.TextureEncodeRequest(
            source_path="input.png",
            output_path="output.dds",
            codec="bc1",
            display_name="output.dds",
        ),
        ok=True,
        attempts=1,
        backend_name="native",
        tool_name="nvcompress",
        returncode=0,
        error_summary="",
    )


class ConvertTexturePatchContext:
    def __init__(self, patches, command_result, tmp_dir):
        self.patches = patches
        self.command_result = command_result
        self.tmp_dir = tmp_dir
        self.stack = ExitStack()

    def __enter__(self):
        multiple_mocks = self.stack.enter_context(self.patches.core)
        self.gdal = self.stack.enter_context(self.patches.gdal_mock)
        self.color_transform = multiple_mocks["color_transform"]
        self.combine_textures = multiple_mocks["combine_textures"]
        self.encode_texture = self.stack.enter_context(self.patches.encode)
        self.encode_texture.return_value = _texture_encode_result()
        self.normalize = self.stack.enter_context(self.patches.normalize)
        for patcher in self.patches.data:
            self.stack.enter_context(patcher)
        self.vprint = self.stack.enter_context(self.patches.vprint)
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.stack.close()

    @property
    def run_external_command(self):
        return self.gdal.Translate

    @property
    def encode_request(self):
        return self.encode_texture.call_args.args[0]
