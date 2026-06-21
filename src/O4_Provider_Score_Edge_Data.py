"""Shared edge extraction helpers for provider scoring."""

from __future__ import annotations

import numpy


def edge_arrays(sample: numpy.ndarray, band: int) -> list[numpy.ndarray]:
    return [
        sample[:, :band, :],
        sample[:, -band:, :],
        sample[:band, :, :],
        sample[-band:, :, :],
    ]
