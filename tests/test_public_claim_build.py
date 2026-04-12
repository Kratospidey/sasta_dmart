from __future__ import annotations

from pathlib import Path

import pytest

from public_claim.build_config import render_config


def test_render_config_requires_firebase_keys(tmp_path):
    with pytest.raises(RuntimeError, match="FIREBASE_WEB_API_KEY"):
        render_config({}, tmp_path / "config.js")


def test_render_config_writes_plain_js_payload(tmp_path):
    output_path = tmp_path / "config.js"
    config = {
        "FIREBASE_DB_URL": "https://example-default-rtdb.asia-southeast1.firebasedatabase.app",
        "FIREBASE_WEB_API_KEY": "api-key",
        "FIREBASE_WEB_AUTH_DOMAIN": "example.firebaseapp.com",
        "FIREBASE_WEB_PROJECT_ID": "example",
        "FIREBASE_WEB_STORAGE_BUCKET": "example.firebasestorage.app",
        "FIREBASE_WEB_MESSAGING_SENDER_ID": "12345",
        "FIREBASE_WEB_APP_ID": "app-id",
        "FIREBASE_WEB_MEASUREMENT_ID": "measurement-id",
    }

    render_config(config, output_path)

    contents = output_path.read_text(encoding="utf-8")
    assert "window.PUBLIC_CLAIM_CONFIG" in contents
    assert '"apiKey": "api-key"' in contents
    assert (
        '"databaseURL": '
        '"https://example-default-rtdb.asia-southeast1.firebasedatabase.app"'
    ) in contents
