# Public Claim Page

This directory contains the hosted HTTPS customer surfaces for Sasta Dmart.

## Purpose

The Pi QR code must point here, not to the laptop dashboard. The hosted pages here are responsible for:

- Google sign-in with Firebase Web Auth
- reading the login token from the QR URL
- claiming the Firebase login session exactly once
- showing signed-in purchase history on `history.html`

## Build the runtime config

Generate `config.js` before deploying:

```bash
python public_claim/build_config.py
```

This reads `FIREBASE_DB_URL` plus the required `FIREBASE_WEB_*` env vars and writes a plain static `config.js` file next to `index.html`.

## Local smoke test

```bash
python public_claim/build_config.py
python -m http.server 4173 --directory public_claim
```

Then open:

- `http://127.0.0.1:4173/?token=test-token` for claim flow
- `http://127.0.0.1:4173/history.html` for purchase history

## Deployment target

Deploy this directory as a static HTTPS site on your Cloudflare-controlled domain.

If you change anything under `public_claim/`, you need a fresh Cloudflare Direct Upload deployment before customer-facing changes go live.

Purchase history also requires the RTDB rules in `docs/firebase-rtdb-rules.json`, especially the `customer_transactions/<uid>` read constraint.
