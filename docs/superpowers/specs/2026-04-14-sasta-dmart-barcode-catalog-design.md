# Sasta Dmart Barcode Reliability And Product Catalog Design

## Goal

Make a focused upgrade to the existing checkout demo without changing its overall architecture:

- improve barcode scanning reliability in the Pi runtime
- move product metadata out of hardcoded Pi code into an external catalog file
- add a standalone barcode generator that uses the same barcode rules
- verify that the laptop ledger already shows `payment_type`, keeping any change there additive only if needed

## Scope And Boundaries

This design is intentionally narrow.

Keep unchanged:

- `pi_checkout_gui_firebase.py` remains the Raspberry Pi checkout runtime
- `laptop_firebase_portal.py` remains the laptop/admin dashboard entrypoint
- Firebase transaction writes remain in the current flow
- QR claim/login behavior remains unchanged
- transaction persistence shape remains additive only

Do not do:

- a framework migration
- a Firebase schema redesign
- a new product database
- a broad refactor of the Pi UI
- a mixed-format barcode migration with legacy numeric labels kept alive

## Current Relevant Code Paths

### Pi scan path

`pi_checkout_gui_firebase.py` currently:

- decodes a frame with `pyzbar.decode(...)`
- reads only `decoded[0]`
- rejects the whole scan attempt if that first decoded candidate is junk or unsupported
- parses a numeric payload directly in `_handle_decoded_barcode(...)`
- resolves product names from a hardcoded `PRODUCT_LOOKUP` dict

This is the main reliability problem.

### Product metadata

The Pi runtime currently hardcodes product names in `PRODUCT_LOOKUP`.

This couples the kiosk runtime to product catalog edits and makes any new barcode generator more likely to duplicate product truth.

### Laptop/admin ledger

The current repo already shows `payment_type` in both:

- `sasta_dmart/portal/templates/dashboard.html`
- `sasta_dmart/portal/static/portal.js`

Task 4 should therefore be treated as verification-first. Only patch it if a real display path is found to still omit the field.

## Approved Architecture

The product catalog becomes the main source of truth:

- `sasta_dmart/products.json`

Each product entry will include at least:

- `product_id`
- `name`
- `default_price`
- optional `category`

The Pi app will load the catalog at startup and use it for metadata lookup only. The scanned barcode payload will still provide the transaction price used for the cart line item. Unknown product ids must remain non-fatal and render as:

- `Unknown (<product_id>)`

To avoid duplicating barcode rules across scripts, add small shared helpers under `sasta_dmart/` for:

- loading and indexing the catalog
- building barcode payloads
- parsing barcode payloads

This keeps the patch local and avoids turning the Pi script into the only place where barcode rules exist.

## Barcode Format Decision

Primary barcode format will be Code128-compatible text payloads only. Legacy numeric `27...` labels will not be kept as a supported scan format in this upgrade.

The primary payload format will be a short catalog-driven string such as:

- `SDM|pid=00001|price=60.00`

Rules:

- `SDM` is a constant prefix identifying Sasta Dmart demo labels
- `pid` is the product id string used to resolve metadata from `products.json`
- `price` is the transaction price encoded in decimal rupees

This keeps the runtime logic simple:

- barcodes carry the price
- the catalog carries the product metadata
- product names are not embedded as required runtime truth

Embedded-name mode is intentionally out of scope for this patch. It is optional future work, not part of the primary architecture.

## Pi Scanner Behavior

The scan loop in `pi_checkout_gui_firebase.py` will stay in its current location, but behavior changes as follows:

1. Decode all candidates in the frame.
2. Iterate candidates in order returned by `pyzbar`.
3. For each candidate:
   - log barcode type
   - log raw decoded payload
   - try to parse the supported `SDM|...` payload
   - reject malformed, unsupported, or incomplete values with a lightweight reason
4. Accept the first valid supported candidate.
5. Stop scanning only after one candidate is accepted into the cart.

Examples of rejection cases:

- undecodable bytes
- blank payload
- wrong prefix
- missing `pid`
- missing or non-numeric `price`

The status line should remain user-friendly, while debug logging can go to stdout with short, readable messages.

## Product Catalog Behavior

Add:

- `sasta_dmart/products.json`

Initial entries:

- `00001` -> Apple
- `00002` -> Bottle
- `00003` -> Bag

The catalog loader should:

- read the JSON file once at startup
- validate minimally that each row contains `product_id`, `name`, and `default_price`
- build a lookup keyed by `product_id`

If the catalog file cannot be loaded, the Pi runtime should fail early with a clear startup error rather than silently reverting to hardcoded data.

## Barcode Generator Design

Add a new standalone script:

- `generate_barcodes.py`

The generator will use the same shared payload builder as the Pi parser.

Minimum supported flows:

- generate one barcode from explicit CLI arguments
- save PNG output
- print the encoded payload

Recommended CLI examples:

- `python generate_barcodes.py --product-id 00001 --price 60.00`
- `python generate_barcodes.py --product-id 00001 --price 60.00 --name Apple`

Simple catalog-assisted flows are also in scope if they stay small:

- `python generate_barcodes.py --product-id 00001` using `default_price` from `products.json`
- `python generate_barcodes.py --all` to generate labels for every catalog entry

The generator should save to a predictable output folder, for example:

- `barcodes/`

Filenames should be readable, such as:

- `00001-apple-60_00.png`

The generator script may depend on a lightweight barcode library in addition to Pillow if needed to emit Code128 PNG files reliably.

## Payment Type Verification

Task 4 is verification-first.

The implementation phase should confirm that:

- server-rendered dashboard rows show `payment_type`
- live-refresh rows from `portal.js` show `payment_type`
- missing values display `-`

Only add a patch if one of those paths is inconsistent.

## Testing Strategy

Focus tests on the new logic, not camera hardware.

Add or update tests for:

- catalog loading and lookup
- barcode payload build/parse success cases
- barcode payload rejection cases
- first-valid-candidate selection after junk candidates
- unknown product fallback naming
- generator helper behavior if factored into testable functions
- portal verification that `payment_type` remains present with `-` fallback when absent

Manual testing should cover:

- scanning a valid generated Code128 label
- scanning with junk plus one valid label in view
- scanning an unknown product id
- generating one barcode from CLI
- generating catalog-backed barcode output
- confirming dashboard payment type display with both present and missing values

## Files Expected To Change

Primary expected changes:

- Modify: `pi_checkout_gui_firebase.py`
- Create: `sasta_dmart/products.json`
- Create: small shared helper module(s) under `sasta_dmart/` for catalog and barcode parsing/building
- Create: `generate_barcodes.py`
- Modify: tests covering the new shared logic and any verified portal behavior

Conditional only if verification finds a gap:

- Modify: `sasta_dmart/portal/templates/dashboard.html`
- Modify: `sasta_dmart/portal/static/portal.js`

## Risks And Caveats

- Code128 generation may require adding a new Python dependency for the generator environment.
- `pyzbar` returns symbol types and payloads based on camera quality and print quality; the parser should therefore be strict about format but tolerant about seeing junk candidates in the same frame.
- Code128 labels are text-capable, but this design intentionally keeps names out of the required payload so the catalog remains the single metadata source of truth.
- Because legacy numeric labels are being dropped, existing old-format demo labels will need to be regenerated before manual Pi testing.
