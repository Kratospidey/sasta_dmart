from __future__ import annotations

import pytest

from sasta_dmart.config import load_runtime_config


def test_missing_public_claim_base_url_raises(monkeypatch):
    monkeypatch.setenv("FIREBASE_DB_URL", "https://example.firebaseio.com")
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", "/tmp/service-account.json")
    monkeypatch.setenv("LAPTOP_DASHBOARD_BASE_URL", "http://laptop:5000")
    monkeypatch.setenv("PI_NODE_NAME", "pi-front-counter")
    monkeypatch.delenv("PUBLIC_CLAIM_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="PUBLIC_CLAIM_BASE_URL"):
        load_runtime_config("pi")


def test_missing_service_account_path_raises(monkeypatch):
    monkeypatch.setenv("FIREBASE_DB_URL", "https://example.firebaseio.com")
    monkeypatch.setenv("PUBLIC_CLAIM_BASE_URL", "https://claim.example.com")
    monkeypatch.setenv("LAPTOP_DASHBOARD_BASE_URL", "http://laptop:5000")
    monkeypatch.setenv("PI_NODE_NAME", "pi-front-counter")
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_PATH", raising=False)

    with pytest.raises(RuntimeError, match="FIREBASE_SERVICE_ACCOUNT_PATH"):
        load_runtime_config("laptop")
