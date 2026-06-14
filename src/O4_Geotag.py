import os
from math import atan, exp, pi

from osgeo import gdal
from pyproj import Transformer

geo_to_webm = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
gdal.UseExceptions()


def gtile_to_wgs84(til_x, til_y, zoomlevel):
    rat_x = til_x / (2 ** (zoomlevel - 1)) - 1
    rat_y = 1 - til_y / (2 ** (zoomlevel - 1))
    lon = rat_x * 180
    lat = 360 / pi * atan(exp(pi * rat_y)) - 90
    return (lat, lon)


def geotag_jpeg(file_name):
    items = file_name.split("_")
    til_y_top = int(items[0])
    til_x_left = int(items[1])
    zoomlevel = int(items[-1][-6:-4])
    (latmax, lonmin) = gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
    (latmin, lonmax) = gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
    (xmin, ymin) = geo_to_webm.transform(lonmin, latmin)
    (xmax, ymax) = geo_to_webm.transform(lonmax, latmax)
    tmp_tif = file_name.replace(".jpg", "_tmp.tif")
    out_tif = file_name.replace(".jpg", ".tif")
    gdal.Translate(
        tmp_tif,
        file_name,
        format="GTiff",
        creationOptions=["COMPRESS=JPEG"],
        outputBounds=[xmin, ymin, xmax, ymax],
        outputSRS="EPSG:3857",
    )
    gdal.Warp(
        out_tif,
        tmp_tif,
        format="GTiff",
        creationOptions=["COMPRESS=JPEG"],
        srcSRS="EPSG:3857",
        dstSRS="EPSG:4326",
        width=4096,
        height=4096,
        resampleAlg="bilinear",
    )
    os.remove(tmp_tif)


def main():
    for file_name in os.listdir():
        if file_name[-4:] == ".jpg":
            geotag_jpeg(file_name)


if __name__ == "__main__":
    main()
