from __future__ import annotations

from sasta_dmart.transactions import (
    build_customer_history_record,
    build_transaction_payload,
    build_transaction_write_map,
)


def test_build_transaction_payload_for_logged_in_session():
    payload = build_transaction_payload(
        cart_items=[
            {
                "product_id": "00001",
                "name": "Apple",
                "qty": 2,
                "unit_price": 44.0,
                "barcode": "2700001044007",
            }
        ],
        session_type="logged_in",
        customer={"uid": "u1", "email": "user@example.com", "name": "Aarav Shah"},
        pi_node="pi-front-counter",
        now_utc="2026-04-12T14:25:30+00:00",
        bill_suffix="AB12CD",
    )

    assert payload["session_type"] == "logged_in"
    assert payload["total"] == 88.0
    assert payload["customer"]["email"] == "user@example.com"
    assert payload["bill_id"] == "BILL-20260412-142530-AB12CD"
    assert payload["generated_at_ms"] == 1776003930000
    assert payload["item_count"] == 2
    assert payload["item_summary"] == "Apple x2"
    assert payload["items"][0]["line_total"] == 88.0


def test_build_transaction_payload_for_anonymous_session_uses_fallback_customer():
    payload = build_transaction_payload(
        cart_items=[
            {
                "product_id": "00002",
                "name": "Banana",
                "qty": 1,
                "unit_price": 22.5,
                "barcode": "2700002022507",
            }
        ],
        session_type="anonymous",
        customer=None,
        pi_node="pi-front-counter",
        now_utc="2026-04-12T14:25:30+00:00",
        bill_suffix="CD34EF",
    )

    assert payload["customer"]["name"] == "Anonymous"
    assert payload["customer"]["uid"] is None
    assert payload["total"] == 22.5
    assert payload["generated_at_ms"] == 1776003930000
    assert payload["item_count"] == 1
    assert payload["item_summary"] == "Banana x1"


def test_build_transaction_payload_adds_sort_and_summary_fields():
    payload = build_transaction_payload(
        cart_items=[
            {
                "product_id": "00001",
                "name": "Apple",
                "qty": 2,
                "unit_price": 44.0,
                "barcode": "2700001044007",
            },
            {
                "product_id": "00002",
                "name": "Banana",
                "qty": 1,
                "unit_price": 22.5,
                "barcode": "2700002022507",
            },
        ],
        session_type="logged_in",
        customer={"uid": "u1", "email": "user@example.com", "name": "Aarav Shah"},
        pi_node="pi-front-counter",
        now_utc="2026-04-12T14:25:30+00:00",
        bill_suffix="AB12CD",
    )

    assert payload["generated_at_ms"] == 1776003930000
    assert payload["item_count"] == 3
    assert payload["item_summary"] == "Apple x2, Banana x1"
    assert "payment_type" not in payload


def test_build_customer_history_record_keeps_history_fields_in_sync():
    payload = {
        "bill_id": "BILL-20260412-142530-AB12CD",
        "generated_at": "2026-04-12T14:25:30+00:00",
        "generated_at_ms": 1776003930000,
        "session_type": "logged_in",
        "customer": {"uid": "u1", "email": "user@example.com", "name": "Aarav Shah"},
        "items": [
            {
                "product_id": "00001",
                "name": "Apple",
                "qty": 2,
                "unit_price": 44.0,
                "line_total": 88.0,
                "barcode": "2700001044007",
            }
        ],
        "total": 88.0,
        "pi_node": "pi-front-counter",
        "item_count": 2,
        "item_summary": "Apple x2",
        "payment_type": "card",
    }

    history_record = build_customer_history_record(
        transaction_id="-OXYZ123",
        transaction=payload,
    )

    assert history_record["transaction_id"] == "-OXYZ123"
    assert history_record["bill_id"] == payload["bill_id"]
    assert history_record["generated_at_ms"] == payload["generated_at_ms"]
    assert history_record["payment_type"] == "card"
    assert history_record["items"][0]["name"] == "Apple"


def test_build_transaction_write_map_writes_source_and_customer_mirror_atomically():
    payload = {
        "bill_id": "BILL-20260412-142530-AB12CD",
        "generated_at": "2026-04-12T14:25:30+00:00",
        "generated_at_ms": 1776003930000,
        "session_type": "logged_in",
        "customer": {"uid": "u1", "email": "user@example.com", "name": "Aarav Shah"},
        "items": [
            {
                "product_id": "00001",
                "name": "Apple",
                "qty": 2,
                "unit_price": 44.0,
                "line_total": 88.0,
                "barcode": "2700001044007",
            }
        ],
        "total": 88.0,
        "pi_node": "pi-front-counter",
        "item_count": 2,
        "item_summary": "Apple x2",
        "payment_type": "card",
    }

    updates = build_transaction_write_map(transaction_id="-OXYZ123", transaction=payload)

    assert updates["transactions/-OXYZ123"]["payment_type"] == "card"
    assert updates["customer_transactions/u1/-OXYZ123"]["transaction_id"] == "-OXYZ123"
    assert (
        updates["customer_transactions/u1/-OXYZ123"]["generated_at_ms"]
        == payload["generated_at_ms"]
    )


def test_build_transaction_write_map_for_anonymous_checkout_skips_customer_history():
    payload = {
        "bill_id": "BILL-20260412-142530-CD34EF",
        "generated_at": "2026-04-12T14:25:30+00:00",
        "generated_at_ms": 1776003930000,
        "session_type": "anonymous",
        "customer": {"uid": None, "email": None, "name": "Anonymous"},
        "items": [],
        "total": 22.5,
        "pi_node": "pi-front-counter",
        "item_count": 1,
        "item_summary": "Banana x1",
        "payment_type": "cash",
    }

    updates = build_transaction_write_map(transaction_id="-OXYZ124", transaction=payload)

    assert list(updates.keys()) == ["transactions/-OXYZ124"]
