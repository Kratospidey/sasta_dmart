from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_LOGIN_SESSION_TTL_SECONDS = 240


def _coerce_utc(now_utc: str | datetime | None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if isinstance(now_utc, datetime):
        return now_utc.astimezone(timezone.utc)
    return datetime.fromisoformat(now_utc).astimezone(timezone.utc)


def build_claim_url(public_claim_base_url: str, token: str) -> str:
    return f"{public_claim_base_url.rstrip('/')}/?token={token}"


def build_login_session(
    token: str,
    pi_node: str,
    public_claim_base_url: str,
    now_utc: str | datetime | None = None,
    ttl_seconds: int = DEFAULT_LOGIN_SESSION_TTL_SECONDS,
) -> dict[str, Any]:
    created_at = _coerce_utc(now_utc)
    expires_at = created_at + timedelta(seconds=ttl_seconds)
    return {
        "status": "pending",
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "expires_at_ms": int(expires_at.timestamp() * 1000),
        "pi_node": pi_node,
        "claimed_by": None,
        "claimed_at": None,
        "claim_url": build_claim_url(public_claim_base_url, token),
    }


def can_claim_session(record: dict[str, Any] | None, now_utc: str | datetime | None = None) -> bool:
    if not record:
        return False
    if record.get("status") != "pending":
        return False

    expires_at = record.get("expires_at")
    if not expires_at:
        return False

    return _coerce_utc(now_utc) <= _coerce_utc(expires_at)


def expire_session_record(
    record: dict[str, Any],
    now_utc: str | datetime | None = None,
) -> dict[str, Any]:
    snapshot = deepcopy(record)
    if snapshot.get("status") != "pending":
        return snapshot
    if can_claim_session(snapshot, now_utc=now_utc):
        return snapshot

    snapshot["status"] = "expired"
    return snapshot


def close_session_record(
    record: dict[str, Any],
    now_utc: str | datetime | None = None,
) -> dict[str, Any]:
    snapshot = deepcopy(record)
    if snapshot.get("status") not in {"claimed", "pending"}:
        return snapshot

    snapshot["status"] = "closed"
    snapshot["closed_at"] = _coerce_utc(now_utc).isoformat()
    return snapshot
