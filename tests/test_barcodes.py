from __future__ import annotations

from types import SimpleNamespace

import pytest

from sasta_dmart.barcodes import (
    BarcodeParseError,
    build_sdm_payload,
    parse_sdm_payload,
    select_first_supported_candidate,
)


def test_build_and_parse_sdm_payload_round_trip():
    payload = build_sdm_payload("00001", 60.0)

    assert payload == "SDM|pid=00001|price=60.00"
    parsed = parse_sdm_payload(payload)
    assert parsed.product_id == "00001"
    assert parsed.unit_price == 60.0


def test_parse_sdm_payload_rejects_bad_prefix():
    with pytest.raises(BarcodeParseError):
        parse_sdm_payload("CODE128 #")


def test_select_first_supported_candidate_skips_junk():
    decoded = [
        SimpleNamespace(type="CODE128", data=b"CODE128 #"),
        SimpleNamespace(type="QRCODE", data=b""),
        SimpleNamespace(type="CODE128", data=b"SDM|pid=00003|price=10.00"),
    ]

    accepted, debug_rows = select_first_supported_candidate(decoded)

    assert accepted.product_id == "00003"
    assert accepted.unit_price == 10.0
    assert debug_rows[0]["accepted"] is False
    assert debug_rows[-1]["accepted"] is True
