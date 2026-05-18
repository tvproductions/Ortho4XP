import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import (
    BathymetryInputError,
    RasterPayload,
    validate_raster_payload,
)


def atom(name: bytes, payload: bytes) -> bytes:
    return name[::-1] + struct.pack("<I", len(payload) + 8) + payload


def raw_atom(name: bytes, payload: bytes) -> bytes:
    return name + struct.pack("<I", len(payload) + 8) + payload


def demn_payload(*names: str) -> bytes:
    return b"".join(name.encode("ascii") + b"\0" for name in names)


def demi(width: int, height: int, bytes_per_pixel: int = 2) -> bytes:
    flags = 1
    return struct.pack(
        "<BBHIIff",
        1,
        bytes_per_pixel,
        flags,
        width,
        height,
        1.0,
        0.0,
    )


def demd(width: int, height: int, bytes_per_pixel: int = 2, value: int = 7) -> bytes:
    if bytes_per_pixel == 1:
        return bytes([value]) * width * height
    if bytes_per_pixel == 2:
        return struct.pack("<" + "h" * width * height, *([value] * width * height))
    raise AssertionError("fixture only supports 1 or 2 byte pixels")


def dems_payload(
    *,
    elevation_size: tuple[int, int] = (2, 2),
    sea_level_size: tuple[int, int] = (2, 2),
    include_sea_level: bool = True,
    empty_sea_level: bool = False,
) -> bytes:
    elevation = atom("DEMI".encode("ascii"), demi(*elevation_size)) + atom(
        "DEMD".encode("ascii"), demd(*elevation_size)
    )
    if not include_sea_level:
        return elevation
    sea_data = b"" if empty_sea_level else demd(*sea_level_size)
    return (
        elevation
        + atom("DEMI".encode("ascii"), demi(*sea_level_size))
        + atom("DEMD".encode("ascii"), sea_data)
    )


class BathymetryInputTests(unittest.TestCase):
    def test_valid_payload_requires_elevation_and_sea_level(self):
        payload = validate_raster_payload(
            demn_payload("elevation", "sea_level"),
            dems_payload(),
            tile_label="+12-123",
            source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
        )

        self.assertIsInstance(payload, RasterPayload)
        self.assertEqual(payload.layer_names, ("elevation", "sea_level"))
        self.assertEqual(payload.elevation.width, 2)
        self.assertEqual(payload.elevation.height, 2)
        self.assertEqual(payload.bathymetry.width, 2)
        self.assertEqual(payload.bathymetry.height, 2)

    def test_missing_sea_level_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*sea_level.*XP12 Global Scenery",
        ):
            validate_raster_payload(
                demn_payload("elevation"),
                dems_payload(include_sea_level=False),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_empty_sea_level_payload_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*sea_level.*empty",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                dems_payload(empty_sea_level=True),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_mismatched_bathymetry_shape_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*sea_level.*2x3.*elevation.*2x2",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                dems_payload(sea_level_size=(2, 3)),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_extra_raster_with_wrong_payload_size_is_rejected(self):
        extra_raster = atom("DEMI".encode("ascii"), demi(2, 2)) + atom(
            "DEMD".encode("ascii"), b"\0"
        )
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
        non_canonical_dems = atom("IMED".encode("ascii"), demi(2, 2)) + atom(
            "DMED".encode("ascii"), demd(2, 2)
        )
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
        oversized_elevation = atom("DEMI".encode("ascii"), demi(2, 2) + b"x") + atom(
            "DEMD".encode("ascii"), demd(2, 2)
        )
        sea_level = atom("DEMI".encode("ascii"), demi(2, 2)) + atom(
            "DEMD".encode("ascii"), demd(2, 2)
        )
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


def dsf_file(*, demn: bytes, dems: bytes) -> bytes:
    body = raw_atom("NFED".encode("ascii"), raw_atom("NMED".encode("ascii"), demn))
    body += raw_atom("SMED".encode("ascii"), dems)
    return b"XPLNEDSF" + struct.pack("<I", 1) + body + (b"0" * 16)


class GlobalSceneryProviderTests(unittest.TestCase):
    def test_extract_validated_global_scenery_rasters(self):
        from O4_Bathymetry_Input import extract_validated_rasters_from_dsf_bytes

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
        from O4_Bathymetry_Input import extract_validated_rasters_from_dsf_bytes

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
        from O4_Bathymetry_Input import extract_validated_rasters_from_dsf_bytes

        with self.assertRaisesRegex(BathymetryInputError, r"corrupted DSF"):
            extract_validated_rasters_from_dsf_bytes(
                b"not-a-dsf",
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )


class BathymetrySourceLookupTests(unittest.TestCase):
    def test_missing_global_scenery_dsf_is_rejected(self):
        from O4_Bathymetry_Input import extract_validated_global_scenery_rasters

        with tempfile.TemporaryDirectory() as tmp:
            missing_primary = str(Path(tmp) / "primary")
            missing_alternate = str(Path(tmp) / "alternate")
            with self.assertRaisesRegex(
                BathymetryInputError,
                r"custom_overlay_src.*custom_overlay_src_alternate.*XP12 Global Scenery",
            ):
                extract_validated_global_scenery_rasters(
                    12,
                    -123,
                    primary_overlay_src=missing_primary,
                    alternate_overlay_src=missing_alternate,
                    tmp_dir=str(Path(tmp) / "tmp"),
                    unzip_executable="7z",
                    run_external_tool=lambda *args, **kwargs: None,
                )

    def test_reads_uncompressed_global_scenery_dsf(self):
        from O4_Bathymetry_Input import extract_validated_global_scenery_rasters

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            dsf_path = root / "Earth nav data" / "+10-130" / "+12-123.dsf"
            dsf_path.parent.mkdir(parents=True)
            dsf_path.write_bytes(
                dsf_file(
                    demn=demn_payload("elevation", "sea_level"),
                    dems=dems_payload(),
                )
            )

            result = extract_validated_global_scenery_rasters(
                12,
                -123,
                primary_overlay_src=str(root),
                alternate_overlay_src="",
                tmp_dir=str(Path(tmp) / "tmp"),
                unzip_executable="7z",
                run_external_tool=mock.Mock(),
            )

        self.assertEqual(result.payload.bathymetry.name, "sea_level")


if __name__ == "__main__":
    unittest.main()
