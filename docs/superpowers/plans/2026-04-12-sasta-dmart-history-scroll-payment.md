# Sasta Dmart History, Scrollable Cart, And Payment Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add customer purchase history on `history.html`, make the Pi cart list scrollable, and require Cash/Card payment selection before saving a purchase.

**Architecture:** Keep `transactions/<push-id>` as the source-of-truth purchase record and add a mirrored `customer_transactions/<uid>/<push-id>` read model for signed-in customers only. Reuse the current hosted static claim domain for customer history, keep the laptop portal operator-only, and keep the Pi runtime in Tkinter with narrowly scoped UI changes.

**Tech Stack:** Python, Tkinter, Flask, Firebase Admin SDK, Firebase Realtime Database, Firebase Web Auth, static HTML/CSS/JS, pytest, Node `--test`

---

## File Map

### Domain helpers and persistence shape

- Modify: `sasta_dmart/transactions.py`
- Modify: `tests/test_transactions.py`

### Pi kiosk runtime

- Modify: `pi_checkout_gui_firebase.py`

### Laptop monitoring surface

- Modify: `sasta_dmart/portal/templates/dashboard.html`
- Modify: `sasta_dmart/portal/static/portal.js`
- Modify: `tests/conftest.py`
- Modify: `tests/test_portal_app.py`

### Hosted customer history surface

- Modify: `public_claim/index.html`
- Create: `public_claim/history.html`
- Create: `public_claim/history.js`
- Create: `public_claim/history_state.mjs`
- Modify: `public_claim/styles.css`
- Modify: `public_claim/README.md`
- Create: `tests/public_claim_history.test.mjs`

### Rules and top-level docs

- Modify: `docs/firebase-rtdb-rules.json`
- Modify: `README.md`

---

### Task 1: Extend Transaction Helpers For History Metadata And Atomic Writes

**Files:**
- Modify: `sasta_dmart/transactions.py`
- Modify: `tests/test_transactions.py`

- [ ] **Step 1: Write the failing transaction helper tests**

Add tests that lock down the new additive transaction shape and the atomic multi-location write map.

```python
from sasta_dmart.transactions import (
    build_customer_history_record,
    build_transaction_payload,
    build_transaction_write_map,
)


def test_build_transaction_payload_adds_sort_and_summary_fields():
    payload = build_transaction_payload(
        cart_items=[
            {"product_id": "00001", "name": "Apple", "qty": 2, "unit_price": 44.0, "barcode": "2700001044007"},
            {"product_id": "00002", "name": "Banana", "qty": 1, "unit_price": 22.5, "barcode": "2700002022507"},
        ],
        session_type="logged_in",
        customer={"uid": "u1", "email": "user@example.com", "name": "Aarav Shah"},
        pi_node="pi-front-counter",
        now_utc="2026-04-12T14:25:30+00:00",
        bill_suffix="AB12CD",
    )
    assert payload["generated_at_ms"] == 1776003930000
    assert payload["item_count"] == 3
    assert payload["item_summary"] == "Apple x2, Banana x1"
    assert "payment_type" not in payload


def test_build_transaction_write_map_writes_source_and_customer_mirror_atomically():
    payload = {
        "bill_id": "BILL-20260412-142530-AB12CD",
        "generated_at": "2026-04-12T14:25:30+00:00",
        "generated_at_ms": 1776003930000,
        "session_type": "logged_in",
        "customer": {"uid": "u1", "email": "user@example.com", "name": "Aarav Shah"},
        "items": [{"name": "Apple", "qty": 2, "unit_price": 44.0, "line_total": 88.0, "barcode": "2700001044007", "product_id": "00001"}],
        "total": 88.0,
        "pi_node": "pi-front-counter",
        "item_count": 2,
        "item_summary": "Apple x2",
        "payment_type": "card",
    }

    updates = build_transaction_write_map(transaction_id="-OXYZ123", transaction=payload)

    assert updates["transactions/-OXYZ123"]["payment_type"] == "card"
    assert updates["customer_transactions/u1/-OXYZ123"]["transaction_id"] == "-OXYZ123"
    assert updates["customer_transactions/u1/-OXYZ123"]["generated_at_ms"] == payload["generated_at_ms"]


def test_build_transaction_write_map_for_anonymous_checkout_skips_customer_history():
    payload = {
        "bill_id": "BILL-20260412-142530-CD34EF",
        "generated_at": "2026-04-12T14:25:30+00:00",
        "generated_at_ms": 1776003930000,
        "session_type": "anonymous",
        "customer": {"uid": None, "email": None, "name": "Anonymous"},
        "items": [],
        "total": 22.5,
        "pi_node": "pi-front-counter",
        "item_count": 1,
        "item_summary": "Banana x1",
        "payment_type": "cash",
    }

    updates = build_transaction_write_map(transaction_id="-OXYZ124", transaction=payload)

    assert list(updates.keys()) == ["transactions/-OXYZ124"]
```

- [ ] **Step 2: Run the focused transaction tests to verify failure**

Run: `pytest tests/test_transactions.py -v`
Expected: FAIL with missing helper functions or missing metadata fields.

- [ ] **Step 3: Implement the smallest helper additions**

Update `sasta_dmart/transactions.py` to:

- keep `build_transaction_payload()` responsible for computing `generated_at`, `generated_at_ms`, `item_count`, and `item_summary` exactly once
- leave `payment_type` out of the prepared payload so the Pi can add it after the operator chooses Cash/Card
- add `build_customer_history_record(transaction_id, transaction)` that copies the history-safe fields unchanged
- add `build_transaction_write_map(transaction_id, transaction)` that always writes `transactions/<push-id>` and conditionally writes `customer_transactions/<uid>/<push-id>`

Use small helpers rather than duplicating summary logic in the Pi or frontend.

- [ ] **Step 4: Run the focused transaction tests to verify pass**

Run: `pytest tests/test_transactions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sasta_dmart/transactions.py tests/test_transactions.py
git commit -m "feat: add transaction history metadata and atomic write helpers"
```

---

### Task 2: Surface Payment Type In The Laptop Portal

**Files:**
- Modify: `sasta_dmart/portal/templates/dashboard.html`
- Modify: `sasta_dmart/portal/static/portal.js`
- Modify: `tests/conftest.py`
- Modify: `tests/test_portal_app.py`

- [ ] **Step 1: Write the failing portal tests**

Extend the portal fixture data and assertions so the operator dashboard renders payment type from source-of-truth transactions.

```python
def test_dashboard_loads_payment_type_column(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Payment" in response.data
    assert b"card" in response.data


def test_transactions_api_still_returns_payment_type(client):
    response = client.get("/api/transactions")
    payload = response.get_json()
    assert payload["transactions"][0]["payment_type"] == "card"
```

- [ ] **Step 2: Run the portal tests to verify failure**

Run: `pytest tests/test_portal_app.py -v`
Expected: FAIL because the fixture data or rendered table does not yet include payment type.

- [ ] **Step 3: Implement the portal display change**

Update the seeded test fixture in `tests/conftest.py`, then add a Payment column to:

- `sasta_dmart/portal/templates/dashboard.html`
- `sasta_dmart/portal/static/portal.js`

Keep the portal operator-focused. Do not add customer-history links or auth logic here.

- [ ] **Step 4: Run the portal tests to verify pass**

Run: `pytest tests/test_portal_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sasta_dmart/portal/templates/dashboard.html sasta_dmart/portal/static/portal.js \
  tests/conftest.py tests/test_portal_app.py
git commit -m "feat: show payment type in portal transactions"
```

---

### Task 3: Update The Pi Checkout Flow For Scrollable Cart And Modal Payment Selection

**Files:**
- Modify: `pi_checkout_gui_firebase.py`
- Reuse: `sasta_dmart/transactions.py`

**Note:** Do not refactor the Pi app into a new UI framework or split it into new modules. Keep the changes inside the existing seams in `pi_checkout_gui_firebase.py`.

- [ ] **Step 1: Add the scrollable-cart UI change**

Inside `_build_right_panel()`:

- attach a vertical `ttk.Scrollbar` to `self.cart_tree`
- keep session controls and action buttons fixed above the cart
- bind mouse-wheel scrolling to the cart widget only

The cart area should remain the only scrollable region in the right column.

- [ ] **Step 2: Add the guarded modal payment dialog**

Implement a small `tk.Toplevel` payment dialog that:

- shows `bill_id`, customer label, total, and item count
- uses `transient(self.root)` and `grab_set()`
- disables the Cash/Card buttons while save is in flight
- ignores close attempts while save is in flight
- keeps the prepared payload alive across retry

Use a prepared payload from `build_transaction_payload(...)`, then on payment selection create:

```python
persisted_payload = {
    **prepared_payload,
    "payment_type": selected_payment_type,
}
```

- [ ] **Step 3: Replace the current direct push with one atomic Admin SDK update**

Change `generate_bill()` so it:

- allocates one push key from `db.reference("transactions").push().key`
- builds `updates = build_transaction_write_map(push_id, persisted_payload)`
- calls one root-level RTDB update, for example:

```python
db.reference("/").update(updates)
```

Only after that succeeds:

- close the login session if one exists
- clear the cart
- reset `session_mode`, `login_token`, `logged_in_user`, and QR state
- show success confirmation

On failure:

- leave dialog open
- leave cart/session unchanged
- re-enable the payment buttons for retry

- [ ] **Step 4: Run a syntax check before runtime smoke testing**

Run: `python -m py_compile pi_checkout_gui_firebase.py sasta_dmart/transactions.py`
Expected: no output and exit code `0`

- [ ] **Step 5: Perform focused manual Pi smoke testing**

Run the Pi app and verify:

- long carts scroll without hiding Generate Bill / Clear Cart
- Generate Bill opens the modal payment dialog
- Cash and Card both save correctly
- duplicate writes do not happen on fast repeated clicks
- failed saves leave cart and session intact for retry

Document any environment-specific Pi issues in the commit message or handoff notes; do not change architecture to work around them.

- [ ] **Step 6: Commit**

```bash
git add pi_checkout_gui_firebase.py sasta_dmart/transactions.py
git commit -m "feat: add modal payment selection and scrollable Pi cart"
```

---

### Task 4: Build The Hosted Purchase History Page And Rules

**Files:**
- Modify: `public_claim/index.html`
- Create: `public_claim/history.html`
- Create: `public_claim/history.js`
- Create: `public_claim/history_state.mjs`
- Modify: `public_claim/styles.css`
- Modify: `public_claim/README.md`
- Modify: `docs/firebase-rtdb-rules.json`
- Modify: `README.md`
- Create: `tests/public_claim_history.test.mjs`

- [ ] **Step 1: Write the failing history-page tests**

Create a small pure JS helper module so sorting and record normalization can be tested without a browser runtime.

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { normalizePurchaseHistory } from "../public_claim/history_state.mjs";

test("normalizePurchaseHistory sorts newest first and keeps line items", () => {
  const rows = normalizePurchaseHistory({
    a: { bill_id: "BILL-1", generated_at_ms: 10, items: [{ name: "Apple", qty: 1 }], payment_type: "cash" },
    b: { bill_id: "BILL-2", generated_at_ms: 20, items: [{ name: "Banana", qty: 2 }], payment_type: "card" },
  });

  assert.equal(rows[0].bill_id, "BILL-2");
  assert.equal(rows[0].payment_type, "card");
  assert.equal(rows[0].items[0].name, "Banana");
});
```

- [ ] **Step 2: Run the history-page tests to verify failure**

Run: `node --test tests/public_claim_history.test.mjs`
Expected: FAIL with missing module or missing exported function.

- [ ] **Step 3: Implement the hosted history surface**

Build the customer history page with these rules:

- `public_claim/index.html` stays claim-focused and gets only a small purchase-history link
- `public_claim/history.html` shows sign-in prompt when signed out
- `public_claim/history.html` shows a small Sign out action when signed in
- `public_claim/history.js` reuses the current Firebase config and auth flow
- reads come only from `customer_transactions/<auth.uid>`
- render newest first using `generated_at_ms`
- show bill id, timestamp, total, payment type, item count or summary
- allow simple expand/collapse for line items if `items` exist
- show a clean empty state if there are no rows

Keep the visual language aligned with the existing hosted claim surface. Do not merge the claim and history pages.

- [ ] **Step 4: Update Firebase rules and docs**

Modify `docs/firebase-rtdb-rules.json` so:

- `transactions` stays closed
- `portal_config` stays closed
- `customer_transactions/$uid/.read` allows only `auth != null && auth.uid == $uid`
- client writes to `customer_transactions` remain blocked

Then update `README.md` and `public_claim/README.md` with:

- the new `history.html` page
- the Cloudflare redeploy reminder
- the required Firebase Rules update

- [ ] **Step 5: Run the hosted-page tests to verify pass**

Run: `node --test tests/public_claim_history.test.mjs tests/public_claim_state.test.mjs`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add public_claim/index.html public_claim/history.html public_claim/history.js public_claim/history_state.mjs \
  public_claim/styles.css public_claim/README.md docs/firebase-rtdb-rules.json README.md \
  tests/public_claim_history.test.mjs
git commit -m "feat: add hosted customer purchase history page"
```

---

### Task 5: Run Combined Verification And Capture Manual Release Steps

**Files:**
- Review only: `pi_checkout_gui_firebase.py`
- Review only: `public_claim/`
- Review only: `docs/firebase-rtdb-rules.json`
- Review only: `README.md`

- [ ] **Step 1: Run the Python regression slice**

Run: `pytest tests/test_transactions.py tests/test_portal_app.py tests/test_public_claim_build.py -v`
Expected: PASS

- [ ] **Step 2: Run the JS regression slice**

Run: `node --test tests/public_claim_state.test.mjs tests/public_claim_history.test.mjs`
Expected: PASS

- [ ] **Step 3: Re-run syntax validation for the Pi entrypoint**

Run: `python -m py_compile pi_checkout_gui_firebase.py`
Expected: no output and exit code `0`

- [ ] **Step 4: Complete the explicit manual checklist**

Verify and record:

- QR claim on `public_claim/index.html` still works unchanged
- signed-in checkout writes `transactions/<push-id>` with `payment_type`, `generated_at_ms`, `item_count`, and `item_summary`
- signed-in checkout writes `customer_transactions/<uid>/<push-id>` with matching values
- anonymous checkout writes only `transactions/<push-id>`
- `history.html` shows only the signed-in user's purchases
- laptop portal shows payment type for recent transactions
- the Cloudflare static frontend requires a fresh Direct Upload deployment before customer-facing changes go live
- Firebase Rules must be updated before customer history reads will work in production

- [ ] **Step 5: Commit final polish if verification changed docs**

```bash
git status --short
```

Expected: no changes, or only intentional doc tweaks from the verification pass. Commit only if verification produced a real documentation correction.

