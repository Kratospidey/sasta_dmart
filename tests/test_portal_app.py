from __future__ import annotations


def test_dashboard_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Retail Ledger" in response.data
    assert b"claim.example.com" in response.data


def test_transactions_api_returns_json(client):
    response = client.get("/api/transactions")

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["transactions"][0]["bill_id"] == "BILL-2401"


def test_portal_info_api_returns_dashboard_and_claim_urls(client):
    response = client.get("/api/portal-info")

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload["portal"]["dashboard_url"] == "http://laptop:5000"
    assert payload["portal"]["public_claim_base_url"] == "https://claim.example.com"
