"""
Laptop Firebase portal.

- Serves phone-friendly Google sign-in page for claiming Pi login sessions.
- Verifies Firebase ID token server-side with Admin SDK.
- Lets laptop view all transactions in Firebase in a dashboard.
"""

import os
import socket
import subprocess
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth, credentials, db
from flask import Flask, jsonify, render_template_string, request

from sasta_dmart.config import load_runtime_config

app = Flask(__name__)

try:
    RUNTIME_CONFIG = load_runtime_config("laptop")
except RuntimeError as exc:
    raise SystemExit(str(exc)) from exc


FIREBASE_DB_URL = RUNTIME_CONFIG.firebase_db_url
SERVICE_ACCOUNT_PATH = RUNTIME_CONFIG.firebase_service_account_path
PUBLIC_CLAIM_BASE_URL = RUNTIME_CONFIG.public_claim_base_url
LAPTOP_DASHBOARD_BASE_URL = RUNTIME_CONFIG.laptop_dashboard_base_url

FIREBASE_WEB_CONFIG = {
    "apiKey": "AIzaSyDG6DfpBGk55RNtn601y9mHzfIbi6KnqdU",
    "authDomain": "sasta-dmart.firebaseapp.com",
    "databaseURL": "https://sasta-dmart-default-rtdb.asia-southeast1.firebasedatabase.app",
    "projectId": "sasta-dmart",
    "storageBucket": "sasta-dmart.firebasestorage.app",
    "messagingSenderId": "72220625394",
    "appId": "1:72220625394:web:e2a836a8d1401561d5036b",
    "measurementId": "G-1F1YR18X2J",
}

if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})


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


def _publish_portal_info():
    info = _portal_info()
    try:
        db.reference("portal_config").set(info)
    except Exception:
        pass
    return info


PORTAL_INFO = _publish_portal_info()

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Sasta Dmart Portal</title>
  <style>
    :root { --bg:#0b1220; --panel:#121a2b; --card:#1a2439; --fg:#f8fafc; --muted:#9ca3af; --green:#22c55e; --red:#ef4444; --blue:#3b82f6; }
    body.light { --bg:#f3f4f6; --panel:#fff; --card:#f8fafc; --fg:#111827; --muted:#4b5563; }
    body { background:var(--bg); color:var(--fg); margin:0; font-family:Inter,Segoe UI,Arial,sans-serif; }
    .wrap { max-width:1000px; margin:0 auto; padding:18px; }
    .row { display:flex; gap:12px; flex-wrap:wrap; }
    .panel { background:var(--panel); border-radius:14px; padding:16px; margin-bottom:12px; }
    .btn { border:none; border-radius:10px; padding:10px 14px; cursor:pointer; font-weight:600; }
    .blue { background:var(--blue); color:#fff; }
    .green { background:var(--green); color:#041b0b; }
    .small { color:var(--muted); font-size:13px; }
    table { width:100%; border-collapse:collapse; font-size:14px; }
    th,td { text-align:left; border-bottom:1px solid rgba(148,163,184,.25); padding:8px 6px; }
    .status { font-weight:700; }
  </style>
</head>
<body>
<div class="wrap">
  <div class="row" style="justify-content:space-between;align-items:center;">
    <h2 style="margin:0;">Sasta Dmart Firebase Portal</h2>
    <button class="btn" onclick="document.body.classList.toggle('light')">Toggle Theme</button>
  </div>

  <div class="panel" id="claimPanel">
    <h3 style="margin-top:0;">Phone Login Claim</h3>
    <div class="small" id="claimText">Open this page from Pi QR code to claim a login session.</div>
    <div class="row" style="margin-top:10px;">
      <button id="googleBtn" class="btn blue">Sign in with Google</button>
      <button id="claimBtn" class="btn green" disabled>Claim Pi Session</button>
    </div>
    <div id="claimStatus" class="status" style="margin-top:10px;"></div>
  </div>

  <div class="panel">
    <h3 style="margin-top:0;">Transactions</h3>
    <div class="small">Live list from Firebase Realtime Database.</div>
    <div style="overflow:auto; margin-top:10px;">
      <table>
        <thead><tr><th>Bill</th><th>Time</th><th>Session</th><th>User</th><th>Total</th></tr></thead>
        <tbody id="txBody"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
  window.FIREBASE_WEB_CONFIG = {{ web_config | safe }};
</script>
<script type="module">
  import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js';
  import { getAuth, GoogleAuthProvider, getRedirectResult, signInWithPopup, signInWithRedirect } from 'https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js';

  const app = initializeApp(window.FIREBASE_WEB_CONFIG);
  const fbAuth = getAuth(app);
  const provider = new GoogleAuthProvider();

  const claimText = document.getElementById('claimText');
  const claimStatus = document.getElementById('claimStatus');
  const googleBtn = document.getElementById('googleBtn');
  const claimBtn = document.getElementById('claimBtn');
  const txBody = document.getElementById('txBody');

  const url = new URL(window.location.href);
  const token = url.searchParams.get('token');
  let idToken = null;

  if (token) claimText.textContent = `Session token detected: ${token.slice(0,10)}...`;

  async function postSignIn(user) {
    idToken = await user.getIdToken(true);
    claimStatus.textContent = `Signed in as ${user.email}`;
    claimStatus.style.color = '#22c55e';
    claimBtn.disabled = !token;
  }

  try {
    const redirectResult = await getRedirectResult(fbAuth);
    if (redirectResult && redirectResult.user) {
      await postSignIn(redirectResult.user);
    }
  } catch (err) {
    claimStatus.textContent = `Redirect sign-in failed: ${err.message}`;
    claimStatus.style.color = '#ef4444';
  }

  googleBtn.onclick = async () => {
    try {
      const result = await signInWithPopup(fbAuth, provider);
      await postSignIn(result.user);
    } catch (err) {
      const code = err && err.code ? String(err.code) : '';
      if (code.includes('popup') || code.includes('operation-not-supported')) {
        await signInWithRedirect(fbAuth, provider);
        return;
      }
      claimStatus.textContent = `Sign-in failed: ${err.message}`;
      claimStatus.style.color = '#ef4444';
    }
  };

  claimBtn.onclick = async () => {
    if (!token || !idToken) return;
    const res = await fetch('/api/claim-session', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ token, id_token: idToken })
    });
    const data = await res.json();
    claimStatus.textContent = data.ok ? 'Pi login claimed successfully. You can return to Pi.' : `Claim failed: ${data.error}`;
    claimStatus.style.color = data.ok ? '#22c55e' : '#ef4444';
  };

  async function loadTransactions() {
    const res = await fetch('/api/transactions');
    const data = await res.json();
    const rows = (data.transactions || []).map((t) => `
      <tr>
        <td>${t.bill_id || '-'}</td>
        <td>${t.generated_at || '-'}</td>
        <td>${t.session_type || '-'}</td>
        <td>${(t.customer && (t.customer.email || t.customer.name)) || 'Anonymous'}</td>
        <td>₹ ${Number(t.total || 0).toFixed(2)}</td>
      </tr>
    `).join('');
    txBody.innerHTML = rows || '<tr><td colspan="5">No transactions yet.</td></tr>';
  }
  loadTransactions();
  setInterval(loadTransactions, 3000);
</script>
</body>
</html>
"""


@app.get("/")
def index():
    import json

    return render_template_string(INDEX_HTML, web_config=json.dumps(FIREBASE_WEB_CONFIG))


@app.post("/api/claim-session")
def claim_session():
    payload = request.get_json(silent=True) or {}
    token = payload.get("token")
    id_token = payload.get("id_token")

    if not token or not id_token:
        return jsonify({"ok": False, "error": "token and id_token are required"}), 400

    try:
        decoded = auth.verify_id_token(id_token)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"invalid firebase id token: {exc}"}), 401

    ref = db.reference(f"login_sessions/{token}")
    existing = ref.get()
    if not existing:
        return jsonify({"ok": False, "error": "session token not found"}), 404
    if existing.get("status") == "closed":
        return jsonify({"ok": False, "error": "session already closed"}), 409

    claimed_by = {
        "uid": decoded.get("uid"),
        "email": decoded.get("email"),
        "name": decoded.get("name"),
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }
    ref.update({"claimed": True, "claimed_by": claimed_by, "status": "claimed"})
    return jsonify({"ok": True, "claimed_by": claimed_by})


@app.get("/api/transactions")
def api_transactions():
    transactions = db.reference("transactions").get() or {}
    rows = sorted((v for _, v in transactions.items()), key=lambda x: x.get("generated_at", ""), reverse=True)
    return jsonify({"ok": True, "transactions": rows})


@app.get("/api/all-bills")
def api_all_bills_compat():
    transactions = db.reference("transactions").get() or {}
    rows = sorted((v for _, v in transactions.items()), key=lambda x: x.get("generated_at", ""), reverse=True)
    return jsonify({"ok": True, "bills": rows})


@app.get("/api/portal-info")
def api_portal_info():
    return jsonify({"ok": True, "portal": PORTAL_INFO})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
