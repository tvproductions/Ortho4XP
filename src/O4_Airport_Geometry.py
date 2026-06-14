import pickle
from math import ceil, floor

import numpy
from PIL import Image, ImageDraw
from shapely import affinity, geometry, ops
from shapely.errors import GEOSException

import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_UI_Utils as UI
import O4_Vector_Utils as VECT


def build_hangar_areas(tile, airport_layer, dico_airports):
    for airport in dico_airports:
        wayid_list = dico_airports[airport]["hangar"]
        hangars = []
        for wayid in wayid_list:
            try:
                pol = geometry.Polygon(
                    numpy.round(
                        numpy.array(
                            [
                                airport_layer.dicosmn[nodeid]
                                for nodeid in airport_layer.dicosmw[wayid]
                            ]
                        )
                        - numpy.array([[tile.lon, tile.lat]]),
                        7,
                    )
                )
                if not pol.is_valid:
                    continue
            except (KeyError, TypeError, ValueError, GEOSException):
                UI.vprint(
                    2,
                    "Unable to turn hangar area to polygon, close to",
                    airport_layer.dicosmn[airport_layer.dicosmw[wayid][0]],
                )
                continue
            hangars.append(pol)
        hangars = VECT.ensure_MultiPolygon(
            VECT.improved_buffer(ops.unary_union(hangars), 2, 1, 0.5)
        )
        dico_airports[airport]["hangar"] = hangars


def build_apron_areas(tile, airport_layer, dico_airports):
    for airport in dico_airports:
        wayid_list = dico_airports[airport]["apron"]
        aprons = []
        for wayid in wayid_list:
            try:
                pol = geometry.Polygon(
                    numpy.round(
                        numpy.array(
                            [
                                airport_layer.dicosmn[nodeid]
                                for nodeid in airport_layer.dicosmw[wayid]
                            ]
                        )
                        - numpy.array([[tile.lon, tile.lat]]),
                        7,
                    )
                )
                if not pol.is_valid:
                    UI.vprint(
                        2,
                        "Unable to turn apron area to polygon, close to",
                        airport_layer.dicosmn[airport_layer.dicosmw[wayid][0]],
                    )
                    continue
            except (KeyError, TypeError, ValueError, GEOSException):
                UI.vprint(
                    2,
                    "Unable to turn apron area to polygon, close to",
                    airport_layer.dicosmn[airport_layer.dicosmw[wayid][0]],
                )
                continue
            aprons.append(pol)
        aprons = VECT.ensure_MultiPolygon(ops.unary_union(aprons))
        dico_airports[airport]["apron"] = (
            aprons,
            dico_airports[airport]["apron"],
        )
    return


def build_taxiway_areas(tile, airport_layer, dico_airports):
    for airport in dico_airports:
        wayid_list = dico_airports[airport]["taxiway"]
        taxiways = geometry.MultiLineString(
            [
                geometry.LineString(
                    numpy.round(
                        numpy.array(
                            [
                                airport_layer.dicosmn[nodeid]
                                for nodeid in airport_layer.dicosmw[wayid]
                            ]
                        )
                        - numpy.array([[tile.lon, tile.lat]]),
                        7,
                    )
                )
                for wayid in wayid_list
            ]
        )
        taxiways = VECT.ensure_MultiPolygon(VECT.improved_buffer(taxiways, 15, 3, 0.5))
        dico_airports[airport]["taxiway"] = (
            taxiways,
            dico_airports[airport]["taxiway"],
        )
    return


def update_airport_boundaries(tile, dico_airports):
    for airport in dico_airports:
        apt = dico_airports[airport]
        boundary = ops.unary_union(
            [
                apt["taxiway"][0],
                apt["apron"][0],
                apt["hangar"],
                apt["runway"][0],
            ]
        )
        if apt["boundary"]:
            apt["boundary"] = VECT.ensure_MultiPolygon(
                ops.unary_union(
                    [
                        affinity.translate(apt["boundary"], -tile.lon, -tile.lat),
                        boundary,
                    ]
                )
                .buffer(0)
                .simplify(0.00001)
            )
        else:
            apt["boundary"] = VECT.ensure_MultiPolygon(
                boundary.buffer(0).simplify(0.00001)
            )
    try:
        with open(FNAMES.apt_file(tile), "wb") as outf:
            pickle.dump(dico_airports, outf)
    except (OSError, pickle.PicklingError) as exc:
        UI.vprint(
            1,
            "WARNING: Could not save airport info to file",
            FNAMES.apt_file(tile),
        )
        UI.vprint(3, exc)
    return


def build_airport_array(tile, dico_airports):
    airport_array = numpy.zeros((1001, 1001), dtype=bool)
    for airport in dico_airports:
        (xmin, ymin, xmax, ymax) = dico_airports[airport]["boundary"].bounds
        x_shift = 1500 * GEO.m_to_lon(tile.lat)
        y_shift = 1500 * GEO.m_to_lat
        colmin = max(round((xmin - x_shift) * 1000), 0)
        colmax = min(round((xmax + x_shift) * 1000), 1000)
        rowmax = min(round(((1 - ymin) + y_shift) * 1000), 1000)
        rowmin = max(round(((1 - ymax) - y_shift) * 1000), 0)
        airport_array[rowmin : rowmax + 1, colmin : colmax + 1] = True
    return airport_array


def smooth_raster_over_airports(tile, dico_airports, preserve_boundary=True):
    max_pix = tile.apt_smoothing_pix
    for airport in dico_airports:
        if "smoothing_pix" in dico_airports[airport]:
            try:
                max_pix = max(int(dico_airports[airport]["smoothing_pix"]), max_pix)
            except (TypeError, ValueError) as exc:
                UI.vprint(3, exc)
    if not max_pix:
        tile.dem.write_to_file(FNAMES.alt_file(tile))
        return
    if preserve_boundary:
        up = numpy.array(tile.dem.alt_dem[:max_pix])
        down = numpy.array(tile.dem.alt_dem[-max_pix:])
        left = numpy.array(tile.dem.alt_dem[:, :max_pix])
        right = numpy.array(tile.dem.alt_dem[:, -max_pix:])
    x0 = tile.dem.x0
    x1 = tile.dem.x1
    y0 = tile.dem.y0
    y1 = tile.dem.y1
    xstep = (x1 - x0) / tile.dem.nxdem
    ystep = (y1 - y0) / tile.dem.nydem
    upscale = max(ceil(ystep * GEO.lat_to_m / 10), 1)
    for airport in dico_airports:
        try:
            pix = (
                int(dico_airports[airport]["smoothing_pix"])
                if "smoothing_pix" in dico_airports[airport]
                else tile.apt_smoothing_pix
            )
        except (KeyError, TypeError, ValueError):
            pix = tile.apt_smoothing_pix
        if not pix:
            continue
        (xmin, ymin, xmax, ymax) = dico_airports[airport]["boundary"].bounds
        colmin = max(floor((xmin - x0) / xstep) - pix, 0)
        colmax = min(ceil((xmax - x0) / xstep) + pix, tile.dem.nxdem - 1)
        rowmin = max(floor((y1 - ymax) / ystep) - pix, 0)
        rowmax = min(ceil((y1 - ymin) / ystep) + pix, tile.dem.nydem - 1)
        if colmin >= colmax or rowmin >= rowmax:
            continue
        X0 = x0 + colmin * xstep
        Y1 = y1 - rowmin * ystep
        airport_im = Image.new(
            "L",
            (upscale * (colmax - colmin + 1), upscale * (rowmax - rowmin + 1)),
        )
        airport_draw = ImageDraw.Draw(airport_im)
        full_area = VECT.ensure_MultiPolygon(
            ops.unary_union(
                [
                    dico_airports[airport]["boundary"],
                    dico_airports[airport]["runway"][0],
                    dico_airports[airport]["hangar"],
                    dico_airports[airport]["taxiway"][0],
                    dico_airports[airport]["apron"][0],
                ]
            )
        )
        for polygon in full_area.geoms:
            exterior_pol_pix = [
                (
                    round(upscale * (X - X0) / xstep),
                    round(upscale * (Y1 - Y) / ystep),
                )
                for (X, Y) in polygon.exterior.coords
            ]
            airport_draw.polygon(exterior_pol_pix, fill="white")
            for inner_ring in polygon.interiors:
                interior_pol_pix = [
                    (
                        round(upscale * (X - X0) / xstep),
                        round(upscale * (Y1 - Y) / ystep),
                    )
                    for (X, Y) in inner_ring.coords
                ]
                airport_draw.polygon(interior_pol_pix, fill="black")
        airport_im = airport_im.resize(
            (colmax - colmin + 1, rowmax - rowmin + 1), Image.Resampling.BICUBIC
        )
        tile.dem.alt_dem[rowmin : rowmax + 1, colmin : colmax + 1] = DEM.smoothen(
            tile.dem.alt_dem[rowmin : rowmax + 1, colmin : colmax + 1],
            pix,
            airport_im,
            preserve_boundary=False,
        )
    if preserve_boundary:
        pix = max_pix
        for i in range(pix):
            tile.dem.alt_dem[i] = (
                i / pix * tile.dem.alt_dem[i] + (pix - i) / pix * up[i]
            )
            tile.dem.alt_dem[-i - 1] = (
                i / pix * tile.dem.alt_dem[-i - 1] + (pix - i) / pix * down[-i - 1]
            )
        for i in range(pix):
            tile.dem.alt_dem[:, i] = (
                i / pix * tile.dem.alt_dem[:, i] + (pix - i) / pix * left[:, i]
            )
            tile.dem.alt_dem[:, -i - 1] = (
                i / pix * tile.dem.alt_dem[:, -i - 1]
                + (pix - i) / pix * right[:, -i - 1]
            )
    tile.dem.write_to_file(FNAMES.alt_file(tile))
    return
