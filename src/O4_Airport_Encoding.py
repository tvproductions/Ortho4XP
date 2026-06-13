from math import pi, cos, sin
import numpy
from shapely import geometry, ops
from shapely.errors import GEOSException
from rtree import index
import O4_UI_Utils as UI
import O4_Vector_Utils as VECT
import O4_Geo_Utils as GEO

runway_chunks = 100
chunk_min_size = 10


def encode_runways_taxiways_and_aprons(
    tile, airport_layer, dico_airports, vector_map, patches_list
):
    seeds = {"RUNWAY": [], "TAXIWAY": [], "APRON": []}
    total_rwy = 0
    total_taxi = 0
    for airport in dico_airports:
        if airport in patches_list:
            continue
        apt = dico_airports[airport]
        total_rwy += len(apt["runway"][1] + apt["runway"][2])
        total_taxi += len(apt["taxiway"][1])
        alt_idx = index.Index()
        alt_dico = {}
        id = 0
        for runway_pol, runway_start, runway_end, runway_width in (
            apt["runway"][1] + apt["runway"][2]
        ):
            center_way = numpy.vstack((runway_start, runway_end))
            runway_length = VECT.length_in_meters(center_way)
            steps = int(max(runway_chunks, runway_length // 7))
            (linestring, polyfit) = VECT.least_square_fit_altitude_along_way(
                center_way, steps, tile.dem, weights=True
            )
            alt_idx.insert(id, linestring.bounds)
            alt_dico[id] = (linestring, polyfit, runway_width)
            id += 1
        for wayid in apt["taxiway"][1]:
            taxiway = numpy.array(
                [
                    airport_layer.dicosmn[nodeid]
                    for nodeid in airport_layer.dicosmw[wayid]
                ]
            ) - numpy.array([[tile.lon, tile.lat]])
            taxiway_length = VECT.length_in_meters(taxiway)
            steps = int(max(runway_chunks, taxiway_length // 7))
            (linestring, polyfit) = VECT.least_square_fit_altitude_along_way(
                taxiway, steps, tile.dem
            )
            alt_idx.insert(id, linestring.bounds)
            alt_dico[id] = (linestring, polyfit, 15)
            id += 1
        pols = []
        for (
            runway_pol,
            runway_start,
            runway_end,
            runway_width,
        ) in []:
            runway_length = VECT.length_in_meters(
                numpy.vstack((runway_start, runway_end))
            )
            refine_size = max(runway_length // runway_chunks, chunk_min_size)
            for pol in VECT.ensure_MultiPolygon(VECT.cut_to_tile(runway_pol)):
                way = numpy.round(
                    VECT.refine_way(numpy.array(pol.exterior.coords), refine_size),
                    7,
                )
                alti_way = numpy.array(
                    [
                        VECT.weighted_alt(node, alt_idx, alt_dico, tile.dem)
                        for node in way
                    ]
                ).reshape((len(way), 1))
                vector_map.insert_way(
                    numpy.hstack([way, alti_way]), "RUNWAY", check=True
                )
                pols.append(pol)
            way = VECT.refine_way(numpy.vstack((runway_start, runway_end)), refine_size)
            way_r = VECT.shift_way(way, 0.6 * runway_width, "right")
            way_l = VECT.shift_way(way, 0.6 * runway_width, "left")
            for k in range(1, len(way)):
                try:
                    lin = geometry.LineString([way_r[k], way_l[k]]).intersection(
                        runway_pol
                    )
                    if lin.geom_type == "LineString" and not lin.is_empty:
                        trav = numpy.round(numpy.array(lin), 7)
                        alti_trav = numpy.array(
                            [
                                VECT.weighted_alt(node, alt_idx, alt_dico, tile.dem)
                                for node in trav
                            ]
                        ).reshape((len(trav), 1))
                        vector_map.insert_way(
                            numpy.hstack([trav, alti_trav]), "DUMMY", check=True
                        )
                except (KeyError, TypeError, ValueError, GEOSException) as e:
                    UI.vprint(3, e)
        for runway_pol, runway_start, runway_end, runway_width in (
            apt["runway"][1] + apt["runway"][2]
        ):
            runway_length = VECT.length_in_meters(
                numpy.vstack((runway_start, runway_end))
            )
            refine_size = max(runway_length // runway_chunks, chunk_min_size)
            way = VECT.refine_way(numpy.vstack((runway_start, runway_end)), refine_size)
            way_r = VECT.shift_way(way, runway_width, "right")
            way_l = VECT.shift_way(way, runway_width, "left")
            for pol in VECT.ensure_MultiPolygon(VECT.cut_to_tile(runway_pol)).geoms:
                boundary = pol.exterior
                abscissae = [
                    boundary.project(geometry.Point(x)) for x in boundary.coords
                ]
                traverses = []
                for k in range(1, len(way)):
                    try:
                        lin = geometry.LineString([way_r[k], way_l[k]]).intersection(
                            runway_pol
                        )
                        if lin.geom_type == "LineString":
                            abs1 = boundary.project(geometry.Point(lin.coords[0]))
                            abs2 = boundary.project(geometry.Point(lin.coords[-1]))
                            traverses.append((abs1, abs2))
                            abscissae += [abs1, abs2]
                    except (TypeError, ValueError, GEOSException) as exc:
                        UI.vprint(3, exc)
                abscissae = sorted(set(abscissae))
                way = numpy.round(
                    numpy.array(
                        [boundary.interpolate(x).coords[0] for x in abscissae + [0]]
                    ),
                    7,
                )
                alti_way = numpy.array(
                    [
                        VECT.weighted_alt(node, alt_idx, alt_dico, tile.dem)
                        for node in way
                    ]
                ).reshape((len(way), 1))
                vector_map.insert_way(
                    numpy.hstack([way, alti_way]), "RUNWAY", check=True
                )
                for abs1, abs2 in traverses:
                    trav = numpy.round(
                        numpy.array(
                            [
                                boundary.interpolate(abs1).coords[0],
                                boundary.interpolate(abs2).coords[0],
                            ]
                        ),
                        7,
                    )
                    alti_trav = numpy.array(
                        [
                            VECT.weighted_alt(node, alt_idx, alt_dico, tile.dem)
                            for node in trav
                        ]
                    ).reshape((len(trav), 1))
                    vector_map.insert_way(
                        numpy.hstack([trav, alti_trav]), "DUMMY", check=True
                    )
                pols.append(pol)
        for pol in pols:
            for subpol in VECT.ensure_MultiPolygon(
                pol.difference(ops.unary_union([pol2 for pol2 in pols if pol2 != pol]))
            ).geoms:
                seeds["RUNWAY"].append(
                    numpy.array(subpol.representative_point().coords[0])
                )
            for subpol in VECT.ensure_MultiPolygon(
                pol.intersection(
                    ops.unary_union([pol2 for pol2 in pols if pol2 != pol])
                )
            ).geoms:
                seeds["RUNWAY"].append(
                    numpy.array(subpol.representative_point().coords[0])
                )
        cleaned_taxiway_area = VECT.improved_buffer(
            apt["taxiway"][0].difference(
                VECT.improved_buffer(apt["runway"][0], 5, 0, 0).union(
                    VECT.improved_buffer(apt["hangar"], 20, 0, 0)
                )
            ),
            3,
            2,
            0.5,
        )
        apt["taxiway"] = (cleaned_taxiway_area, apt["taxiway"][1])
        for pol in VECT.ensure_MultiPolygon(
            VECT.cut_to_tile(cleaned_taxiway_area)
        ).geoms:
            if not pol.is_valid or pol.is_empty or pol.area < 1e-9:
                continue
            way = numpy.round(VECT.refine_way(numpy.array(pol.exterior.coords), 20), 7)
            alti_way = numpy.array(
                [VECT.weighted_alt(node, alt_idx, alt_dico, tile.dem) for node in way]
            ).reshape((len(way), 1))
            vector_map.insert_way(numpy.hstack([way, alti_way]), "TAXIWAY", check=True)
            for subpol in pol.interiors:
                way = numpy.round(VECT.refine_way(numpy.array(subpol.coords), 20), 7)
                alti_way = numpy.array(
                    [
                        VECT.weighted_alt(node, alt_idx, alt_dico, tile.dem)
                        for node in way
                    ]
                ).reshape((len(way), 1))
                vector_map.insert_way(
                    numpy.hstack([way, alti_way]), "TAXIWAY", check=True
                )
            seeds["TAXIWAY"].append(numpy.array(pol.representative_point().coords[0]))
        for wayid in apt["apron"][1]:
            if (
                wayid not in airport_layer.dicosmtags["w"]
                or "include" not in airport_layer.dicosmtags["w"][wayid]
            ):
                continue
            try:
                way = numpy.round(
                    numpy.array(
                        [
                            airport_layer.dicosmn[nodeid]
                            for nodeid in airport_layer.dicosmw[wayid]
                        ]
                    )
                    - numpy.array([tile.lon, tile.lat]),
                    7,
                )
                way = numpy.round(VECT.refine_way(way, 15), 7)
                apron_pol = geometry.Polygon(way)
                if not apron_pol.is_empty and runway_pol.is_valid:
                    alti_way = numpy.array(
                        [
                            VECT.weighted_alt(node, alt_idx, alt_dico, tile.dem)
                            for node in way
                        ]
                    ).reshape((len(way), 1))
                    vector_map.insert_way(
                        numpy.hstack([way, alti_way]), "APRON", check=True
                    )
                    seeds["APRON"].append(
                        numpy.array(apron_pol.representative_point().coords[0])
                    )
            except (TypeError, ValueError, GEOSException) as exc:
                UI.vprint(3, exc)
    for surface in ("RUNWAY", "TAXIWAY", "APRON"):
        if seeds[surface]:
            if surface in vector_map.seeds:
                vector_map.seeds[surface] += seeds[surface]
            else:
                vector_map.seeds[surface] = seeds[surface]
    plural_rwy = "s" if total_rwy > 1 else ""
    plural_taxi = "s" if total_taxi > 1 else ""
    UI.vprint(
        1,
        "   Auto-patched",
        total_rwy,
        "runway" + plural_rwy + " and",
        total_taxi,
        "piece" + plural_taxi + " of taxiway.",
    )
    return ops.unary_union(
        [dico_airports[airport]["runway"][0] for airport in dico_airports]
        + [dico_airports[airport]["taxiway"][0] for airport in dico_airports]
        + [dico_airports[airport]["apron"][0] for airport in dico_airports]
    )


def encode_hangars(tile, dico_airports, vector_map, patches_list):
    seeds = []
    for airport in dico_airports:
        if airport in patches_list:
            continue
        for pol in VECT.ensure_MultiPolygon(
            VECT.cut_to_tile(dico_airports[airport]["hangar"])
        ).geoms:
            way = numpy.array(pol.exterior.coords)
            alt = tile.dem.alt_vec(way)
            if alt.max() - alt.min() <= 1.5:
                alti_way = numpy.ones((len(way), 1)) * numpy.mean(tile.dem.alt_vec(way))
                vector_map.insert_way(
                    numpy.hstack([way, alti_way]), "HANGAR", check=True
                )
                seeds.append(numpy.array(pol.representative_point().coords[0]))
    if seeds:
        if "HANGAR" in vector_map.seeds:
            vector_map.seeds["HANGAR"] += seeds
        else:
            vector_map.seeds["HANGAR"] = seeds
    return 1


def flatten_helipads(airport_layer, vector_map, tile, treated_area):
    multipol = []
    seeds = []
    total = 0
    for wayid in (
        x
        for x in airport_layer.dicosmw
        if x in airport_layer.dicosmtags["w"]
        and "aeroway" in airport_layer.dicosmtags["w"][x]
        and airport_layer.dicosmtags["w"][x]["aeroway"] == "helipad"
    ):
        if airport_layer.dicosmw[wayid][0] != airport_layer.dicosmw[wayid][-1]:
            continue
        way = numpy.round(
            numpy.array(
                [
                    airport_layer.dicosmn[nodeid]
                    for nodeid in airport_layer.dicosmw[wayid]
                ]
            )
            - numpy.array([[tile.lon, tile.lat]]),
            7,
        )
        pol = geometry.Polygon(way)
        if (
            (pol.is_empty)
            or (not pol.is_valid)
            or (not pol.area)
            or (pol.intersects(treated_area))
        ):
            continue
        multipol.append(pol)
        total += 1
    helipad_area = ops.unary_union(multipol)
    for nodeid in (
        x
        for x in airport_layer.dicosmn
        if x in airport_layer.dicosmtags["n"]
        and "aeroway" in airport_layer.dicosmtags["n"][x]
        and airport_layer.dicosmtags["n"][x]["aeroway"] == "helipad"
    ):
        center = numpy.round(
            numpy.array(airport_layer.dicosmn[nodeid])
            - numpy.array([tile.lon, tile.lat]),
            7,
        )
        if geometry.Point(center).intersects(helipad_area) or geometry.Point(
            center
        ).intersects(treated_area):
            continue
        way = numpy.round(
            center
            + numpy.array(
                [
                    [
                        cos(k * pi / 3) * 9 * GEO.m_to_lon(tile.lat),
                        sin(k * pi / 3) * 9 * GEO.m_to_lat,
                    ]
                    for k in range(7)
                ]
            ),
            7,
        )
        pol = geometry.Polygon(way)
        multipol.append(pol)
        total += 1
    helipad_area = VECT.ensure_MultiPolygon(VECT.cut_to_tile(ops.unary_union(multipol)))
    for pol in helipad_area.geoms:
        if (pol.is_empty) or (not pol.is_valid) or (not pol.area):
            continue
        way = numpy.array(pol.exterior.coords)
        alti_way = numpy.ones((len(way), 1)) * numpy.mean(tile.dem.alt_vec(way))
        vector_map.insert_way(numpy.hstack([way, alti_way]), "INTERP_ALT", check=True)
        seeds.append(numpy.array(pol.representative_point().coords[0]))
    if seeds:
        if "INTERP_ALT" in vector_map.seeds:
            vector_map.seeds["INTERP_ALT"] += seeds
        else:
            vector_map.seeds["INTERP_ALT"] = seeds
    if total:
        UI.vprint(1, "   Flattened", total, "helipads.")
