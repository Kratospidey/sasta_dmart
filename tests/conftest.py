from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client():
    from sasta_dmart.portal import create_portal_app

    app = create_portal_app(
        transaction_loader=lambda: [
            {
                "bill_id": "BILL-2401",
                "generated_at": "2026-04-12T14:25:30+00:00",
                "session_type": "logged_in",
                "customer": {"email": "user@example.com", "name": "Aarav Shah"},
                "payment_type": "card",
                "total": 88.0,
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

    with app.test_client() as test_client:
        yield test_client
