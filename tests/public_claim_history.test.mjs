import test from "node:test";
import assert from "node:assert/strict";

import { normalizePurchaseHistory } from "../public_claim/history_state.mjs";


test("normalizePurchaseHistory sorts newest first and keeps line items", () => {
  const rows = normalizePurchaseHistory({
    a: {
      bill_id: "BILL-1",
      generated_at_ms: 10,
      items: [{ name: "Apple", qty: 1 }],
      payment_type: "cash",
    },
    b: {
      bill_id: "BILL-2",
      generated_at_ms: 20,
      items: [{ name: "Banana", qty: 2 }],
      payment_type: "card",
    },
  });

  assert.equal(rows[0].bill_id, "BILL-2");
  assert.equal(rows[0].payment_type, "card");
  assert.equal(rows[0].items[0].name, "Banana");
});
