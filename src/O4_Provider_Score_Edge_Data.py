"""Shared edge extraction helpers for provider scoring."""

from __future__ import annotations

import numpy

EDGE_NAMES = ("left", "right", "top", "bottom")


def named_edge_arrays(sample: numpy.ndarray, band: int) -> dict[str, numpy.ndarray]:
    return {
        "left": sample[:, :band, :],
        "right": sample[:, -band:, :],
        "top": sample[:band, :, :],
        "bottom": sample[-band:, :, :],
    }


def edge_arrays(sample: numpy.ndarray, band: int) -> list[numpy.ndarray]:
    return list(named_edge_arrays(sample, band).values())


def border_pairs(
    sample: numpy.ndarray, band: int
) -> dict[str, tuple[numpy.ndarray, numpy.ndarray]]:
    height, width = sample.shape[:2]
    pairs: dict[str, tuple[numpy.ndarray, numpy.ndarray]] = {}
    if width > band:
        pairs["left"] = (sample[:, band, :], sample[:, band - 1, :])
        pairs["right"] = (
            sample[:, width - band, :],
            sample[:, width - band - 1, :],
        )
    if height > band:
        pairs["top"] = (sample[band, :, :], sample[band - 1, :, :])
        pairs["bottom"] = (
            sample[height - band, :, :],
            sample[height - band - 1, :, :],
        )
    return pairs
