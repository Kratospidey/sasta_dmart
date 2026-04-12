export function isExpired(expiresAt) {
  if (!expiresAt) {
    return true;
  }
  return new Date(expiresAt).getTime() < Date.now();
}


export function isExpiredSession(session) {
  if (!session) {
    return true;
  }
  if (typeof session.expires_at_ms === "number") {
    return session.expires_at_ms < Date.now();
  }
  return isExpired(session.expires_at);
}


export function isClaimable(session) {
  return Boolean(
    session &&
    session.status === "pending" &&
    !session.claimed_by &&
    !isExpiredSession(session)
  );
}


export function shouldEnableClaimButton({ token, currentUser, session, isClaimInFlight }) {
  return Boolean(
    token &&
    currentUser &&
    isClaimable(session) &&
    !isClaimInFlight
  );
}


export function buildClaimTransactionUpdate({
  currentSession,
  fallbackSession,
  user,
  claimedAt,
}) {
  const baseSession = currentSession ?? fallbackSession ?? null;

  if (!baseSession) {
    return {
      allowed: false,
      message: "This session no longer exists.",
    };
  }

  if (baseSession.status !== "pending") {
    return {
      allowed: false,
      message: `This session is ${baseSession.status}.`,
    };
  }

  if (baseSession.claimed_by) {
    return {
      allowed: false,
      message: "This session has already been claimed.",
    };
  }

  if (isExpiredSession(baseSession)) {
    return {
      allowed: false,
      message: "This session has expired.",
    };
  }

  return {
    allowed: true,
    session: {
      ...baseSession,
      status: "claimed",
      claimed_by: {
        uid: user.uid,
        email: user.email || null,
        name: user.displayName || null,
      },
      claimed_at: claimedAt,
    },
  };
}


function normalizeErrorCode(error) {
  return String(error?.code || "").trim().toLowerCase();
}


export function describeClaimFailure({ blockedReason, postClaimSession, error }) {
  const errorCode = normalizeErrorCode(error);

  if (errorCode.includes("permission_denied") || errorCode.includes("permission-denied")) {
    return "Claim write was rejected by Firebase rules. Check RTDB permissions for login_sessions/<token>.";
  }

  if (errorCode.includes("aborted")) {
    return "Claim transaction was aborted before Firebase committed it. Please try again.";
  }

  if (errorCode.includes("network")) {
    return "Claim failed due to a network issue while writing to Firebase. Please try again.";
  }

  if (postClaimSession === null) {
    return "This session no longer exists.";
  }

  if (postClaimSession && postClaimSession.status === "claimed") {
    return "This session has already been claimed.";
  }

  if (postClaimSession && postClaimSession.status === "closed") {
    return "This session is closed.";
  }

  if (postClaimSession && (postClaimSession.status === "expired" || isExpiredSession(postClaimSession))) {
    return "This session has expired.";
  }

  if (postClaimSession && postClaimSession.status === "pending") {
    return "Claim did not complete. The session is still pending in Firebase.";
  }

  if (blockedReason && blockedReason !== "This session no longer exists.") {
    return blockedReason;
  }

  if (error?.message) {
    return `Claim failed: ${error.message}`;
  }

  return "Claim failed before Firebase updated the session. Please try again.";
}
