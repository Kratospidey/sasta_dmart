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
