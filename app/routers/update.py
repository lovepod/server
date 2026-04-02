from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.config import Settings
from app.deps import get_settings
from app.schemas import FirmwareUpdateCheckResponse

router = APIRouter(prefix="/v1/device/update", tags=["device-update"])


def _parse_version_parts(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in version.strip().split("."):
        token = chunk.strip()
        if not token:
            parts.append(0)
            continue
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits or "0"))
    return tuple(parts)


def _is_newer_version(current_version: str, available_version: str) -> bool:
    current = _parse_version_parts(current_version)
    available = _parse_version_parts(available_version)
    max_len = max(len(current), len(available))
    current = current + (0,) * (max_len - len(current))
    available = available + (0,) * (max_len - len(available))
    return available > current


@router.get("/check", response_model=FirmwareUpdateCheckResponse)
def check_for_update(
    version: str = Query(..., min_length=1, max_length=32),
    board: str = Query(..., min_length=1, max_length=64),
    channel: str = Query(default="stable", min_length=1, max_length=32),
    device_uuid: str | None = Query(default=None, min_length=1, max_length=64),
    app_settings: Settings = Depends(get_settings),
) -> FirmwareUpdateCheckResponse:
    del board
    del device_uuid

    checked_at = datetime.now(UTC).isoformat()
    configured_version = (app_settings.firmware_update_version or "").strip()
    configured_url = (app_settings.firmware_update_url or "").strip()
    configured_sha256 = (app_settings.firmware_update_sha256 or "").strip() or None
    configured_channel = (app_settings.firmware_update_channel or "stable").strip() or "stable"
    requested_channel = channel.strip() or "stable"

    if (
        not app_settings.firmware_update_enabled
        or not configured_version
        or not configured_url
        or requested_channel != configured_channel
        or not _is_newer_version(version, configured_version)
    ):
        return FirmwareUpdateCheckResponse(
            updateAvailable=False,
            version=None,
            url=None,
            sha256=None,
            mandatory=False,
            channel=requested_channel,
            notes=None,
            sizeBytes=None,
            checkedAt=checked_at,
        )

    return FirmwareUpdateCheckResponse(
        updateAvailable=True,
        version=configured_version,
        url=configured_url,
        sha256=configured_sha256,
        mandatory=app_settings.firmware_update_mandatory,
        channel=configured_channel,
        notes=app_settings.firmware_update_notes,
        sizeBytes=app_settings.firmware_update_size_bytes,
        checkedAt=checked_at,
    )
