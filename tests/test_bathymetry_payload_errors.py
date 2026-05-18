import struct
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import BathymetryInputError, validate_raster_payload
from tests.test_bathymetry_input import atom, demd, demi, demn_payload, dems_payload


class BathymetryPayloadErrorTests(unittest.TestCase):
    def test_extra_raster_with_wrong_payload_size_is_rejected(self):
        extra_raster = atom(b"DEMI", demi(2, 2)) + atom(b"DEMD", b"\0")
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*temperature.*expected",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level", "temperature"),
                dems_payload() + extra_raster,
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_malformed_dems_payload_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMS",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                b"too-short",
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_non_ascii_dems_atom_header_is_rejected_with_context(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMS",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                b"\xffMED" + struct.pack("<I", 8),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_non_canonical_dems_atom_byte_order_is_rejected(self):
        non_canonical_dems = atom(b"IMED", demi(2, 2)) + atom(b"DMED", demd(2, 2))
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMS",
        ):
            validate_raster_payload(
                demn_payload("elevation"),
                non_canonical_dems,
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_empty_demn_layer_entry_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMN",
        ):
            validate_raster_payload(
                b"elevation\0\0sea_level\0",
                dems_payload(),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_extra_trailing_demn_empty_entry_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMN",
        ):
            validate_raster_payload(
                b"elevation\0sea_level\0\0",
                dems_payload(),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_truncated_demn_final_name_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMN",
        ):
            validate_raster_payload(
                b"elevation\0sea_level",
                dems_payload(),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_oversized_demi_metadata_is_rejected(self):
        oversized_elevation = atom(b"DEMI", demi(2, 2) + b"x") + atom(
            b"DEMD", demd(2, 2)
        )
        sea_level = atom(b"DEMI", demi(2, 2)) + atom(b"DEMD", demd(2, 2))
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMI",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                oversized_elevation + sea_level,
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )


if __name__ == "__main__":
    unittest.main()
