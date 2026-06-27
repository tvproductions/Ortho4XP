"""Edge seam-risk metric for provider scoring."""

from __future__ import annotations

from typing import Any

import numpy

from O4_Provider_Score_Edge_Data import EDGE_NAMES, border_pairs, named_edge_arrays
from O4_Provider_Score_Models import ProviderScoreContext
from O4_Provider_Score_Sampling import luminance
from O4_Provider_Score_Seam_Stats import (
    EdgeInput,
    InteriorStats,
    empty_details,
    interior_stats,
    neighbor_drift,
    rgb_mean,
    risk_score,
)


def seam_risk_score(sample: numpy.ndarray) -> float:
    score, _details = seam_risk_score_details(sample)
    return score


def seam_risk_score_details(
    sample: numpy.ndarray,
    scoring_context: ProviderScoreContext | None = None,
) -> tuple[float, dict[str, Any]]:
    # Invalid or degenerate samples behave like zero-risk tiles.
    if sample.size == 0 or sample.ndim != 3 or sample.shape[2] < 3:
        return 0.0, empty_details(EDGE_NAMES)

    rgb = sample[:, :, :3].astype(numpy.float64)
    band = max(1, min(rgb.shape[0], rgb.shape[1]) // 16)
    interior = _interior(rgb, band)
    neighbor_edges = scoring_context.neighbor_edges if scoring_context else None
    edge_details = _edge_details(rgb, band, interior, neighbor_edges)
    worst_edge = max(edge_details, key=lambda edge: edge_details[edge]["risk"])
    score = float(edge_details[worst_edge]["risk"])
    return score, {
        "worst_edge": worst_edge,
        "edges": edge_details,
        "neighbor_compared": any(
            details["neighbor_drift"] > 0 for details in edge_details.values()
        ),
    }


def _edge_details(
    rgb: numpy.ndarray,
    band: int,
    interior: numpy.ndarray,
    neighbor_edges: Any,
) -> dict[str, dict[str, float]]:
    # The comparison baseline comes from the tile interior, while border pairs
    # isolate the immediate seam transition against the adjacent interior band.
    stats = interior_stats(interior)
    borders = border_pairs(rgb, band)
    return {
        edge_name: _edge_detail(
            EdgeInput(
                border_pair=borders.get(edge_name),
                edge=edge,
                edge_name=edge_name,
            ),
            stats,
            neighbor_edges,
        )
        for edge_name, edge in named_edge_arrays(rgb, band).items()
    }


def _interior(sample: numpy.ndarray, band: int) -> numpy.ndarray:
    # Very small samples fall back to the full image so every downstream mean
    # still has a stable, deterministic input array.
    interior = sample[band:-band, band:-band, :]
    if interior.size == 0:
        return sample
    return interior


def _edge_detail(
    edge_input: EdgeInput,
    interior_stats: InteriorStats,
    neighbor_edges: Any,
) -> dict[str, float]:
    # Risk is the strongest of the independent seam indicators for a single
    # edge: luminance drift, RGB drift, border discontinuity, or neighbor drift.
    edge_luma = luminance(edge_input.edge)
    luma_drift = abs(float(numpy.mean(edge_luma)) - interior_stats.luma_mean)
    rgb_drift = float(
        numpy.mean(numpy.abs(rgb_mean(edge_input.edge) - interior_stats.rgb_mean))
    )
    border_gradient = _border_gradient(edge_input.border_pair)
    edge_neighbor_drift = neighbor_drift(
        edge_input.edge, edge_input.edge_name, neighbor_edges
    )
    return {
        "risk": round(
            risk_score(luma_drift, rgb_drift, border_gradient, edge_neighbor_drift),
            2,
        ),
        "luminance_drift": round(luma_drift, 2),
        "rgb_drift": round(rgb_drift, 2),
        "border_gradient": round(border_gradient, 2),
        "neighbor_drift": round(edge_neighbor_drift, 2),
    }


def _border_gradient(border_pair: tuple[numpy.ndarray, numpy.ndarray] | None) -> float:
    # Some tiny inputs have no interior-adjacent border band; treat those as a
    # zero-gradient edge instead of special-casing them in the caller.
    if border_pair is None:
        return 0.0
    outer_band, inner_band = border_pair
    return float(numpy.mean(numpy.abs(outer_band - inner_band)))
