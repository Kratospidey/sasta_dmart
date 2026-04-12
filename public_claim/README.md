# Public Claim Page

This directory contains the hosted HTTPS phone claim surface for Sasta Dmart.

## Purpose

The Pi QR code must point here, not to the laptop dashboard. This page is responsible only for:

- Google sign-in with Firebase Web Auth
- reading the login token from the QR URL
- claiming the Firebase login session exactly once

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

Then open `http://127.0.0.1:4173/?token=test-token`.

## Deployment target

Deploy this directory as a static HTTPS site on your Cloudflare-controlled domain.
