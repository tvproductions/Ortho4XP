import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX
import O4_Tile_Utils as TILE


def _tile():
    return SimpleNamespace(lat=12, lon=-123)


class TileTextureConversionSummaryTests(unittest.TestCase):
    def test_reports_failed_conversion_providers(self):
        result = TCS.TextureConversionBatchResult(
            completed=3,
            failed=2,
            interrupted=False,
            failures=(
                TEX.TextureConversionResult.failure("a.dds", "BI", "bad"),
                TEX.TextureConversionResult.failure("b.dds", "GO2", "bad"),
            ),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(
            1,
            "DDS conversion summary:",
            "2 failed texture(s)",
            "for tile +12-123.",
            "Providers: BI=1, GO2=1.",
        )

    def test_reports_successful_conversion_completion(self):
        result = TCS.TextureConversionBatchResult(
            completed=2,
            failed=0,
            interrupted=False,
            failures=(),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, " *DDS conversion of textures completed.")

    def test_reports_interrupted_conversion(self):
        result = TCS.TextureConversionBatchResult(
            completed=0,
            failed=0,
            interrupted=True,
            failures=(),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, "DDS conversion process interrupted.")


if __name__ == "__main__":
    unittest.main()
