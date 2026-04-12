from __future__ import annotations

from sasta_dmart.transactions import build_transaction_payload


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
