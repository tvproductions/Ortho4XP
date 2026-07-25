"""Preserve requested and resolved texture identities across provider failover."""


def with_job_texture_resolution(job, result):
    """Attach scheduler identities unless conversion already supplied them."""
    if result.requested_attrs is not None or result.resolved_attrs is not None:
        return result
    resolved_attrs = (
        job.til_x_left,
        job.til_y_top,
        job.zoomlevel,
        job.provider_code,
    )
    requested_attrs = (
        job.source.terrain_attrs if job.source is not None else resolved_attrs
    )
    return result.with_texture_resolution(requested_attrs, resolved_attrs)
