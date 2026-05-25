"""Parser and splice tests for native DSF header text.

The fixture text includes supported header lines, unrelated properties, and a
body block.  These tests protect the conservative allowlist and the insertion
point used by the DSFTool bridge.
"""

import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_DSF_Header_Text import (
    extract_supported_header_lines,
    splice_supported_header_lines,
)
from tests._dsf_header_bridge_helpers import DEFAULT_DSF_TEXT, GENERATED_DSF_TEXT


class DsfHeaderTextTests(unittest.TestCase):
    def test_extracts_only_supported_native_header_lines(self):
        lines = extract_supported_header_lines(DEFAULT_DSF_TEXT)

        self.assertEqual(
            lines,
            (
                "PROPERTY sim/season/winter_raster Resources/default scenery/winter.png",
                "PROPERTY sim/vegetation_region pacific_northwest",
                "PROPERTY sim/soundscape airport_terminal_small",
                "PROPERTY sim/runway_friction 0.82",
                "ATTR_season winter",
            ),
        )

    def test_splices_supported_lines_after_generated_property_block(self):
        result = splice_supported_header_lines(
            GENERATED_DSF_TEXT,
            (
                "PROPERTY sim/season/winter_raster Resources/default scenery/winter.png",
                "ATTR_season winter",
            ),
        )

        self.assertEqual(
            result,
            """PROPERTY sim/west -123
PROPERTY sim/east -122
PROPERTY sim/south 12
PROPERTY sim/north 13
PROPERTY sim/season/winter_raster Resources/default scenery/winter.png
ATTR_season winter
TERRAIN_DEF terrain/ortho.ter
BEGIN_PATCH 0
END_PATCH
""",
        )

    def test_splice_deduplicates_existing_supported_lines(self):
        generated = (
            "PROPERTY sim/west -123\n"
            "PROPERTY sim/season/winter_raster Resources/default scenery/winter.png\n"
            "TERRAIN_DEF terrain/ortho.ter\n"
        )

        result = splice_supported_header_lines(
            generated,
            (
                "PROPERTY sim/season/winter_raster Resources/default scenery/winter.png",
                "ATTR_season winter",
            ),
        )

        self.assertEqual(
            result,
            (
                "PROPERTY sim/west -123\n"
                "PROPERTY sim/season/winter_raster Resources/default scenery/winter.png\n"
                "ATTR_season winter\n"
                "TERRAIN_DEF terrain/ortho.ter\n"
            ),
        )


if __name__ == "__main__":
    unittest.main()
