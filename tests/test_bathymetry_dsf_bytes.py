import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import (
    BathymetryInputError,
    extract_validated_rasters_from_dsf_bytes,
)
from tests.test_bathymetry_provider import demn_payload, dems_payload, dsf_file


class BathymetryDsfByteTests(unittest.TestCase):
    def test_extract_validated_rasters_from_dsf_bytes(self):
        demn = demn_payload("elevation", "sea_level")
        dems = dems_payload()
        result = extract_validated_rasters_from_dsf_bytes(
            dsf_file(demn=demn, dems=dems),
            tile_label="+12-123",
            source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
        )

        self.assertEqual(result.demn, demn)
        self.assertEqual(result.dems, dems)
        self.assertEqual(result.payload.bathymetry.name, "sea_level")

    def test_rejects_dsf_without_required_rasters(self):
        with self.assertRaisesRegex(BathymetryInputError, r"missing sea_level"):
            extract_validated_rasters_from_dsf_bytes(
                dsf_file(
                    demn=demn_payload("elevation"),
                    dems=dems_payload(include_sea_level=False),
                ),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_rejects_corrupted_dsf_header(self):
        with self.assertRaisesRegex(BathymetryInputError, r"corrupted DSF"):
            extract_validated_rasters_from_dsf_bytes(
                b"not-a-dsf",
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )


if __name__ == "__main__":
    unittest.main()
