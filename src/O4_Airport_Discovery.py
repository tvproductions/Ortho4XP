import numpy
from shapely import geometry, ops
from shapely.errors import GEOSException

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_UI_Utils as UI
import O4_Vector_Utils as VECT


def discover_airport_names(airport_layer, dico_airports):
    for osmtype in ("r", "w", "n"):
        for osmid in (
            x
            for x in airport_layer.dicosmtags[osmtype]
            if "aerodrome" in airport_layer.dicosmtags[osmtype][x].values()
            or "airstrip" in airport_layer.dicosmtags[osmtype][x].values()
        ):
            key = None
            if "icao" in airport_layer.dicosmtags[osmtype][osmid]:
                key = airport_layer.dicosmtags[osmtype][osmid]["icao"][:4]
                if key in dico_airports:
                    continue
                dico_airports[key] = {"key_type": "icao"}
            elif "iata" in airport_layer.dicosmtags[osmtype][osmid]:
                key = airport_layer.dicosmtags[osmtype][osmid]["iata"][:3]
                if key in dico_airports:
                    continue
                dico_airports[key] = {"key_type": "iata"}
            elif "local_ref" in airport_layer.dicosmtags[osmtype][osmid]:
                key = airport_layer.dicosmtags[osmtype][osmid]["local_ref"]
                if key in dico_airports:
                    continue
                dico_airports[key] = {"key_type": "local_ref"}
            if "name:en" in airport_layer.dicosmtags[osmtype][osmid]:
                name = (
                    airport_layer.dicosmtags[osmtype][osmid]["name:en"]
                    .replace("&quot;", '"')
                    .replace("&apos;", "'")
                )
            elif "name:alt" in airport_layer.dicosmtags[osmtype][osmid]:
                name = (
                    airport_layer.dicosmtags[osmtype][osmid]["name:alt"]
                    .replace("&quot;", '"')
                    .replace("&apos;", "'")
                )
            elif "name" in airport_layer.dicosmtags[osmtype][osmid]:
                name = (
                    airport_layer.dicosmtags[osmtype][osmid]["name"]
                    .replace("&quot;", '"')
                    .replace("&apos;", "'")
                )
            else:
                name = "****"
            if len(name) >= 60:
                name = name[:57] + "..."
            repr_node = (
                airport_layer.dicosmn[osmid]
                if osmtype == "n"
                else tuple(
                    numpy.mean(
                        numpy.array(
                            [
                                airport_layer.dicosmn[nodeid]
                                for nodeid in airport_layer.dicosmw[osmid]
                            ]
                        ),
                        axis=0,
                    )
                )
                if osmtype == "w"
                else tuple(
                    numpy.mean(
                        numpy.array(
                            [
                                airport_layer.dicosmn[nodeid]
                                for nodeid in airport_layer.dicosmr[osmid]["outer"][0]
                            ]
                        ),
                        axis=0,
                    )
                )
            )
            if not key:
                if name in dico_airports:
                    continue
                if name != "****":
                    key = name
                    dico_airports[key] = {"key_type": "name"}
                else:
                    key = repr_node
                    if key in dico_airports:
                        continue
                    dico_airports[key] = {"key_type": "repr_node"}
            dico_airports[key]["name"] = name
            dico_airports[key]["runway"] = []
            dico_airports[key]["runway_as_rel"] = []
            dico_airports[key]["taxiway"] = []
            dico_airports[key]["apron"] = []
            dico_airports[key]["hangar"] = []
            dico_airports[key]["repr_node"] = repr_node
            if "smoothing_pix" in airport_layer.dicosmtags[osmtype][osmid]:
                try:
                    dico_airports[key]["smoothing_pix"] = int(
                        airport_layer.dicosmtags[osmtype][osmid]["smoothing_pix"]
                    )
                except (TypeError, ValueError) as exc:
                    UI.vprint(3, exc)
            try:
                dico_airports[key]["boundary"] = (
                    geometry.Polygon(
                        numpy.array(
                            [
                                airport_layer.dicosmn[nodeid]
                                for nodeid in airport_layer.dicosmw[osmid]
                            ]
                        )
                    )
                    if osmtype == "w"
                    else ops.unary_union(
                        [
                            geometry.Polygon(
                                numpy.array(
                                    [
                                        airport_layer.dicosmn[nodeid]
                                        for nodeid in nodelist
                                    ]
                                )
                            )
                            for nodelist in airport_layer.dicosmr[osmid]["outer"]
                        ]
                    )
                    if osmtype == "r"
                    else None
                )
                if (
                    dico_airports[key]["boundary"]
                    and not dico_airports[key]["boundary"].is_valid
                ):
                    UI.lvprint(
                        2,
                        "Airport ",
                        dico_airports[key],
                        "OSM boundary is an invalid polygon, boundary set to ",
                        "None.",
                    )
                    dico_airports[key]["boundary"] = None
            except (KeyError, TypeError, ValueError, GEOSException):
                UI.lvprint(
                    2,
                    "WARNING:  A presumably erroneous tag marked aerodrome ",
                    "was found and skipped close to the point",
                    repr_node,
                    ".\n          You might wish to check and correct it ",
                    "online in OSM.",
                )
                dico_airports.pop(key, None)


def attach_surfaces_to_airports(airport_layer, dico_airports):
    for surface_type in ("runway", "taxiway", "apron", "hangar"):
        for wayid in (
            x
            for x in airport_layer.dicosmw
            if x in airport_layer.dicosmtags["w"]
            and "aeroway" in airport_layer.dicosmtags["w"][x]
            and airport_layer.dicosmtags["w"][x]["aeroway"] == surface_type
        ):
            linestring = geometry.LineString(
                numpy.array(
                    [
                        airport_layer.dicosmn[nodeid]
                        for nodeid in airport_layer.dicosmw[wayid]
                    ]
                )
            )
            found_apt = False
            for airport in (x for x in dico_airports if dico_airports[x]["boundary"]):
                if linestring.intersects(dico_airports[airport]["boundary"]):
                    dico_airports[airport][surface_type].append(wayid)
                    found_apt = True
                    break
            if found_apt:
                continue
            closest_dist = 99999
            closest_apt = None
            pt_check = tuple(
                numpy.mean(
                    numpy.array(
                        [
                            airport_layer.dicosmn[nodeid]
                            for nodeid in airport_layer.dicosmw[wayid]
                        ]
                    ),
                    axis=0,
                )
            )
            for airport in dico_airports:
                dist = GEO.dist(pt_check, dico_airports[airport]["repr_node"])
                if dist < closest_dist:
                    closest_dist = dist
                    closest_apt = airport
            if closest_apt and closest_dist < 3500:
                dico_airports[closest_apt][surface_type].append(wayid)
            else:
                try:
                    name = airport_layer.dicosmtags["w"][wayid]["name"]
                    dico_airports[name] = {
                        "key_type": "name",
                        "repr_node": pt_check,
                        "name": name,
                        "runway": [],
                        "runway_as_rel": [],
                        "taxiway": [],
                        "apron": [],
                        "hangar": [],
                        "boundary": None,
                    }
                    dico_airports[name][surface_type].append(wayid)
                except KeyError:
                    dico_airports[pt_check] = {
                        "key_type": "repr_node",
                        "repr_node": pt_check,
                        "name": "****",
                        "runway": [],
                        "runway_as_rel": [],
                        "taxiway": [],
                        "apron": [],
                        "hangar": [],
                        "boundary": None,
                    }
                    dico_airports[pt_check][surface_type].append(wayid)
    for relid in (
        x
        for x in airport_layer.dicosmr
        if x in airport_layer.dicosmtags["r"]
        and "aeroway" in airport_layer.dicosmtags["r"][x]
        and airport_layer.dicosmtags["r"][x]["aeroway"] == "runway"
    ):
        linestring = geometry.LineString(
            numpy.array(
                [
                    airport_layer.dicosmn[nodeid]
                    for nodeid in airport_layer.dicosmr[relid]["outer"][0]
                ]
            )
        )
        found_apt = False
        for airport in (x for x in dico_airports if dico_airports[x]["boundary"]):
            if linestring.intersects(dico_airports[airport]["boundary"]):
                dico_airports[airport]["runway_as_rel"].append(relid)
                found_apt = True
                break
        if found_apt:
            continue
        closest_dist = 99999
        closest_apt = None
        pt_check = tuple(
            numpy.mean(
                numpy.array(
                    [
                        airport_layer.dicosmn[nodeid]
                        for nodeid in airport_layer.dicosmr[relid]["outer"][0]
                    ]
                ),
                axis=0,
            )
        )
        for airport in dico_airports:
            dist = GEO.dist(pt_check, dico_airports[airport]["repr_node"])
            if dist < closest_dist:
                closest_dist = dist
                closest_apt = airport
        if closest_apt and closest_dist < 3500:
            dico_airports[closest_apt]["runway_as_rel"].append(relid)
        else:
            try:
                name = airport_layer.dicosmtags["r"][relid]["name"]
                dico_airports[name] = {
                    "key_type": "name",
                    "repr_node": pt_check,
                    "name": name,
                    "runway": [],
                    "runway_as_rel": [],
                    "taxiway": [],
                    "apron": [],
                    "hangar": [],
                    "boundary": None,
                }
                dico_airports[name]["runway_as_rel"].append(relid)
            except KeyError:
                dico_airports[pt_check] = {
                    "key_type": "repr_node",
                    "repr_node": pt_check,
                    "name": "****",
                    "runway": [],
                    "runway_as_rel": [],
                    "taxiway": [],
                    "apron": [],
                    "hangar": [],
                    "boundary": None,
                }
                dico_airports[pt_check]["runway_as_rel"].append(relid)
    return


def sort_and_reconstruct_runways(tile, airport_layer, dico_airports):
    for airport in dico_airports:
        runways_as_area = []
        runways_as_line = []
        linear = []
        linear_width = []
        for wayid in dico_airports[airport]["runway"]:
            if airport_layer.dicosmw[wayid][0] == airport_layer.dicosmw[wayid][-1]:
                runway_pol = geometry.Polygon(
                    numpy.round(
                        numpy.array(
                            [
                                airport_layer.dicosmn[nodeid]
                                for nodeid in airport_layer.dicosmw[wayid]
                            ]
                        )
                        - numpy.array([tile.lon, tile.lat]),
                        7,
                    )
                )
                if not runway_pol.is_empty and runway_pol.is_valid:
                    if runway_pol.area < 1e-7:
                        continue
                    runway_pol_rect = VECT.min_bounding_rectangle(runway_pol)
                    if (
                        wayid not in airport_layer.dicosmtags["w"]
                        or "custom" not in airport_layer.dicosmtags["w"][wayid]
                    ):
                        discrep = runway_pol_rect.hausdorff_distance(runway_pol)
                        if discrep > 0.0008:
                            UI.logprint(
                                "Bad runway (geometry too far from a ",
                                "rectangle) close to",
                                airport,
                                "at",
                                dico_airports[airport]["repr_node"],
                            )
                            UI.vprint(
                                1,
                                "   !Bad runway (geometry too far from a ",
                                "rectangle) close to",
                                airport,
                                "at",
                                dico_airports[airport]["repr_node"],
                            )
                            UI.vprint(
                                1,
                                "   !You may correct it editing the file ",
                                FNAMES.osm_cached(tile.lat, tile.lon, "airports"),
                                "in JOSM.",
                            )
                            continue
                    rectangle = numpy.array(
                        VECT.min_bounding_rectangle(runway_pol).exterior.coords
                    )
                    if VECT.length_in_meters(rectangle[0:2]) < VECT.length_in_meters(
                        rectangle[1:3]
                    ):
                        runway_start = (rectangle[0] + rectangle[1]) / 2
                        runway_end = (rectangle[2] + rectangle[3]) / 2
                        runway_width = VECT.length_in_meters(rectangle[0:2])
                    else:
                        runway_start = (rectangle[1] + rectangle[2]) / 2
                        runway_end = (rectangle[0] + rectangle[3]) / 2
                        runway_width = VECT.length_in_meters(rectangle[1:3])
                    runways_as_area.append(
                        (runway_pol, runway_start, runway_end, runway_width)
                    )
                else:
                    UI.logprint(
                        1,
                        "Bad runway (geometry invalid or going back over ",
                        "itself) close to",
                        airport,
                        "at",
                        dico_airports[airport]["repr_node"],
                    )
                    UI.vprint(
                        1,
                        "   !Bad runway (geometry invalid or going back over ",
                        "itself) close to",
                        airport,
                        "at",
                        dico_airports[airport]["repr_node"],
                    )
                    UI.vprint(
                        1,
                        "   !You may correct it editing the file ",
                        FNAMES.osm_cached(tile.lat, tile.lon, "airports"),
                        "in JOSM.",
                    )
                    continue
            else:
                linear.append(airport_layer.dicosmw[wayid])
                try:
                    linear_width.append(
                        float(airport_layer.dicosmtags["w"][wayid]["width"])
                    )
                except (KeyError, TypeError, ValueError):
                    linear_width.append(0)
        for relid in dico_airports[airport]["runway_as_rel"]:
            runway_pol = geometry.Polygon(
                numpy.round(
                    numpy.array(
                        [
                            airport_layer.dicosmn[nodeid]
                            for nodeid in airport_layer.dicosmr[relid]["outer"][0]
                        ]
                    )
                    - numpy.array([tile.lon, tile.lat]),
                    7,
                )
            )
            if not runway_pol.is_empty and runway_pol.is_valid:
                if runway_pol.area < 1e-7:
                    continue
                runway_pol_rect = VECT.min_bounding_rectangle(runway_pol)
                if (
                    relid not in airport_layer.dicosmtags["r"]
                    or "custom" not in airport_layer.dicosmtags["r"][relid]
                ):
                    discrep = runway_pol_rect.hausdorff_distance(runway_pol)
                    if discrep > 0.0008:
                        UI.logprint(
                            "Bad runway (geometry too far from a rectangle) ",
                            "close to",
                            airport,
                            "at",
                            dico_airports[airport]["repr_node"],
                        )
                        UI.vprint(
                            1,
                            "   !Bad runway (geometry too far from a ",
                            "rectangle) close to",
                            airport,
                            "at",
                            dico_airports[airport]["repr_node"],
                        )
                        UI.vprint(
                            1,
                            "   !You may correct it editing the file ",
                            FNAMES.osm_cached(tile.lat, tile.lon, "airports"),
                            "in JOSM.",
                        )
                        continue
                rectangle = numpy.array(
                    VECT.min_bounding_rectangle(runway_pol).exterior.coords
                )
                if VECT.length_in_meters(rectangle[0:2]) < VECT.length_in_meters(
                    rectangle[1:3]
                ):
                    runway_start = (rectangle[0] + rectangle[1]) / 2
                    runway_end = (rectangle[2] + rectangle[3]) / 2
                    runway_width = VECT.length_in_meters(rectangle[0:2])
                else:
                    runway_start = (rectangle[1] + rectangle[2]) / 2
                    runway_end = (rectangle[0] + rectangle[3]) / 2
                    runway_width = VECT.length_in_meters(rectangle[1:3])
                runways_as_area.append(
                    (runway_pol, runway_start, runway_end, runway_width)
                )
            else:
                UI.logprint(
                    1,
                    "Bad runway (geometry invalid or going back over itself) ",
                    "close to",
                    airport,
                    "at",
                    dico_airports[airport]["repr_node"],
                )
                UI.vprint(
                    1,
                    "   !Bad runway (geometry invalid or going back over ",
                    "itself) close to",
                    airport,
                    "at",
                    dico_airports[airport]["repr_node"],
                )
                UI.vprint(
                    1,
                    "   !You may correct it editing the file ",
                    FNAMES.osm_cached(tile.lat, tile.lon, "airports"),
                    "in JOSM.",
                )
                continue
        from math import pi

        runway_parts_are_grouped = False
        while not runway_parts_are_grouped:
            runway_parts_are_grouped = True
            for i in range(len(linear) - 1):
                dir_i = numpy.arctan2(
                    *(
                        numpy.array(airport_layer.dicosmn[linear[i][-1]])
                        - numpy.array(airport_layer.dicosmn[linear[i][0]])
                    )
                )
                for j in range(i + 1, len(linear)):
                    dir_j = numpy.arctan2(
                        *(
                            numpy.array(airport_layer.dicosmn[linear[j][-1]])
                            - numpy.array(airport_layer.dicosmn[linear[j][0]])
                        )
                    )
                    if (
                        not numpy.min(
                            numpy.abs(
                                numpy.array([-2 * pi, -pi, 0, pi, 2 * pi])
                                - (dir_i - dir_j)
                            )
                        )
                        < 0.2
                    ):
                        continue
                    if linear[i][-1] == linear[j][0]:
                        linear = [
                            linear[k] for k in range(len(linear)) if k not in (i, j)
                        ] + [linear[i] + linear[j][1:]]
                        linear_width = [
                            linear_width[k]
                            for k in range(len(linear_width))
                            if k not in (i, j)
                        ] + [max(linear_width[i], linear_width[j])]
                        runway_parts_are_grouped = False
                        break
                    elif linear[i][-1] == linear[j][-1]:
                        linear = [
                            linear[k] for k in range(len(linear)) if k not in (i, j)
                        ] + [linear[i] + linear[j][-2::-1]]
                        linear_width = [
                            linear_width[k]
                            for k in range(len(linear_width))
                            if k not in (i, j)
                        ] + [max(linear_width[i], linear_width[j])]
                        runway_parts_are_grouped = False
                        break
                    elif linear[i][0] == linear[j][0]:
                        linear = [
                            linear[k] for k in range(len(linear)) if k not in (i, j)
                        ] + [linear[i][-1::-1] + linear[j][1:]]
                        linear_width = [
                            linear_width[k]
                            for k in range(len(linear_width))
                            if k not in (i, j)
                        ] + [max(linear_width[i], linear_width[j])]
                        runway_parts_are_grouped = False
                        break
                    elif linear[i][0] == linear[j][-1]:
                        linear = [
                            linear[k] for k in range(len(linear)) if k not in (i, j)
                        ] + [linear[j] + linear[i][1:]]
                        linear_width = [
                            linear_width[k]
                            for k in range(len(linear_width))
                            if k not in (i, j)
                        ] + [max(linear_width[i], linear_width[j])]
                        runway_parts_are_grouped = False
                        break
                if not runway_parts_are_grouped:
                    break
        for nodeid_list, width in zip(linear, linear_width, strict=False):
            runway_start = airport_layer.dicosmn[nodeid_list[0]]
            runway_end = airport_layer.dicosmn[nodeid_list[-1]]
            runway_length = GEO.dist(runway_start, runway_end)
            runway_start = numpy.round(
                numpy.array(runway_start) - numpy.array([tile.lon, tile.lat]), 7
            )
            runway_end = numpy.round(
                numpy.array(runway_end) - numpy.array([tile.lon, tile.lat]), 7
            )
            if width:
                width += 10
            else:
                width = 30 + runway_length // 1000
            pol = geometry.Polygon(
                VECT.buffer_simple_way(numpy.vstack((runway_start, runway_end)), width)
            )
            keep_this = True
            for i, pol2 in enumerate(runways_as_area):
                if (pol2[0].intersection(pol)).area > 0.6 * min(pol.area, pol2[0].area):
                    runways_as_area[i] = (
                        pol2[0],
                        runway_start,
                        runway_end,
                        width,
                    )
                    keep_this = False
                    break
            if keep_this:
                runways_as_line.append((pol, runway_start, runway_end, width))
        runway_area = VECT.ensure_MultiPolygon(
            ops.unary_union([item[0] for item in runways_as_area + runways_as_line])
        )
        dico_airports[airport]["runway"] = (
            runway_area,
            runways_as_area,
            runways_as_line,
        )
    return


def discard_unwanted_airports(tile, dico_airports):
    for airport in list(dico_airports.keys()):
        apt = dico_airports[airport]
        if apt["boundary"]:
            if apt["boundary"].area < 5000 * GEO.m_to_lat * GEO.m_to_lon(tile.lat):
                dico_airports.pop(airport, None)
            continue
        if apt["runway"][0].area < 2500 * GEO.m_to_lat * GEO.m_to_lon(tile.lat):
            dico_airports.pop(airport, None)
            continue


def list_airports_and_runways(dico_airports):
    airport_list = (
        sorted([x for x in dico_airports if dico_airports[x]["key_type"] == "icao"])
        + sorted([x for x in dico_airports if dico_airports[x]["key_type"] == "iata"])
        + sorted(
            [x for x in dico_airports if dico_airports[x]["key_type"] == "local_ref"]
        )
        + sorted([x for x in dico_airports if dico_airports[x]["key_type"] == "name"])
        + sorted(
            [x for x in dico_airports if dico_airports[x]["key_type"] == "repr_node"]
        )
    )
    for airport in airport_list:
        l = len(dico_airports[airport]["runway"][1]) + len(
            dico_airports[airport]["runway"][2]
        )
        runway_str = (
            str(l) + (" runways," if l > 1 else " runway ,") if l else "boundary ,"
        )
        if dico_airports[airport]["key_type"] in ("icao", "iata", "local_ref"):
            UI.vprint(
                1,
                "  ",
                f"{airport:6s}",
                "{:60s}".format(dico_airports[airport]["name"]),
                runway_str,
                "lat=",
                "{:.2f}".format(dico_airports[airport]["repr_node"][1]) + ",",
                "lon=",
                "{:.2f}".format(dico_airports[airport]["repr_node"][0]),
            )
        else:
            UI.vprint(
                1,
                "  ",
                "{:6s}".format("****"),
                "{:60s}".format(dico_airports[airport]["name"]),
                runway_str,
                "lat=",
                "{:.2f}".format(dico_airports[airport]["repr_node"][1]) + ",",
                "lon=",
                "{:.2f}".format(dico_airports[airport]["repr_node"][0]),
            )
    return
