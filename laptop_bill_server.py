"""
laptop_bill_server.py

Laptop side Flask app:
- Receives final bills from the Pi over the Tailscale network
- Displays the latest bill and bill history in a webpage
"""

import json
import os
from datetime import datetime
from threading import Lock

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

DATA_FILE = "received_bills.json"
data_lock = Lock()
bills = []


def load_bills():
    global bills
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                bills = json.load(f)
        except Exception:
            bills = []
    else:
        bills = []


def save_bills():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(bills, f, indent=2)


@app.route("/api/bills", methods=["POST"])
def receive_bill():
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    required = {"bill_id", "generated_at", "items", "total"}
    missing = required - set(payload.keys())
    if missing:
        return jsonify({"ok": False, "error": f"Missing fields: {sorted(missing)}"}), 400

    record = {
        "bill_id": payload["bill_id"],
        "generated_at": payload["generated_at"],
        "source": payload.get("source", "unknown"),
        "items": payload["items"],
        "total": payload["total"],
        "received_at": datetime.now().isoformat(timespec="seconds"),
    }

    with data_lock:
        bills.insert(0, record)
        save_bills()

    return jsonify({"ok": True, "message": "Bill received", "bill_id": record["bill_id"]}), 200


@app.route("/api/latest-bill", methods=["GET"])
def latest_bill():
    with data_lock:
        latest = bills[0] if bills else None
    return jsonify({"ok": True, "bill": latest})


@app.route("/api/all-bills", methods=["GET"])
def all_bills():
    with data_lock:
        return jsonify({"ok": True, "bills": bills})


HTML_PAGE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Self Checkout Bills</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #f7f7f7; color: #222; }
        h1, h2 { margin-bottom: 8px; }
        .card { background: white; border-radius: 14px; padding: 18px; box-shadow: 0 2px 10px rgba(0,0,0,.08); margin-bottom: 20px; }
        .muted { color: #666; }
        .row { display: flex; gap: 20px; flex-wrap: wrap; }
        .pill { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #eef4ff; color: #1f4fbf; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { border-bottom: 1px solid #e5e5e5; padding: 10px 8px; text-align: left; }
        th:last-child, td:last-child { text-align: right; }
        .total { font-size: 20px; font-weight: bold; text-align: right; margin-top: 12px; }
        .empty { padding: 30px; text-align: center; color: #777; }
        .small { font-size: 13px; }
    </style>
</head>
<body>
    <h1>Pi Self Checkout Bills</h1>
    <p class="muted">Open this page on the laptop while the Pi sends bills over Tailscale.</p>

    <div id="latestBill" class="card">
        <div class="empty">Waiting for first bill...</div>
    </div>

    <div class="card">
        <h2>Bill History</h2>
        <div id="history" class="muted">No bills yet.</div>
    </div>

    <script>
        function renderBillCard(bill) {
            if (!bill) {
                return '<div class="empty">Waiting for first bill...</div>';
            }

            let rows = '';
            for (const item of bill.items) {
                rows += `
                    <tr>
                        <td>${item.name}</td>
                        <td>${item.qty}</td>
                        <td>₹ ${Number(item.unit_price).toFixed(2)}</td>
                        <td>₹ ${Number(item.line_total).toFixed(2)}</td>
                    </tr>
                `;
            }

            return `
                <h2>Latest Bill</h2>
                <div class="row small">
                    <div><span class="pill">${bill.bill_id}</span></div>
                    <div><strong>Generated:</strong> ${bill.generated_at}</div>
                    <div><strong>Received:</strong> ${bill.received_at}</div>
                    <div><strong>Source:</strong> ${bill.source}</div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th>Qty</th>
                            <th>Unit Price</th>
                            <th>Line Total</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
                <div class="total">Grand Total: ₹ ${Number(bill.total).toFixed(2)}</div>
            `;
        }

        function renderHistory(bills) {
            if (!bills || bills.length === 0) {
                return 'No bills yet.';
            }

            return `
                <ul>
                    ${bills.map(b => `<li><strong>${b.bill_id}</strong> — ₹ ${Number(b.total).toFixed(2)} — ${b.generated_at}</li>`).join('')}
                </ul>
            `;
        }

        async function refreshData() {
            try {
                const res = await fetch('/api/all-bills');
                const data = await res.json();

                const bills = data.bills || [];
                const latest = bills.length > 0 ? bills[0] : null;

                document.getElementById('latestBill').innerHTML = renderBillCard(latest);
                document.getElementById('history').innerHTML = renderHistory(bills);
            } catch (err) {
                document.getElementById('latestBill').innerHTML = '<div class="empty">Failed to load bills.</div>';
            }
        }

        refreshData();
        setInterval(refreshData, 2000);
    </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE)


if __name__ == "__main__":
    load_bills()
    app.run(host="0.0.0.0", port=5000, debug=False)
