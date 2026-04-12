from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from flask import Flask, jsonify, render_template


TransactionLoader = Callable[[], list[dict]]
PortalInfoLoader = Callable[[], dict]


def create_portal_app(
    transaction_loader: TransactionLoader,
    portal_info_loader: PortalInfoLoader,
) -> Flask:
    portal_root = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(portal_root / "templates"),
        static_folder=str(portal_root / "static"),
    )

    @app.get("/")
    def dashboard():
        portal_info = portal_info_loader()
        transactions = transaction_loader()
        return render_template(
            "dashboard.html",
            portal_info=portal_info,
            transactions=transactions,
        )

    @app.get("/api/transactions")
    def api_transactions():
        return jsonify({"ok": True, "transactions": transaction_loader()})

    @app.get("/api/all-bills")
    def api_all_bills_compat():
        return jsonify({"ok": True, "bills": transaction_loader()})

    @app.get("/api/portal-info")
    def api_portal_info():
        return jsonify({"ok": True, "portal": portal_info_loader()})

    return app
