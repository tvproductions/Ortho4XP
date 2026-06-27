"""Edge seam-risk metric for provider scoring."""

from __future__ import annotations

from typing import Any

import numpy

from O4_Provider_Score_Models import ProviderScoreContext
from O4_Provider_Score_Sampling import luminance

EDGE_NAMES = ("left", "right", "top", "bottom")


def seam_risk_score(sample: numpy.ndarray) -> float:
    score, _details = seam_risk_score_details(sample)
    return score


def seam_risk_score_details(
    sample: numpy.ndarray,
    scoring_context: ProviderScoreContext | None = None,
) -> tuple[float, dict[str, Any]]:
    if sample.size == 0 or sample.ndim != 3 or sample.shape[2] < 3:
        return 0.0, _empty_details()

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
    interior_luma_mean = float(numpy.mean(luminance(interior)))
    interior_rgb_mean = _rgb_mean(interior)
    return {
        edge_name: _edge_detail(
            rgb,
            edge_name,
            edge,
            band,
            interior_luma_mean,
            interior_rgb_mean,
            neighbor_edges,
        )
        for edge_name, edge in _edge_arrays(rgb, band).items()
    }


def _edge_arrays(sample: numpy.ndarray, band: int) -> dict[str, numpy.ndarray]:
    return {
        "left": sample[:, :band, :],
        "right": sample[:, -band:, :],
        "top": sample[:band, :, :],
        "bottom": sample[-band:, :, :],
    }


def _interior(sample: numpy.ndarray, band: int) -> numpy.ndarray:
    interior = sample[band:-band, band:-band, :]
    if interior.size == 0:
        return sample
    return interior


def _edge_detail(
    sample: numpy.ndarray,
    edge_name: str,
    edge: numpy.ndarray,
    band: int,
    interior_luma_mean: float,
    interior_rgb_mean: numpy.ndarray,
    neighbor_edges: Any,
) -> dict[str, float]:
    edge_luma = luminance(edge)
    luma_drift = abs(float(numpy.mean(edge_luma)) - interior_luma_mean)
    rgb_drift = float(numpy.mean(numpy.abs(_rgb_mean(edge) - interior_rgb_mean)))
    border_gradient = _border_gradient(sample, edge_name, band)
    neighbor_drift = _neighbor_drift(edge, edge_name, neighbor_edges)
    return {
        "risk": round(
            _risk_score(luma_drift, rgb_drift, border_gradient, neighbor_drift),
            2,
        ),
        "luminance_drift": round(luma_drift, 2),
        "rgb_drift": round(rgb_drift, 2),
        "border_gradient": round(border_gradient, 2),
        "neighbor_drift": round(neighbor_drift, 2),
    }


def _rgb_mean(edge: numpy.ndarray) -> numpy.ndarray:
    return edge.reshape(-1, 3).mean(axis=0)


def _risk_score(
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


def _border_gradient(sample: numpy.ndarray, edge_name: str, band: int) -> float:
    border_pair = _border_pair(sample, edge_name, band)
    if border_pair is None:
        return 0.0
    outer_band, inner_band = border_pair
    return float(numpy.mean(numpy.abs(outer_band - inner_band)))


def _border_pair(
    sample: numpy.ndarray,
    edge_name: str,
    band: int,
) -> tuple[numpy.ndarray, numpy.ndarray] | None:
    height, width = sample.shape[:2]
    if edge_name == "left" and width > band:
        return sample[:, band, :], sample[:, band - 1, :]
    if edge_name == "right" and width > band:
        return sample[:, width - band, :], sample[:, width - band - 1, :]
    if edge_name == "top" and height > band:
        return sample[band, :, :], sample[band - 1, :, :]
    if edge_name == "bottom" and height > band:
        return sample[height - band, :, :], sample[height - band - 1, :, :]
    return None


def _neighbor_drift(
    edge: numpy.ndarray,
    edge_name: str,
    neighbor_edges: Any,
) -> float:
    if not neighbor_edges or edge_name not in neighbor_edges:
        return 0.0
    neighbor = numpy.asarray(neighbor_edges[edge_name], dtype=numpy.float64)
    if neighbor.size == 0 or neighbor.ndim != 3 or neighbor.shape[2] < 3:
        return 0.0
    return float(numpy.mean(numpy.abs(_rgb_mean(edge) - _rgb_mean(neighbor[:, :, :3]))))


def _empty_details() -> dict[str, Any]:
    edges = {
        edge: {
            "risk": 0.0,
            "luminance_drift": 0.0,
            "rgb_drift": 0.0,
            "border_gradient": 0.0,
            "neighbor_drift": 0.0,
        }
        for edge in EDGE_NAMES
    }
    return {"worst_edge": "left", "edges": edges, "neighbor_compared": False}
