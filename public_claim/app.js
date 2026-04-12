import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import { getAuth, GoogleAuthProvider, getRedirectResult, signInWithPopup, signInWithRedirect } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js";
import { getDatabase, get, ref, runTransaction } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-database.js";


const config = window.PUBLIC_CLAIM_CONFIG;
if (!config) {
  throw new Error("Missing PUBLIC_CLAIM_CONFIG. Generate public_claim/config.js first.");
}

const token = new URL(window.location.href).searchParams.get("token");
const firebaseApp = initializeApp(config);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();
const database = getDatabase(firebaseApp);

const tokenText = document.getElementById("tokenText");
const sessionState = document.getElementById("sessionState");
const userText = document.getElementById("userText");
const statusText = document.getElementById("statusText");
const statusPanel = document.getElementById("statusPanel");
const signInBtn = document.getElementById("signInBtn");
const claimBtn = document.getElementById("claimBtn");

let currentUser = null;
let latestSession = null;


function setPanel(message, variant = "idle") {
  statusPanel.textContent = message;
  statusPanel.className = `status-panel status-${variant}`;
}


function setSessionBadge(message) {
  sessionState.textContent = message;
}


function isExpired(expiresAt) {
  if (!expiresAt) {
    return true;
  }
  return new Date(expiresAt).getTime() < Date.now();
}


function isExpiredSession(session) {
  if (!session) {
    return true;
  }
  if (typeof session.expires_at_ms === "number") {
    return session.expires_at_ms < Date.now();
  }
  return isExpired(session.expires_at);
}


function isClaimable(session) {
  return Boolean(
    session &&
    session.status === "pending" &&
    !session.claimed_by &&
    !isExpiredSession(session)
  );
}


async function loadSession() {
  if (!token) {
    tokenText.textContent = "Missing token";
    setSessionBadge("Invalid link");
    statusText.textContent = "No token in URL";
    setPanel("This link is missing a session token. Scan the QR code again from the Pi.", "error");
    return null;
  }

  const snapshot = await get(ref(database, `login_sessions/${token}`));
  latestSession = snapshot.val();

  if (!latestSession) {
    setSessionBadge("Not found");
    statusText.textContent = "Session not found";
    setPanel("This session token no longer exists. Start a new login session on the Pi.", "error");
    return null;
  }

  if (latestSession.status === "claimed" || latestSession.status === "closed") {
    setSessionBadge("Already used");
    statusText.textContent = "Session already claimed";
    setPanel("This session has already been claimed. Return to the Pi and start a fresh login flow if needed.", "error");
    return latestSession;
  }

  if (latestSession.status === "expired" || isExpiredSession(latestSession)) {
    setSessionBadge("Expired");
    statusText.textContent = "Session expired";
    setPanel("This session has expired. Return to the Pi and create a new login session.", "error");
    return latestSession;
  }

  setSessionBadge("Ready");
  statusText.textContent = "Session is claimable";
  setPanel("Session is valid. Sign in with Google, then claim it once.", "idle");
  return latestSession;
}


function updateUser(user) {
  currentUser = user;
  userText.textContent = user ? (user.email || user.displayName || "Signed in") : "Not signed in";
  claimBtn.disabled = !(user && isClaimable(latestSession));
}


async function tryClaim() {
  if (!currentUser || !token) {
    return;
  }

  const sessionRef = ref(database, `login_sessions/${token}`);
  let blockedReason = "Session is no longer claimable.";

  const result = await runTransaction(sessionRef, (current) => {
    if (!current) {
      blockedReason = "This session no longer exists.";
      return;
    }
    if (current.status !== "pending") {
      blockedReason = `This session is ${current.status}.`;
      return;
    }
    if (current.claimed_by) {
      blockedReason = "This session has already been claimed.";
      return;
    }
    if (isExpired(current.expires_at)) {
      blockedReason = "This session has expired.";
      return;
    }

    return {
      ...current,
      status: "claimed",
      claimed_by: {
        uid: currentUser.uid,
        email: currentUser.email || null,
        name: currentUser.displayName || null,
      },
      claimed_at: new Date().toISOString(),
    };
  });

  if (!result.committed) {
    setSessionBadge("Rejected");
    statusText.textContent = blockedReason;
    setPanel(blockedReason, "error");
    latestSession = result.snapshot?.val() || latestSession;
    claimBtn.disabled = true;
    return;
  }

  latestSession = result.snapshot.val();
  setSessionBadge("Claimed");
  statusText.textContent = "Session attached successfully";
  setPanel("Checkout session claimed successfully. You can return to the Pi now.", "success");
  claimBtn.disabled = true;
}


async function handleRedirectResult() {
  try {
    const result = await getRedirectResult(auth);
    if (result?.user) {
      updateUser(result.user);
      await loadSession();
      setPanel("Signed in successfully. You can claim the session now.", "idle");
    }
  } catch (error) {
    setPanel(`Google sign-in failed: ${error.message}`, "error");
  }
}


signInBtn.addEventListener("click", async () => {
  try {
    const result = await signInWithPopup(auth, provider);
    updateUser(result.user);
    await loadSession();
    setPanel("Signed in successfully. You can claim the session now.", "idle");
  } catch (error) {
    const code = String(error?.code || "");
    if (code.includes("popup") || code.includes("operation-not-supported")) {
      await signInWithRedirect(auth, provider);
      return;
    }
    setPanel(`Google sign-in failed: ${error.message}`, "error");
  }
});


claimBtn.addEventListener("click", async () => {
  try {
    await tryClaim();
  } catch (error) {
    setPanel(`Claim failed: ${error.message}`, "error");
  }
});


window.addEventListener("DOMContentLoaded", async () => {
  try {
    if (!token) {
      await loadSession();
      return;
    }

    tokenText.textContent = `${token.slice(0, 8)}…`;
    setSessionBadge("Sign in first");
    statusText.textContent = "Authenticate to verify this token";
    setPanel("Sign in with Google to verify and claim this checkout session.", "idle");

    await handleRedirectResult();
    claimBtn.disabled = !(currentUser && isClaimable(latestSession));
  } catch (error) {
    setSessionBadge("Error");
    statusText.textContent = "Could not verify session";
    setPanel(`Could not load this session: ${error.message}`, "error");
  }
});
