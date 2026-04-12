import test from "node:test";
import assert from "node:assert/strict";

import {
  buildClaimTransactionUpdate,
  describeClaimFailure,
  shouldEnableClaimButton,
} from "../public_claim/claim_state.mjs";


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


test("claim transaction falls back to the verified session when local transaction state is null", () => {
  const decision = buildClaimTransactionUpdate({
    currentSession: null,
    fallbackSession: claimableSession,
    user: {
      uid: "user-1",
      email: "person@example.com",
      displayName: "Person Example",
    },
    claimedAt: "2026-04-13T12:00:00.000Z",
  });

  assert.equal(decision.allowed, true);
  assert.equal(decision.session.status, "claimed");
  assert.equal(decision.session.claimed_by.uid, "user-1");
  assert.equal(decision.session.claimed_at, "2026-04-13T12:00:00.000Z");
});


test("missing-session message is only used when the post-claim re-read is actually missing", () => {
  assert.equal(
    describeClaimFailure({
      blockedReason: "This session no longer exists.",
      postClaimSession: null,
      error: null,
    }),
    "This session no longer exists.",
  );

  assert.equal(
    describeClaimFailure({
      blockedReason: "This session no longer exists.",
      postClaimSession: claimableSession,
      error: null,
    }),
    "Claim did not complete. The session is still pending in Firebase.",
  );
});


test("permission and aborted transaction failures get distinct messages", () => {
  assert.equal(
    describeClaimFailure({
      blockedReason: "Session is no longer claimable.",
      postClaimSession: claimableSession,
      error: { code: "PERMISSION_DENIED", message: "permission denied" },
    }),
    "Claim write was rejected by Firebase rules. Check RTDB permissions for login_sessions/<token>.",
  );

  assert.equal(
    describeClaimFailure({
      blockedReason: "Session is no longer claimable.",
      postClaimSession: claimableSession,
      error: { code: "databse/aborted", message: "transaction aborted" },
    }),
    "Claim transaction was aborted before Firebase committed it. Please try again.",
  );
});
