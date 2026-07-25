"""Shared error contract for pre-activation texture finalization."""


class TextureFinalizationError(RuntimeError):
    """A texture-resolution invariant prevented safe DSF activation."""
