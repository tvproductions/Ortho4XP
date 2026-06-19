"""GDAL memory dataset and /vsimem/ VRT helpers for texture assembly."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import numpy
from osgeo import gdal
from PIL import Image

gdal.UseExceptions()


@dataclass
class VsimemVRT:
    path: str
    dataset: object | None


def memory_dataset_from_image(image: Image.Image, bbox, epsg) -> object:
    supported = image if image.mode in ("L", "RGB", "RGBA") else image.convert("RGB")
    array = numpy.asarray(supported)
    bands = 1 if supported.mode == "L" else len(supported.getbands())
    dataset = gdal.GetDriverByName("MEM").Create(
        "",
        supported.width,
        supported.height,
        bands,
        gdal.GDT_Byte,
    )
    ulx, uly, lrx, lry = bbox
    dataset.SetGeoTransform(
        (
            ulx,
            (lrx - ulx) / supported.width,
            0,
            uly,
            0,
            (lry - uly) / supported.height,
        )
    )
    dataset.SetProjection(f"EPSG:{epsg}")
    if bands == 1:
        dataset.GetRasterBand(1).WriteArray(array)
    else:
        for band_index in range(bands):
            dataset.GetRasterBand(band_index + 1).WriteArray(array[:, :, band_index])
    return dataset


@contextmanager
def vsimem_vrt_from_sources(sources, vrt_name: str | None = None) -> Iterator[VsimemVRT]:
    name = vrt_name or uuid.uuid4().hex
    path = f"/vsimem/ortho4xp/{name}.vrt"
    dataset = gdal.BuildVRT(path, list(sources))
    if dataset is None:
        raise RuntimeError("GDAL BuildVRT failed")
    vrt = VsimemVRT(path, dataset)
    try:
        yield vrt
    finally:
        vrt.dataset = None
        dataset = None
        gdal.Unlink(path)


def image_from_dataset(dataset, mode: str) -> Image.Image:
    if mode == "L":
        return Image.fromarray(dataset.GetRasterBand(1).ReadAsArray(), "L")
    bands = [dataset.GetRasterBand(index + 1).ReadAsArray() for index in range(len(mode))]
    return Image.fromarray(numpy.dstack(bands), mode)


def warp_dataset_to_image(
    dataset,
    target_bbox,
    target_epsg,
    target_size,
    resampling,
    mode,
) -> Image.Image:
    ulx, uly, lrx, lry = target_bbox
    width, height = target_size
    warped = gdal.Warp(
        "",
        dataset,
        format="MEM",
        dstSRS=f"EPSG:{target_epsg}",
        outputBounds=[ulx, lry, lrx, uly],
        width=width,
        height=height,
        resampleAlg=resampling,
    )
    if warped is None:
        raise RuntimeError("GDAL warp failed")
    return image_from_dataset(warped, mode)
