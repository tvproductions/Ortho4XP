"""Shared seam-score stat helpers for provider scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy

from O4_Provider_Score_Sampling import luminance


@dataclass(frozen=True)
class InteriorStats:
    luma_mean: float
    rgb_mean: numpy.ndarray


@dataclass(frozen=True)
class EdgeInput:
    # Bundle per-edge inputs so seam helpers stay under the repo's lizard
    # parameter-count limit without changing any public scoring interface.
    border_pair: tuple[numpy.ndarray, numpy.ndarray] | None
    edge: numpy.ndarray
    edge_name: str


def interior_stats(interior: numpy.ndarray) -> InteriorStats:
    # Interior means anchor every seam comparison against the non-border region.
    return InteriorStats(
        luma_mean=float(numpy.mean(luminance(interior))),
        rgb_mean=rgb_mean(interior),
    )


def rgb_mean(edge: numpy.ndarray) -> numpy.ndarray:
    return edge.reshape(-1, 3).mean(axis=0)


def risk_score(
    luma_drift: float,
    rgb_drift: float,
    border_gradient: float,
    neighbor_drift: float,
) -> float:
    return max(
        0.0,
        luma_drift - 12.0,
        rgb_drift - 12.0,
        border_gradient - 18.0,
        neighbor_drift - 12.0,
    )


def neighbor_drift(
    edge: numpy.ndarray,
    edge_name: str,
    neighbor_edges: Any,
) -> float:
    # Neighbor comparisons are optional and must remain tolerant of partial or
    # malformed context payloads from callers.
    if not neighbor_edges or edge_name not in neighbor_edges:
        return 0.0
    neighbor = numpy.asarray(neighbor_edges[edge_name], dtype=numpy.float64)
    if neighbor.size == 0 or neighbor.ndim != 3 or neighbor.shape[2] < 3:
        return 0.0
    return float(numpy.mean(numpy.abs(rgb_mean(edge) - rgb_mean(neighbor[:, :, :3]))))


def empty_details(edge_names: tuple[str, ...]) -> dict[str, Any]:
    edges = {
        edge: {
            "risk": 0.0,
            "luminance_drift": 0.0,
            "rgb_drift": 0.0,
            "border_gradient": 0.0,
            "neighbor_drift": 0.0,
        }
        for edge in edge_names
    }
    return {"worst_edge": "left", "edges": edges, "neighbor_compared": False}
