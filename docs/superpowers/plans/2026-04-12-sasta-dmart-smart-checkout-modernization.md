# Sasta Dmart Smart Checkout Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the Pi QR login flow, move phone auth to a hosted claim page, modernize the Pi and laptop UI, clean up config/secrets/repo structure, and leave the project easy to run on Pi and laptop.

**Architecture:** Keep `pi_checkout_gui_firebase.py` as the Python desktop checkout runtime and `laptop_firebase_portal.py` as the local/Tailscale Flask dashboard. Extract shared logic into a lean `sasta_dmart` package, and add a small `public_claim/` static site for QR-driven phone sign-in and claim. Use explicit config for `PUBLIC_CLAIM_BASE_URL` and `LAPTOP_DASHBOARD_BASE_URL`; no auth-critical URL guessing remains.

**Tech Stack:** Python, Tkinter, Flask, Firebase Admin SDK, Firebase Web Auth, Firebase Realtime Database, pytest, static HTML/CSS/JS for hosted claim page

---

## File Map

### Runtime entrypoints

- Modify: `pi_checkout_gui_firebase.py`
- Modify: `laptop_firebase_portal.py`

### Shared package

- Create: `sasta_dmart/__init__.py`
- Create: `sasta_dmart/config.py`
- Create: `sasta_dmart/firebase.py`
- Create: `sasta_dmart/sessions.py`
- Create: `sasta_dmart/transactions.py`
- Create: `sasta_dmart/portal/__init__.py`
- Create: `sasta_dmart/portal/templates/base.html`
- Create: `sasta_dmart/portal/templates/dashboard.html`
- Create: `sasta_dmart/portal/static/portal.css`
- Create: `sasta_dmart/portal/static/portal.js`

### Hosted claim surface

- Create: `public_claim/index.html`
- Create: `public_claim/styles.css`
- Create: `public_claim/app.js`
- Create: `public_claim/build_config.py`
- Create: `public_claim/config.template.js`
- Create: `public_claim/README.md`

### Docs and config

- Modify: `.gitignore`
- Create: `.env.example`
- Create: `requirements-laptop.txt`
- Create: `requirements-pi.txt`
- Create: `requirements-dev.txt`
- Modify: `README.md`
- Create: `docs/firebase-rtdb-rules.json`

### Tests

- Create: `tests/conftest.py`
- Create: `tests/test_config.py`
- Create: `tests/test_sessions.py`
- Create: `tests/test_transactions.py`
- Create: `tests/test_portal_app.py`
- Create: `tests/test_public_claim_build.py`

### Cleanup targets

- Delete if obsolete after migration: `pi_checkout_gui.py`
- Delete if obsolete after migration: `laptop_bill_server.py`
- Delete if obsolete after migration: `received_bills.json`
- Remove from git tracking: `sasta-dmart-firebase-adminsdk-fbsvc-708b9680b3.json`

---

### Task 1: Config, Dependency Split, And Secret Hygiene

**Files:**
- Create: `sasta_dmart/__init__.py`
- Create: `sasta_dmart/config.py`
- Create: `.env.example`
- Create: `requirements-laptop.txt`
- Create: `requirements-pi.txt`
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Test: `tests/test_config.py`
- Modify: `.gitignore`
- Modify: `pi_checkout_gui_firebase.py`
- Modify: `laptop_firebase_portal.py`

- [ ] **Step 1: Write the failing config tests**

```python
from sasta_dmart.config import load_runtime_config


def test_missing_public_claim_base_url_raises(monkeypatch):
    monkeypatch.delenv("PUBLIC_CLAIM_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="PUBLIC_CLAIM_BASE_URL"):
        load_runtime_config("pi")


def test_missing_service_account_path_raises(monkeypatch):
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_PATH", raising=False)
    with pytest.raises(RuntimeError, match="FIREBASE_SERVICE_ACCOUNT_PATH"):
        load_runtime_config("laptop")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `load_runtime_config`

- [ ] **Step 3: Implement explicit runtime config loading**

Write `sasta_dmart/config.py` with a small validated config loader:

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RuntimeConfig:
    firebase_db_url: str
    firebase_service_account_path: str
    public_claim_base_url: str
    laptop_dashboard_base_url: str
    pi_node_name: str


def load_runtime_config(role: str) -> RuntimeConfig:
    ...
```

- [ ] **Step 4: Split dependencies and add env template**

Populate:

- `requirements-laptop.txt`
- `requirements-pi.txt`
- `requirements-dev.txt`
- `.env.example`
- `tests/conftest.py`

Keep them lean. Put only `pytest`-class tooling in `requirements-dev.txt`.

- [ ] **Step 5: Harden ignore rules**

Update `.gitignore` to block:

- `.env`
- `*.env`
- service-account JSON files
- generated `public_claim/config.js`
- caches and Python artifacts
- `.superpowers/`

- [ ] **Step 6: Wire entry scripts to fail early on missing config**

Replace hard-coded defaults in the two top-level entry scripts with `load_runtime_config(...)`. Startup failures must raise explicit, human-readable errors.

- [ ] **Step 7: Run tests to verify config path works**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add .gitignore .env.example requirements-laptop.txt requirements-pi.txt requirements-dev.txt \
  sasta_dmart/__init__.py sasta_dmart/config.py tests/conftest.py tests/test_config.py \
  pi_checkout_gui_firebase.py laptop_firebase_portal.py
git commit -m "chore: add explicit runtime config and dependency split"
```

---

### Task 2: Session State Machine And Transaction Helpers

**Files:**
- Create: `sasta_dmart/firebase.py`
- Create: `sasta_dmart/sessions.py`
- Create: `sasta_dmart/transactions.py`
- Test: `tests/test_sessions.py`
- Test: `tests/test_transactions.py`

- [ ] **Step 1: Write the failing session tests**

```python
from sasta_dmart.sessions import build_login_session, expire_session_record, can_claim_session


def test_build_login_session_sets_default_ttl():
    record = build_login_session(token="abc", pi_node="pi-front-counter")
    assert record["status"] == "pending"
    assert record["pi_node"] == "pi-front-counter"
    assert record["claimed_by"] is None


def test_expired_session_is_not_claimable():
    record = {
        "status": "pending",
        "expires_at": "2026-04-12T14:20:31+00:00",
    }
    assert can_claim_session(record, now_utc="2026-04-12T14:21:31+00:00") is False
```

- [ ] **Step 2: Write the failing transaction tests**

```python
from sasta_dmart.transactions import build_transaction_payload


def test_build_transaction_payload_for_logged_in_session():
    payload = build_transaction_payload(
        cart_items=[{"product_id": "00001", "name": "Apple", "qty": 2, "unit_price": 44.0, "barcode": "2700001044007"}],
        session_type="logged_in",
        customer={"uid": "u1", "email": "user@example.com", "name": "Aarav Shah"},
        pi_node="pi-front-counter",
    )
    assert payload["session_type"] == "logged_in"
    assert payload["total"] == 88.0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_sessions.py tests/test_transactions.py -v`
Expected: FAIL with missing modules/functions

- [ ] **Step 4: Implement session helpers**

Add lean helpers in `sasta_dmart/sessions.py` for:

- token/session record creation
- claim URL creation from `PUBLIC_CLAIM_BASE_URL`
- expiry detection
- transition guards for `pending`, `claimed`, `closed`, `expired`, `cancelled`

Keep Pi as the owner of writing `expired`.

- [ ] **Step 5: Implement transaction payload shaping**

Add `sasta_dmart/transactions.py` helpers for:

- line total calculation
- bill ID generation
- transaction payload shaping

- [ ] **Step 6: Implement Firebase helper module**

Create `sasta_dmart/firebase.py` to centralize Admin SDK initialization and database reference access.

- [ ] **Step 7: Run tests to verify the domain helpers pass**

Run: `pytest tests/test_sessions.py tests/test_transactions.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add sasta_dmart/firebase.py sasta_dmart/sessions.py sasta_dmart/transactions.py \
  tests/test_sessions.py tests/test_transactions.py
git commit -m "feat: add session and transaction domain helpers"
```

---

### Task 3: Refactor The Laptop Dashboard Into Templates And Lean Flask App Code

**Files:**
- Create: `sasta_dmart/portal/__init__.py`
- Create: `sasta_dmart/portal/templates/base.html`
- Create: `sasta_dmart/portal/templates/dashboard.html`
- Create: `sasta_dmart/portal/static/portal.css`
- Create: `sasta_dmart/portal/static/portal.js`
- Test: `tests/test_portal_app.py`
- Modify: `laptop_firebase_portal.py`

- [ ] **Step 1: Write the failing Flask route tests**

```python
from laptop_firebase_portal import app


def test_dashboard_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Retail Ledger" in res.data


def test_transactions_api_returns_json(client):
    res = client.get("/api/transactions")
    assert res.status_code == 200
    assert res.is_json
```

- [ ] **Step 2: Run tests to verify they fail against the current structure**

Run: `pytest tests/test_portal_app.py -v`
Expected: FAIL because no reusable test client/setup exists yet, or HTML expectations do not match

- [ ] **Step 3: Create a lean portal package**

Move Flask UI concerns into `sasta_dmart/portal/__init__.py` with a small app factory or route registration helper, but keep `laptop_firebase_portal.py` as the runnable top-level entrypoint.

- [ ] **Step 4: Replace inline HTML with templates and static assets**

Build:

- premium, elegant, lightly playful dashboard
- proper loading, empty, and error states
- clear distinction between public claim URL and local dashboard role

Keep motion subtle and stateful.

- [ ] **Step 5: Preserve and improve API endpoints**

Keep or improve:

- `/api/transactions`
- `/api/all-bills` compatibility if still needed
- `/api/portal-info`

Add only diagnostics that help the dashboard. Do not reintroduce phone auth responsibilities.

- [ ] **Step 6: Run tests to verify portal behavior**

Run: `pytest tests/test_portal_app.py -v`
Expected: PASS

- [ ] **Step 7: Smoke test the dashboard locally**

Run: `python laptop_firebase_portal.py`
Expected: app starts cleanly with explicit config validation and serves the styled dashboard

- [ ] **Step 8: Commit**

```bash
git add laptop_firebase_portal.py sasta_dmart/portal/__init__.py \
  sasta_dmart/portal/templates/base.html sasta_dmart/portal/templates/dashboard.html \
  sasta_dmart/portal/static/portal.css sasta_dmart/portal/static/portal.js \
  tests/test_portal_app.py
git commit -m "feat: refactor laptop dashboard into templates"
```

---

### Task 4: Refactor The Pi Runtime Around Explicit Session Logic And Stronger UI States

**Files:**
- Modify: `pi_checkout_gui_firebase.py`
- Modify: `sasta_dmart/sessions.py`
- Modify: `sasta_dmart/transactions.py`
- Test: `tests/test_sessions.py`

- [ ] **Step 1: Extend the failing session tests for Pi-specific recovery**

```python
from sasta_dmart.sessions import expire_session_record


def test_expire_session_record_preserves_claimed_session():
    record = {"status": "claimed"}
    assert expire_session_record(record)["status"] == "claimed"


def test_expire_session_record_transitions_pending_to_expired():
    record = {"status": "pending"}
    assert expire_session_record(record)["status"] == "expired"
```

- [ ] **Step 2: Run tests to verify any new cases fail**

Run: `pytest tests/test_sessions.py -v`
Expected: FAIL until helper coverage is expanded

- [ ] **Step 3: Update Pi session creation and polling**

Use `sasta_dmart/sessions.py` from the Pi script so that:

- QR always uses `PUBLIC_CLAIM_BASE_URL`
- session records always include `status`, `created_at`, `expires_at`, `pi_node`, `claimed_by`, `claimed_at`, and optional `claim_url`
- Pi owns expiry writes
- polling handles `pending`, `claimed`, `expired`, `closed`, and `cancelled`

- [ ] **Step 4: Modernize the Pi UI without changing the runtime model**

Improve:

- layout hierarchy
- QR/session card prominence
- cart readability
- scan/login/bill state clarity
- tasteful motion-like feedback through Tkinter state updates

Do not rewrite the Pi runtime into a browser app.

- [ ] **Step 5: Handle Firebase failures explicitly**

Add human-readable UI states for:

- claim polling failure
- bill write failure
- recovery after expired session

- [ ] **Step 6: Run tests to verify helper behavior**

Run: `pytest tests/test_sessions.py tests/test_transactions.py -v`
Expected: PASS

- [ ] **Step 7: Manual Pi smoke test**

Run on Pi: `python3 pi_checkout_gui_firebase.py`
Expected: app starts, shows polished UI, creates login session, and recovers cleanly after expiry or failed poll

- [ ] **Step 8: Commit**

```bash
git add pi_checkout_gui_firebase.py sasta_dmart/sessions.py sasta_dmart/transactions.py tests/test_sessions.py
git commit -m "feat: improve pi session handling and ui states"
```

---

### Task 5: Build The Hosted Claim Surface With Atomic One-Time Claim

**Files:**
- Create: `public_claim/index.html`
- Create: `public_claim/styles.css`
- Create: `public_claim/app.js`
- Create: `public_claim/build_config.py`
- Create: `public_claim/config.template.js`
- Create: `public_claim/README.md`
- Test: `tests/test_public_claim_build.py`

- [ ] **Step 1: Write the failing config-build test**

```python
from pathlib import Path
from public_claim.build_config import render_config


def test_render_config_requires_firebase_keys(tmp_path):
    with pytest.raises(RuntimeError, match="FIREBASE_WEB_API_KEY"):
        render_config({}, tmp_path / "config.js")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_claim_build.py -v`
Expected: FAIL with missing module/function

- [ ] **Step 3: Implement the tiny hosted-config build step**

Create `public_claim/build_config.py` that reads env vars and writes generated `public_claim/config.js` from `config.template.js`.

This keeps the site plain static HTML/CSS/JS while still supporting env-driven deployment on Cloudflare Pages.

- [ ] **Step 4: Build the hosted claim UI**

Implement a minimal mobile-first page that:

- reads `token` from query params
- signs in with Firebase Google auth
- rejects missing/invalid tokens
- explains success/failure clearly

- [ ] **Step 5: Implement atomic one-time claim**

Use Firebase Realtime Database client transaction logic in `public_claim/app.js` so that:

- only one claimant succeeds
- already-claimed sessions fail cleanly
- expired sessions fail cleanly
- only allowed fields are written for `pending -> claimed`

If this cannot be made correct, stop and switch to the minimal hosted/serverless fallback instead of weakening the claim flow.

- [ ] **Step 6: Smoke test the hosted claim build**

Run:

```bash
python public_claim/build_config.py
python -m http.server 4173 --directory public_claim
```

Expected: generated config exists and the claim page loads locally for manual Firebase-connected testing

- [ ] **Step 7: Commit**

```bash
git add public_claim/index.html public_claim/styles.css public_claim/app.js \
  public_claim/build_config.py public_claim/config.template.js public_claim/README.md \
  tests/test_public_claim_build.py
git commit -m "feat: add hosted public claim flow"
```

---

### Task 6: Docs, Firebase Rules, Cleanup, And Secret Removal

**Files:**
- Modify: `README.md`
- Create: `docs/firebase-rtdb-rules.json`
- Modify: `.gitignore`
- Delete if obsolete: `pi_checkout_gui.py`
- Delete if obsolete: `laptop_bill_server.py`
- Delete if obsolete: `received_bills.json`
- Remove from tracking: `sasta-dmart-firebase-adminsdk-fbsvc-708b9680b3.json`

- [ ] **Step 1: Write the Firebase rules file**

Create `docs/firebase-rtdb-rules.json` with the exact RTDB rule shape documented for the hosted claim path.

- [ ] **Step 2: Rewrite the README around the final architecture**

Document:

- Pi runtime
- laptop dashboard
- hosted claim page
- env vars
- Firebase Console steps
- Cloudflare deployment steps
- QR troubleshooting
- key rotation note if the service-account JSON was ever pushed publicly

- [ ] **Step 3: Remove dead legacy artifacts only after confirming they are unused**

Delete:

- `pi_checkout_gui.py`
- `laptop_bill_server.py`
- `received_bills.json`

only if no runtime/docs still depend on them.

- [ ] **Step 4: Remove the tracked service-account JSON from git**

Run:

```bash
git rm --cached sasta-dmart-firebase-adminsdk-fbsvc-708b9680b3.json
```

Leave the local file alone if needed for testing, but remove it from tracking and block it in `.gitignore`.

- [ ] **Step 5: Review repo status for stragglers**

Run: `git status --short`
Expected: no secrets staged accidentally and only intended cleanup/docs changes remain

- [ ] **Step 6: Commit**

```bash
git add README.md docs/firebase-rtdb-rules.json .gitignore
git add -u
git commit -m "docs: add setup guide and remove legacy tracked secrets"
```

---

### Task 7: End-To-End Verification, Git Hygiene, And Push

**Files:**
- Modify: `docs/superpowers/specs/2026-04-12-sasta-dmart-smart-checkout-design.md` only if implementation reality forces a design note
- Modify: `docs/superpowers/plans/2026-04-12-sasta-dmart-smart-checkout-modernization.md` only to check off items during execution

- [ ] **Step 1: Run the automated test suite**

Run: `pytest tests -v`
Expected: PASS

- [ ] **Step 2: Verify laptop startup**

Run: `python laptop_firebase_portal.py`
Expected: explicit config validation, clean startup, styled dashboard, working `/api/transactions`

- [ ] **Step 3: Verify anonymous checkout**

Manual flow:

1. start Pi app
2. choose anonymous session
3. scan at least one item
4. generate bill

Expected: transaction saved to Firebase and visible in laptop dashboard

- [ ] **Step 4: Verify QR login claim flow**

Manual flow:

1. start Pi login session
2. scan QR on phone
3. sign in on hosted claim page
4. claim session
5. confirm Pi transitions to logged-in
6. generate bill

Expected: `pending -> claimed -> closed` with one-time claim semantics

- [ ] **Step 5: Verify rejection scenarios**

Manual checks:

- expired token rejection
- already-claimed token rejection
- Pi recovery after failed or expired claim attempt
- network failure during Pi polling
- network failure during bill write

- [ ] **Step 6: Inspect git diff and commit history**

Run:

```bash
git status --short
git log --oneline --decorate -10
```

Expected: no unintended files or secrets, coherent commit history

- [ ] **Step 7: Push to GitHub**

Run: `git push`
Expected: remote updated successfully

---

## Inline Plan Review

**Status:** Approved

**Issues (if any):**
- None blocking

**Recommendations (advisory, do not block approval):**
- During implementation, prefer reusing helper logic in `sasta_dmart/sessions.py` instead of duplicating expiry/claimability checks across Pi and laptop code.
- If the direct RTDB transaction path feels rule-heavy during execution, switch to the minimal hosted/serverless claim fallback early rather than forcing a brittle client-only claim implementation.
