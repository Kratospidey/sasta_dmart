import test from "node:test";
import assert from "node:assert/strict";

import { shouldEnableClaimButton } from "../public_claim/claim_state.mjs";


const claimableSession = {
  status: "pending",
  claimed_by: null,
  expires_at_ms: Date.now() + 60_000,
};


test("claim button enables once a signed-in user and claimable session both exist", () => {
  const baseState = {
    token: "token-123",
    currentUser: null,
    session: claimableSession,
    isClaimInFlight: false,
  };

  assert.equal(shouldEnableClaimButton(baseState), false);
  assert.equal(
    shouldEnableClaimButton({
      ...baseState,
      currentUser: { uid: "user-1", email: "person@example.com" },
    }),
    true,
  );
});


test("claim button disables while a claim request is in flight", () => {
  assert.equal(
    shouldEnableClaimButton({
      token: "token-123",
      currentUser: { uid: "user-1" },
      session: claimableSession,
      isClaimInFlight: true,
    }),
    false,
  );
});


test("claim button stays disabled for missing token or unclaimable session", () => {
  assert.equal(
    shouldEnableClaimButton({
      token: null,
      currentUser: { uid: "user-1" },
      session: claimableSession,
      isClaimInFlight: false,
    }),
    false,
  );

  assert.equal(
    shouldEnableClaimButton({
      token: "token-123",
      currentUser: { uid: "user-1" },
      session: { ...claimableSession, status: "claimed" },
      isClaimInFlight: false,
    }),
    false,
  );
});
