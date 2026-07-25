"""Gate DSF activation on complete, atomically finalized texture artifacts."""

import O4_Texture_Artifact_Finalizer as TAF
import O4_UI_Utils as UI


def finalize_texture_conversion(tile, result_holder):
    """Finalize successful scheduler output and report any integrity failure."""
    if "exception" in result_holder:
        return False
    result = result_holder.get("result")
    if result is None or result.interrupted or result.failed:
        return False
    try:
        TAF.finalize_terrain_texture_references(
            tile,
            _completed_texture_results(result),
        )
    except TAF.TextureFinalizationError as exc:
        UI.vprint(1, "Texture artifact finalization failed:", str(exc))
        UI.vprint(3, exc)
        return False
    return True


def _completed_texture_results(result):
    """Return the complete result set or reject scheduler aggregation drift."""
    if len(result.results) != result.completed:
        raise TAF.TextureFinalizationError(
            "texture conversion result count mismatch: "
            f"completed={result.completed}, results={len(result.results)}"
        )
    return result.results
