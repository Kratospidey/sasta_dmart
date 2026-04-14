from __future__ import annotations


def test_dashboard_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Retail Ledger" in response.data
    assert b"claim.example.com" in response.data
    assert b"Payment" in response.data
    assert b"card" in response.data


def test_transactions_api_returns_json(client):
    response = client.get("/api/transactions")

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["transactions"][0]["bill_id"] == "BILL-2401"
    assert payload["transactions"][0]["payment_type"] == "card"


def test_dashboard_falls_back_to_dash_when_payment_type_missing():
    from sasta_dmart.portal import create_portal_app

    app = create_portal_app(
        transaction_loader=lambda: [
            {
                "bill_id": "BILL-2402",
                "generated_at": "2026-04-12T14:30:00+00:00",
                "session_type": "anonymous",
                "customer": {"name": "Anonymous"},
                "total": 10.0,
                "pi_node": "pi-front-counter",
            }
        ],
        portal_info_loader=lambda: {
            "dashboard_url": "http://laptop:5000",
            "public_claim_base_url": "https://claim.example.com",
            "tailscale_ip": "100.101.102.103",
            "hostname": "laptop",
        },
    )
    app.config.update(TESTING=True)

    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert b"<td>-</td>" in response.data


def test_portal_info_api_returns_dashboard_and_claim_urls(client):
    response = client.get("/api/portal-info")

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload["portal"]["dashboard_url"] == "http://laptop:5000"
    assert payload["portal"]["public_claim_base_url"] == "https://claim.example.com"
