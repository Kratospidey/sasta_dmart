# Sasta Dmart Customer History, Scrollable Cart, And Payment Selection Design

## Goal

Add three focused improvements without changing the current architecture:

- a standalone customer purchase history page on the hosted claim domain
- a scrollable right-side cart area in the Pi Tkinter UI
- payment method selection after bill generation, with the selected payment type saved in Firebase

## Scope And Boundaries

This design is intentionally narrow.

Keep unchanged:

- `pi_checkout_gui_firebase.py` remains the checkout kiosk runtime
- `laptop_firebase_portal.py` remains the operator monitoring/dashboard surface
- `public_claim/index.html` remains the QR claim surface
- the phone QR claim flow remains separate from purchase history
- no real payment gateway logic is introduced

Do not do:

- a Tkinter rewrite
- a new backend service for customer history
- a move of customer history into the laptop portal
- a schema redesign beyond the additive fields needed for these features

## Current Relevant Code Paths

### Source-of-truth purchase records

- Completed purchases are currently written under `transactions/<push-id>`.
- The write happens in `pi_checkout_gui_firebase.py` inside `generate_bill()`.
- The transaction payload is currently shaped by `sasta_dmart/transactions.py::build_transaction_payload()`.

### User linkage

- The phone claim flow writes claimed user identity into `login_sessions/<token>.claimed_by`.
- The Pi polling flow copies `claimed_by` into `self.logged_in_user`.
- When a logged-in bill is generated, `build_transaction_payload()` receives that user object as `customer`.
- The current ownership field on purchase records is therefore `transactions/<push-id>/customer/uid`.
- Existing signed-in source records therefore already contain the identity needed for per-user ownership filtering.
- What is missing today is a safe customer-readable branch and rules model for exposing that history to the signed-in user.

### Pi cart rendering

- The right-side UI is built inside `pi_checkout_gui_firebase.py::_build_right_panel()`.
- The cart list is a `ttk.Treeview` stored as `self.cart_tree`.
- The cart content is refreshed through `refresh_cart_view()`.

### Bill generation flow

- `pi_checkout_gui_firebase.py::generate_bill()` validates session/cart state, builds the payload, writes to `transactions`, then clears cart/session state.
- Login sessions are closed after a successful bill save via `close_session_record()`.

### Hosted claim frontend

- `public_claim/index.html` and `public_claim/app.js` are the existing customer-facing QR claim surface.
- The claim page already uses Firebase Web Auth and RTDB.

### Laptop monitoring

- The laptop portal reads from `transactions` only.
- The table rendering lives in `sasta_dmart/portal/templates/dashboard.html` and `sasta_dmart/portal/static/portal.js`.

## Approved Architecture

The architecture split remains exactly as it is today:

- Pi kiosk owns checkout flow and purchase writes
- hosted static claim domain owns customer-facing auth and history
- laptop portal owns operator monitoring only

Customer history is implemented as a second hosted static page:

- `public_claim/history.html`

The claim page remains separate and claim-focused. It may include only a small optional link to purchase history.

## Data Model Changes

### Source-of-truth transaction record

Keep `transactions/<push-id>` as the canonical purchase record.

Add the following fields to each completed transaction:

- `payment_type`: `"cash"` or `"card"`
- `item_count`: integer total quantity across all scanned items
- `item_summary`: short customer-friendly summary for list views
- `generated_at_ms`: numeric UTC timestamp in milliseconds for stable ordering

Existing fields remain in place, including:

- `bill_id`
- `generated_at`
- `session_type`
- `customer`
- `items`
- `total`
- `pi_node`

The following derived fields must be computed once before persistence and then copied unchanged into both the source-of-truth record and the mirrored customer record:

- `generated_at`
- `generated_at_ms`
- `item_count`
- `item_summary`

### Mirrored customer history record

For signed-in purchases only, also write a mirrored record under:

- `customer_transactions/<uid>/<push-id>`

This mirrored record is the customer-facing read model for `history.html`.

It should remain history-focused and additive, not a redesign of the primary schema.

Recommended fields:

- `transaction_id` containing the Firebase `push-id`
- `bill_id`
- `generated_at`
- `generated_at_ms`
- `total`
- `payment_type`
- `item_count`
- `item_summary`
- `pi_node`
- `customer`
- `items`

Anonymous purchases must not create a `customer_transactions` mirror.

### Ownership rule

Ownership is keyed by:

- `customer.uid`

`customer.email` can be stored and displayed, but it is not the access-control key.

## Task 1 Design: Standalone Customer Purchase History

### Page structure

Add a standalone page:

- `public_claim/history.html`

Add a companion module:

- `public_claim/history.js`

Optional small UX addition:

- a lightweight link or button from `public_claim/index.html` to `history.html`
- a small sign-out action on `history.html`

The claim page must remain focused on QR token claim and must not be merged with history browsing.

### Auth behavior

`history.html` reuses the same Firebase web config already used by the claim page.

If the visitor is not signed in:

- show a Google sign-in prompt

If the visitor is signed in:

- read only `customer_transactions/<auth.uid>`
- render purchases newest first using `generated_at_ms`

### UI behavior

Each purchase card/list row shows at least:

- bill id
- timestamp
- total
- payment type
- item count or item summary
- pi node if useful

Expandable detail is allowed and preferred when simple:

- clicking or tapping a purchase expands line items from the mirrored `items` field

If there are no purchases:

- show a clean empty state such as "No purchases found yet"

### Safety model

Do not expose broad reads on `transactions`.

Customer history reads come only from:

- `customer_transactions/<uid>`

This avoids making the customer page responsible for filtering a globally readable purchase table.

## Task 2 Design: Scrollable Right-Side Cart In The Pi UI

Keep the existing right-column layout intact in `pi_checkout_gui_firebase.py`.

Only the cart/items area becomes scrollable.

Implementation shape:

- keep session controls, action buttons, and status areas fixed in the right column
- attach a vertical `ttk.Scrollbar` directly to `self.cart_tree`
- bind mouse-wheel behavior to the cart widget only

Do not:

- make the whole window scroll
- make the entire right panel scroll
- refactor the right-side layout into a different UI structure

The goal is only to keep long carts usable while preserving current button visibility.

## Task 3 Design: Payment Type Selection After Bill Generation

### Flow

`generate_bill()` keeps its current validation role:

- require ready session
- block `login_pending`
- require at least one cart item

After validation, it builds the prepared bill payload first, but does not write it yet.

Then it opens a small Tkinter payment selection dialog using `tk.Toplevel`.

The dialog clearly shows:

- bill id
- customer label
- total
- item count

The dialog offers exactly two choices:

- `Cash`
- `Card`

The payment dialog must behave as a guarded modal:

- use `transient(...)`
- use `grab_set()`
- disable `Cash` and `Card` buttons while a save is in flight
- block or ignore dialog close while save is in flight
- re-enable retry only after a failed save

### Save behavior

On selection:

- set `payment_type` to `"cash"` or `"card"`
- build the final persisted payload once
- allocate one Firebase `push-id` for the transaction
- create one root-level RTDB multi-location update map
- always include `transactions/<push-id>`
- if `customer.uid` exists, also include `customer_transactions/<uid>/<push-id>`
- perform one atomic Admin SDK write for the full update map

For anonymous checkout, the same save flow is used, but the atomic update map contains only:

- `transactions/<push-id>`

Only after a successful write:

- close/end the login session as appropriate
- clear/reset cart and session state exactly once
- show success confirmation in the kiosk UI

Treat the purchase save as failed unless the full atomic multi-location update succeeds.

### Failure behavior

If the write fails:

- keep the payment dialog open
- keep the prepared bill state intact
- keep the cart intact
- keep the current session intact
- allow operator retry

Do not:

- write a half-finished transaction and patch it later
- clear the cart before persistence succeeds
- close the session before persistence succeeds

## Firebase Rules Changes

Keep these branches closed to client reads/writes:

- `transactions`
- `portal_config`

Keep login session rules focused on claim flow as they are now.

Add a new customer-owned branch:

- `customer_transactions/<uid>`

Rules intent:

- authenticated users can read only their own uid branch
- client writes remain blocked there
- Pi and laptop continue using Firebase Admin SDK for writes

This keeps the customer page production-sensible without broadening access to source-of-truth purchase data.

## Rendering And Ordering Details

Use both:

- `generated_at` for display
- `generated_at_ms` for stable sorting

Use additive summary helpers on both source-of-truth and mirrored records:

- `item_count`
- `item_summary`

That keeps both history and monitoring views cheap to render without requiring client recomputation from raw line items.

## Regression Expectations

The following existing flows must continue to work:

- QR claim flow on `public_claim/index.html`
- logged-in checkout on the Pi
- anonymous checkout on the Pi
- laptop monitoring portal transaction list

Anonymous checkout must still write only the source-of-truth transaction and must not create a customer history record.

## Testing Strategy

Add focused regression coverage where practical.

Python coverage:

- extend transaction payload tests for `payment_type`, `generated_at_ms`, `item_count`, and `item_summary`
- add helper tests for mirrored customer history record shaping if a helper is introduced
- extend portal tests so `payment_type` is surfaced in operator monitoring

Frontend/static coverage:

- add a small test around the hosted history page build or structure if practical
- keep existing claim-state coverage intact

Manual verification should cover:

- QR claim still works unchanged
- signed-in checkout writes `transactions/<push-id>` correctly
- signed-in checkout creates `customer_transactions/<uid>/<push-id>`
- `history.html` shows that signed-in user’s purchase only
- anonymous checkout still works and does not create customer history
- `payment_type` appears in DB and relevant UI surfaces
- the Pi cart becomes scrollable without hiding key buttons

## Deployment And Operations Notes

Because `public_claim/` changes are part of this work, a fresh Cloudflare Direct Upload deployment is required for customer-facing frontend changes to go live.

After implementation:

- redeploy the hosted static files for `public_claim/`
- update Firebase RTDB rules to include `customer_transactions/<uid>` read constraints

The Pi and laptop runtimes should not require architecture changes beyond pulling the updated code and using the existing config model.
