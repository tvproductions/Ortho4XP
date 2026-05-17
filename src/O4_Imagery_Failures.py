from dataclasses import dataclass
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import O4_UI_Utils as UI

incomplete_imgs: dict[str, list[Any]] = {}
imagery_failure_records: list[Any] = []
_imagery_failure_lock = threading.Lock()


@dataclass(frozen=True)
class ImageryFailureRecord:
    provider_code: str | None
    request_type: str | None
    url_type: str | None
    status_code: int | str | None
    connect_retries: int
    bad_data_retries: int
    texture_filename: str | None
    tile_x: int | None
    tile_y: int | None
    zoomlevel: int | None
    url_origin: str
    url_path: str
    reason: str
    full_url: str | None = None

    def to_context(self, include_full_url=False):
        context = {
            "provider_code": self.provider_code,
            "request_type": self.request_type,
            "url_type": self.url_type,
            "status_code": self.status_code,
            "connect_retries": self.connect_retries,
            "bad_data_retries": self.bad_data_retries,
            "texture_filename": self.texture_filename,
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
            "zoomlevel": self.zoomlevel,
            "url_origin": self.url_origin,
            "url_path": self.url_path,
            "reason": self.reason,
        }
        if include_full_url and self.full_url:
            context["full_url"] = self.full_url
        return context


def response_status_code(response):
    code = getattr(response, "status_code", None)
    if code is not None:
        return code
    status_text = str(response)
    if "[" in status_text and "]" in status_text:
        return status_text.split("[", 1)[1].split("]", 1)[0]
    return status_text


def response_status_text(response):
    code = response_status_code(response)
    return f"[{code}]" if isinstance(code, int) else str(response)


def request_headers_with_context(headers, context):
    return (headers, context)


def split_request_headers(request_headers):
    if isinstance(request_headers, tuple) and len(request_headers) == 2:
        return request_headers
    return request_headers, None


def provider_with_texture_context(provider, texture_context):
    if not texture_context:
        return provider
    return {**provider, "_o4xp_texture_context": texture_context}


def request_context(provider, url_type, extra=None):
    return {
        **provider.get("_o4xp_texture_context", {}),
        "provider_code": provider["code"],
        "request_type": provider["request_type"],
        "url_type": url_type,
        **(extra or {}),
    }


def failure_record(
    url, status_code, connect_retries, bad_data_retries, reason, context
):
    context = context or {}
    parsed = urlparse(url)
    origin = (
        f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    )
    return ImageryFailureRecord(
        provider_code=context.get("provider_code"),
        request_type=context.get("request_type"),
        url_type=context.get("url_type"),
        status_code=status_code,
        connect_retries=connect_retries,
        bad_data_retries=bad_data_retries,
        texture_filename=context.get("texture_filename"),
        tile_x=context.get("tile_x"),
        tile_y=context.get("tile_y"),
        zoomlevel=context.get("zoomlevel"),
        url_origin=origin,
        url_path=parsed.path or url,
        reason=reason,
        full_url=url,
    )


def record_imagery_failure(record):
    with _imagery_failure_lock:
        imagery_failure_records.append(record)
    UI.log_event(
        "Imagery request failed",
        level="WARNING",
        context=record.to_context(include_full_url=UI.verbosity >= 3),
    )


def record_failure(
    url, status_code, connect_retries, bad_data_retries, reason, context
):
    record = failure_record(
        url, status_code, connect_retries, bad_data_retries, reason, context
    )
    record_imagery_failure(record)
    return record


def failures_for_texture(texture_filename, provider_code):
    with _imagery_failure_lock:
        return [
            record
            for record in imagery_failure_records
            if record.texture_filename == texture_filename
            and record.provider_code == provider_code
        ]


def record_incomplete_texture(file_dir, file_name, texture_attributes):
    til_x_left, til_y_top, zoomlevel, provider_code = texture_attributes
    tile_coords = Path(file_dir).parent.name
    failures = failures_for_texture(file_name, provider_code)
    record = {
        "file_name": file_name,
        "provider_code": provider_code,
        "til_x_left": til_x_left,
        "til_y_top": til_y_top,
        "zoomlevel": zoomlevel,
        "failures": [
            failure.to_context(include_full_url=False) for failure in failures
        ],
    }
    records = incomplete_imgs.setdefault(tile_coords, [])
    for index, existing in enumerate(records):
        existing_file_name = (
            existing.get("file_name") if isinstance(existing, dict) else existing
        )
        if existing_file_name == file_name:
            records[index] = record
            return
    records.append(record)


def incomplete_texture_file_names(tile_coords):
    return [
        record.get("file_name") if isinstance(record, dict) else record
        for record in incomplete_imgs.get(tile_coords, [])
    ]


def incomplete_texture_file_names_by_tile():
    return {
        tile_coords: incomplete_texture_file_names(tile_coords)
        for tile_coords in incomplete_imgs
    }


def _increment_count(counts, key):
    normalized = str(key if key is not None else "unknown")
    counts[normalized] = counts.get(normalized, 0) + 1


def _add_incomplete_to_summary(record, by_provider, by_status, by_request_type):
    if isinstance(record, dict):
        provider = record.get("provider_code")
        failures = record.get("failures") or []
    else:
        provider = None
        failures = []
    _increment_count(by_provider, provider)
    if not failures:
        _increment_count(by_status, "unknown")
        _increment_count(by_request_type, "unknown")
        return
    for failure in failures:
        _increment_count(by_status, failure.get("status_code"))
        _increment_count(by_request_type, failure.get("request_type"))


def _texture_summary(record, kind):
    if not isinstance(record, dict):
        return {"file_name": record, "kind": kind}
    return {
        "file_name": record.get("file_name"),
        "provider_code": record.get("provider_code"),
        "til_x_left": record.get("til_x_left"),
        "til_y_top": record.get("til_y_top"),
        "zoomlevel": record.get("zoomlevel"),
        "kind": kind,
    }


def imagery_download_summary(tile_coords, final_failures=None):
    final_failures = final_failures or []
    incomplete = list(incomplete_imgs.get(tile_coords, []))
    if not incomplete and not final_failures:
        return None

    by_provider = {}
    by_status = {}
    by_request_type = {}
    textures = []
    for record in incomplete:
        _add_incomplete_to_summary(record, by_provider, by_status, by_request_type)
        textures.append(_texture_summary(record, "incomplete"))

    for failure in final_failures:
        _increment_count(by_provider, failure.get("provider_code"))
        _increment_count(by_status, failure.get("status_code"))
        _increment_count(by_request_type, failure.get("request_type"))
        textures.append({**failure, "kind": "failed"})

    summary = {
        "tile": tile_coords,
        "incomplete_textures": len(incomplete),
        "failed_textures": len(final_failures),
        "total_textures": len(incomplete) + len(final_failures),
        "by_provider": by_provider,
        "by_status": by_status,
        "by_request_type": by_request_type,
        "textures": textures,
    }
    UI.log_event("Imagery download summary", level="WARNING", context=summary)
    return summary
