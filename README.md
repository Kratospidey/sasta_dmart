# Sasta Dmart Smart Checkout

Sasta Dmart is a two-device smart checkout demo:

- the Raspberry Pi runs the checkout kiosk, camera preview, barcode scan flow, and bill generation
- the laptop runs a local/Tailscale operator dashboard
- the phone login flow runs on a separate hosted HTTPS claim page

The critical design change in this version is intentional separation:

- **Pi app** owns checkout and session creation
- **public claim page** owns QR-driven Google sign-in and one-time claim
- **laptop dashboard** owns monitoring and diagnostics only

The laptop dashboard is no longer part of the phone auth path.

## Deliverables

Top-level entrypoints:

- `pi_checkout_gui_firebase.py`
- `laptop_firebase_portal.py`

Shared code:

- `sasta_dmart/config.py`
- `sasta_dmart/firebase.py`
- `sasta_dmart/sessions.py`
- `sasta_dmart/transactions.py`
- `sasta_dmart/portal/`

Hosted claim page:

- `public_claim/`

## Architecture

### Pi runtime

The Pi app:

- starts anonymous or login-backed sessions
- creates opaque high-entropy login tokens
- writes `login_sessions/<token>` to Firebase
- renders QR codes that always use `PUBLIC_CLAIM_BASE_URL`
- polls Firebase for claim status
- writes final transactions to Firebase

### Hosted claim page

The hosted claim page:

- lives on your public HTTPS domain
- signs the phone user in with Firebase Google auth
- verifies the token after sign-in
- performs a one-time atomic `pending -> claimed` transition with an RTDB transaction

### Laptop dashboard

The laptop dashboard:

- stays local/Tailscale-first
- shows transactions and portal/session diagnostics
- never hosts the phone sign-in flow

## Environment Variables

Create a local `.env` from `.env.example`, or export the variables directly.

Runtime config:

- `FIREBASE_DB_URL`
- `FIREBASE_SERVICE_ACCOUNT_PATH`
- `PUBLIC_CLAIM_BASE_URL`
- `LAPTOP_DASHBOARD_BASE_URL`
- `PI_NODE_NAME`

Hosted claim build config:

- `FIREBASE_WEB_API_KEY`
- `FIREBASE_WEB_AUTH_DOMAIN`
- `FIREBASE_WEB_PROJECT_ID`
- `FIREBASE_WEB_STORAGE_BUCKET`
- `FIREBASE_WEB_MESSAGING_SENDER_ID`
- `FIREBASE_WEB_APP_ID`
- `FIREBASE_WEB_MEASUREMENT_ID`

Auth-critical values must be explicit. There is no fallback to guessed hostnames, Windows paths, or runtime URL priority lists.

## Laptop Setup

1. Create and activate a virtualenv.
2. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-laptop.txt
```

3. Set the runtime env vars:

```bash
export FIREBASE_DB_URL="https://your-project-default-rtdb.asia-southeast1.firebasedatabase.app"
export FIREBASE_SERVICE_ACCOUNT_PATH="/absolute/path/to/service-account.json"
export PUBLIC_CLAIM_BASE_URL="https://claim.yourdomain.com"
export LAPTOP_DASHBOARD_BASE_URL="http://your-laptop-tailnet-name:5000"
export PI_NODE_NAME="pi-front-counter"
```

4. Start the dashboard:

```bash
python laptop_firebase_portal.py
```

5. Open the dashboard at `LAPTOP_DASHBOARD_BASE_URL`.

## Pi Setup

1. Install Raspberry Pi system packages:

```bash
sudo apt update
sudo apt install -y \
  python3-picamera2 \
  python3-tk \
  python3-pil \
  python3-pil.imagetk \
  python3-pyzbar \
  libzbar0
```

2. Create and activate a virtualenv.
3. Install Pi Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-pi.txt
```

4. Set the same runtime env vars as above, but with the Pi's `PI_NODE_NAME`.
5. Start the Pi app:

```bash
python3 pi_checkout_gui_firebase.py
```

## Hosted Claim Page Setup

The hosted claim page is a plain static site with a tiny generated `config.js`.

### Build locally

```bash
export FIREBASE_WEB_API_KEY="..."
export FIREBASE_WEB_AUTH_DOMAIN="your-project.firebaseapp.com"
export FIREBASE_WEB_PROJECT_ID="your-project"
export FIREBASE_WEB_STORAGE_BUCKET="your-project.firebasestorage.app"
export FIREBASE_WEB_MESSAGING_SENDER_ID="..."
export FIREBASE_WEB_APP_ID="..."
export FIREBASE_WEB_MEASUREMENT_ID="..."

python public_claim/build_config.py
```

That writes `public_claim/config.js`.

### Deploy on Cloudflare

1. Create a Cloudflare Pages project or other static-hosted site on your domain.
2. Set the site root to `public_claim/`.
3. Generate `config.js` during your deploy step, or upload it as part of the static artifact.
4. Publish the site on your canonical claim domain, for example:

```text
https://claim.yourdomain.com
```

5. Set:

```bash
PUBLIC_CLAIM_BASE_URL=https://claim.yourdomain.com
```

That exact HTTPS origin is what the Pi QR code must use.

## Firebase Console Setup

### 1. Enable Google sign-in

Firebase Console:

1. Go to `Authentication`
2. Open `Sign-in method`
3. Enable `Google`
4. Save

### 2. Add authorized domains

Firebase Console:

1. Go to `Authentication`
2. Open `Settings`
3. Under `Authorized domains`, add:
   - `claim.yourdomain.com`
   - `localhost` only if you need local claim-page testing
4. Do **not** depend on random Tailscale hostnames for Google auth

The public claim domain must be the stable, canonical auth origin.

### 3. Realtime Database

Use the RTDB URL from your project and apply the rules in:

- `docs/firebase-rtdb-rules.json`

These rules are designed for:

- authenticated reads of `login_sessions/<token>` from the hosted claim page
- atomic one-time writes from `pending` to `claimed`
- immutable session metadata during client claims

### 4. Web app config

Firebase Console:

1. Open `Project settings`
2. Select your web app
3. Copy the web app config values
4. Put them in the `FIREBASE_WEB_*` env vars used by `public_claim/build_config.py`

## Realtime Database Rules

The exact file lives at:

- `docs/firebase-rtdb-rules.json`

Important rule assumptions:

- client reads and writes for login sessions require authenticated users
- session claims must stay atomic
- the rules rely on `expires_at_ms` for time-based expiry checks
- the Pi and laptop use the Admin SDK, so they are not constrained by these client rules

## Session Data Shape

Minimal `login_sessions/<token>` example:

```json
{
  "status": "pending",
  "created_at": "2026-04-12T14:20:31Z",
  "expires_at": "2026-04-12T14:24:31Z",
  "expires_at_ms": 1776003871000,
  "pi_node": "pi-front-counter",
  "claimed_by": null,
  "claimed_at": null,
  "claim_url": "https://claim.yourdomain.com/?token=4b2d..."
}
```

Minimal `transactions/<id>` example:

```json
{
  "bill_id": "BILL-20260412-142530-AB12CD",
  "generated_at": "2026-04-12T14:25:30Z",
  "session_type": "logged_in",
  "customer": {
    "uid": "firebase-uid-123",
    "email": "user@example.com",
    "name": "Aarav Shah"
  },
  "items": [
    {
      "product_id": "00001",
      "name": "Apple",
      "qty": 2,
      "unit_price": 44.0,
      "line_total": 88.0,
      "barcode": "2700001044007"
    }
  ],
  "total": 88.0,
  "pi_node": "pi-front-counter"
}
```

## QR Login Troubleshooting

If phone claim is failing:

1. Confirm the Pi session record exists under `login_sessions/<token>`.
2. Confirm the QR URL starts with `PUBLIC_CLAIM_BASE_URL`.
3. Confirm the claim page is served over HTTPS on the exact domain listed in Firebase `Authorized domains`.
4. Confirm the token is still `pending` and not `expired`, `claimed`, or `closed`.
5. Confirm RTDB rules were updated from `docs/firebase-rtdb-rules.json`.
6. Confirm the hosted page generated the correct `config.js`.
7. Confirm the phone user signs in before claim.

If the dashboard opens on the phone for auth, your deployment is wrong. The phone should hit the public claim page instead.

## Secret Hygiene

- `.env` should stay local only
- service-account JSON files must never be tracked
- generated `public_claim/config.js` should not be committed

If a service-account JSON file or `.env` with secrets was ever pushed to a public remote, rotate or reissue those credentials after removing them from version control.

## Removed Legacy Files

These older non-final artifacts were removed from the supported runtime story:

- `pi_checkout_gui.py`
- `laptop_bill_server.py`
- `received_bills.json`

Use the Firebase-backed Pi app, the laptop dashboard, and the hosted claim page instead.
