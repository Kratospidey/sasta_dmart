"""Laptop Firebase portal dashboard and diagnostics surface."""

import socket
import subprocess
from datetime import datetime, timezone

from sasta_dmart.config import load_runtime_config
from sasta_dmart.firebase import initialize_firebase_admin
from sasta_dmart.portal import create_portal_app

from firebase_admin import db

try:
    RUNTIME_CONFIG = load_runtime_config("laptop")
except RuntimeError as exc:
    raise SystemExit(str(exc)) from exc


FIREBASE_DB_URL = RUNTIME_CONFIG.firebase_db_url
SERVICE_ACCOUNT_PATH = RUNTIME_CONFIG.firebase_service_account_path
PUBLIC_CLAIM_BASE_URL = RUNTIME_CONFIG.public_claim_base_url
LAPTOP_DASHBOARD_BASE_URL = RUNTIME_CONFIG.laptop_dashboard_base_url

initialize_firebase_admin(SERVICE_ACCOUNT_PATH, FIREBASE_DB_URL)


def _detect_tailscale_ipv4():
    try:
        out = subprocess.check_output(["tailscale", "ip", "-4"], text=True, timeout=2).strip()
    except Exception:
        return None

    for line in out.splitlines():
        value = line.strip()
        if value:
            return value
    return None


def _portal_info():
    hostname = socket.gethostname().lower()
    tailscale_ip = _detect_tailscale_ipv4()

    return {
        "dashboard_url": LAPTOP_DASHBOARD_BASE_URL,
        "public_claim_base_url": PUBLIC_CLAIM_BASE_URL,
        "tailscale_ip": tailscale_ip,
        "hostname": hostname,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _publish_portal_info() -> dict:
    info = _portal_info()
    try:
        db.reference("portal_config").set(info)
    except Exception:
        pass
    return info


def _load_transactions():
    transactions = db.reference("transactions").get() or {}
    return sorted(
        (value for value in transactions.values()),
        key=lambda row: row.get("generated_at", ""),
        reverse=True,
    )


def _load_portal_info():
    return _publish_portal_info()


app = create_portal_app(
    transaction_loader=_load_transactions,
    portal_info_loader=_load_portal_info,
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
