import struct
from pathlib import Path
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import GlobalSceneryRasterSource


def atom(name: bytes, payload: bytes) -> bytes:
    return name[::-1] + struct.pack("<I", len(payload) + 8) + payload


def raw_atom(name: bytes, payload: bytes) -> bytes:
    return name + struct.pack("<I", len(payload) + 8) + payload


def demn_payload(*names: str) -> bytes:
    return b"".join(name.encode("ascii") + b"\0" for name in names)


def demi(width: int, height: int, bytes_per_pixel: int = 2) -> bytes:
    return struct.pack(
        "<BBHIIff",
        1,
        bytes_per_pixel,
        1,
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


def dems_payload(*, include_sea_level: bool = True) -> bytes:
    elevation = atom(b"DEMI", demi(2, 2)) + atom(b"DEMD", demd(2, 2))
    if not include_sea_level:
        return elevation
    return elevation + atom(b"DEMI", demi(2, 2)) + atom(b"DEMD", demd(2, 2))


def dsf_file(*, demn: bytes, dems: bytes) -> bytes:
    body = raw_atom(b"NFED", raw_atom(b"NMED", demn))
    body += raw_atom(b"SMED", dems)
    return b"XPLNEDSF" + struct.pack("<I", 1) + body + (b"0" * 16)


def valid_dsf_file() -> bytes:
    return dsf_file(
        demn=demn_payload("elevation", "sea_level"),
        dems=dems_payload(),
    )


def global_scenery_dsf_path(root: Path) -> Path:
    return root / "Earth nav data" / "+10-130" / "+12-123.dsf"


def raster_source(
    tmp: str,
    *,
    primary: Path | str,
    alternate: Path | str = "",
    run_external_tool=None,
) -> GlobalSceneryRasterSource:
    if run_external_tool is None:
        run_external_tool = mock.Mock()
    return GlobalSceneryRasterSource(
        lat=12,
        lon=-123,
        primary_overlay_src=str(primary),
        alternate_overlay_src=str(alternate),
        tmp_dir=str(Path(tmp) / "tmp"),
        unzip_executable="7z",
        run_external_tool=run_external_tool,
    )
