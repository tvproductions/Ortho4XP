import os
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Vector_Map as VMAP

WARNING = (
    "WARNING: Airport OSM query failed; continuing vector construction "
    "without airport data."
)


def airport_tile():
    return SimpleNamespace(
        lat=12,
        lon=-123,
        dem=object(),
        custom_dem="custom-dem.tif",
        fill_nodata=None,
    )


@contextmanager
def failed_airport_mocks(patch_area):
    order = []

    def record_patches(*_args):
        order.append("patches")
        return (patch_area, ["custom"])

    def record_output(*args, **_kwargs):
        if args == (1, WARNING):
            order.append("warning")

    with (
        mock.patch.object(VMAP.OSM, "OSM_layer", return_value=object()),
        mock.patch.object(VMAP.OSM, "OSM_queries_to_OSM_layer", return_value=False),
        mock.patch.object(
            VMAP, "include_patches", side_effect=record_patches
        ) as include_patches,
        mock.patch.object(VMAP.APT_DISC, "discover_airport_names") as discover,
        mock.patch.object(VMAP.UI, "vprint", side_effect=record_output) as vprint,
        mock.patch.object(VMAP.UI, "log_event") as log_event,
    ):
        yield SimpleNamespace(
            include_patches=include_patches,
            discover=discover,
            vprint=vprint,
            log_event=log_event,
            order=order,
        )


def _patch_airport_preparation(stack, order):
    stack.enter_context(
        mock.patch.multiple(
            VMAP.APT_DISC,
            discover_airport_names=mock.DEFAULT,
            attach_surfaces_to_airports=mock.DEFAULT,
            sort_and_reconstruct_runways=mock.DEFAULT,
            discard_unwanted_airports=mock.DEFAULT,
            list_airports_and_runways=mock.DEFAULT,
        )
    )
    stack.enter_context(
        mock.patch.multiple(
            VMAP.APT_GEOM,
            build_hangar_areas=mock.DEFAULT,
            build_apron_areas=mock.DEFAULT,
            build_taxiway_areas=mock.DEFAULT,
            update_airport_boundaries=mock.DEFAULT,
        )
    )
    stack.enter_context(
        mock.patch.object(
            VMAP.APT_GEOM,
            "smooth_raster_over_airports",
            side_effect=lambda *_args: order.append("smooth"),
        )
    )


@contextmanager
def successful_airport_mocks(fixture):
    order = []
    airport_layer = object()
    patch_names = ["custom"]
    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(VMAP.OSM, "OSM_layer", return_value=airport_layer)
        )
        stack.enter_context(
            mock.patch.object(VMAP.OSM, "OSM_queries_to_OSM_layer", return_value=True)
        )
        _patch_airport_preparation(stack, order)
        calls = _patch_airport_encoding(stack, fixture, patch_names, order)
        stack.enter_context(mock.patch.object(VMAP.UI, "vprint"))
        calls.airport_layer = airport_layer
        calls.patch_names = patch_names
        calls.order = order
        yield calls


def _patch_airport_encoding(stack, fixture, patch_names, order):
    include_patches = stack.enter_context(
        mock.patch.object(
            VMAP,
            "include_patches",
            side_effect=lambda *_args: (
                order.append("patches") or (fixture.patch_area, patch_names)
            ),
        )
    )
    encode_airports = stack.enter_context(
        mock.patch.object(
            VMAP.APT_ENC,
            "encode_runways_taxiways_and_aprons",
            return_value=fixture.airport_area,
        )
    )
    stack.enter_context(mock.patch.object(VMAP.APT_ENC, "encode_hangars"))
    flatten_helipads = stack.enter_context(
        mock.patch.object(VMAP.APT_ENC, "flatten_helipads")
    )
    stack.enter_context(
        mock.patch.object(
            VMAP.APT_GEOM,
            "build_airport_array",
            return_value=fixture.airport_mask,
        )
    )
    dem_constructor = stack.enter_context(mock.patch.object(VMAP.INPUTS.DEM, "DEM"))
    return SimpleNamespace(
        include_patches=include_patches,
        encode_airports=encode_airports,
        flatten_helipads=flatten_helipads,
        dem_constructor=dem_constructor,
    )


def builder_tile(tmpdir):
    return SimpleNamespace(
        lat=12,
        lon=-123,
        build_dir=os.path.join(tmpdir, "build"),
        custom_dem="custom-dem.tif",
        fill_nodata=None,
        road_level=1,
    )


class BuilderProbe:
    def __init__(self, testcase, fixture):
        self.testcase = testcase
        self.fixture = fixture
        self.order = []

    def construct_dem(self, *_args, **_kwargs):
        self.order.append("dem")
        return self.fixture.dem

    def include_airports(self, _vector_map, tile):
        self.testcase.assertIs(getattr(tile, "dem", None), self.fixture.dem)
        self.order.append("airports")
        return (
            self.fixture.airport_mask,
            self.fixture.airport_area,
            self.fixture.patch_area,
        )

    def include_roads(self, *args):
        _vector_map, tile, received_mask, treated_area = args
        self.testcase.assertIs(tile.dem, self.fixture.dem)
        self.testcase.assertIs(received_mask, self.fixture.airport_mask)
        self.testcase.assertTrue(treated_area.equals(self.fixture.expected_union))
        self.order.append("roads")
        self.fixture.ctx.red_flag = True


@contextmanager
def builder_mocks(tmpdir, vector_map, probe):
    osm_dir = os.path.join(tmpdir, "osm")
    with (
        mock.patch.object(VMAP.INPUTS.VECT, "Vector_Map", return_value=vector_map),
        mock.patch.object(
            VMAP.INPUTS.DEM, "DEM", side_effect=probe.construct_dem
        ) as dem_constructor,
        mock.patch.object(VMAP, "include_airports", side_effect=probe.include_airports),
        mock.patch.object(VMAP, "include_roads", side_effect=probe.include_roads),
        mock.patch.object(VMAP.FNAMES, "osm_dir", return_value=osm_dir),
        mock.patch.object(
            VMAP.FNAMES,
            "input_node_file",
            return_value=os.path.join(tmpdir, "tile.node"),
        ),
        mock.patch.object(
            VMAP.FNAMES,
            "input_poly_file",
            return_value=os.path.join(tmpdir, "tile.poly"),
        ),
        mock.patch.object(VMAP.UI, "logprint"),
        mock.patch.object(VMAP.UI, "vprint"),
        mock.patch.object(VMAP.UI, "exit_message_and_bottom_line"),
    ):
        yield dem_constructor
