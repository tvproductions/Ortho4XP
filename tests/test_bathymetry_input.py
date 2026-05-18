import struct
import unittest

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
    elevation = atom("IMED".encode("ascii"), demi(*elevation_size)) + atom(
        "DMED".encode("ascii"), demd(*elevation_size)
    )
    if not include_sea_level:
        return elevation
    sea_data = b"" if empty_sea_level else demd(*sea_level_size)
    return (
        elevation
        + atom("IMED".encode("ascii"), demi(*sea_level_size))
        + atom("DMED".encode("ascii"), sea_data)
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


if __name__ == "__main__":
    unittest.main()
