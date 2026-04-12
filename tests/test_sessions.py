from __future__ import annotations

from sasta_dmart.sessions import (
    DEFAULT_LOGIN_SESSION_TTL_SECONDS,
    build_claim_url,
    build_login_session,
    can_claim_session,
    expire_session_record,
)


def test_build_login_session_sets_default_ttl():
    record = build_login_session(
        token="abc123",
        pi_node="pi-front-counter",
        public_claim_base_url="https://claim.example.com",
        now_utc="2026-04-12T14:20:31+00:00",
    )

    assert record["status"] == "pending"
    assert record["pi_node"] == "pi-front-counter"
    assert record["claimed_by"] is None
    assert record["claimed_at"] is None
    assert record["claim_url"] == "https://claim.example.com/?token=abc123"
    assert record["expires_at"] == "2026-04-12T14:24:31+00:00"


def test_build_claim_url_uses_canonical_base():
    assert (
        build_claim_url("https://claim.example.com/", "opaque-token")
        == "https://claim.example.com/?token=opaque-token"
    )


def test_expired_session_is_not_claimable():
    record = {
        "status": "pending",
        "expires_at": "2026-04-12T14:20:31+00:00",
    }

    assert can_claim_session(record, now_utc="2026-04-12T14:21:31+00:00") is False


def test_expire_session_record_transitions_pending_to_expired():
    record = {
        "status": "pending",
        "expires_at": "2026-04-12T14:20:31+00:00",
    }

    expired = expire_session_record(record, now_utc="2026-04-12T14:21:31+00:00")

    assert expired["status"] == "expired"
    assert expired["expires_at"] == "2026-04-12T14:20:31+00:00"


def test_expire_session_record_preserves_claimed_session():
    record = {
        "status": "claimed",
        "expires_at": "2026-04-12T14:20:31+00:00",
    }

    same_record = expire_session_record(record, now_utc="2026-04-12T14:21:31+00:00")

    assert same_record["status"] == "claimed"


def test_default_ttl_constant_matches_spec():
    assert DEFAULT_LOGIN_SESSION_TTL_SECONDS == 240
