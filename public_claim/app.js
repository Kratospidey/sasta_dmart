import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import { getAuth, GoogleAuthProvider, getRedirectResult, onAuthStateChanged, signInWithPopup, signInWithRedirect } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js";
import { getDatabase, get, ref, runTransaction } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-database.js";
import { isClaimable, isExpiredSession, shouldEnableClaimButton } from "./claim_state.mjs";


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
let isClaimInFlight = false;


function setPanel(message, variant = "idle") {
  statusPanel.textContent = message;
  statusPanel.className = `status-panel status-${variant}`;
}


function setSessionBadge(message) {
  sessionState.textContent = message;
}


function syncClaimButtonState() {
  claimBtn.disabled = !shouldEnableClaimButton({
    token,
    currentUser,
    session: latestSession,
    isClaimInFlight,
  });
}


async function loadSession() {
  latestSession = null;

  try {
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
  } finally {
    syncClaimButtonState();
  }
}


function updateUser(user) {
  currentUser = user;
  userText.textContent = user ? (user.email || user.displayName || "Signed in") : "Not signed in";
  syncClaimButtonState();
}


async function tryClaim() {
  if (!shouldEnableClaimButton({
    token,
    currentUser,
    session: latestSession,
    isClaimInFlight,
  })) {
    return;
  }

  isClaimInFlight = true;
  syncClaimButtonState();

  const sessionRef = ref(database, `login_sessions/${token}`);
  let blockedReason = "Session is no longer claimable.";

  try {
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
      if (isExpiredSession(current)) {
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
      latestSession = result.snapshot?.val() || null;
      return;
    }

    latestSession = result.snapshot.val();
    setSessionBadge("Claimed");
    statusText.textContent = "Session attached successfully";
    setPanel("Checkout session claimed successfully. You can return to the Pi now.", "success");
  } finally {
    isClaimInFlight = false;
    syncClaimButtonState();
  }
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


onAuthStateChanged(auth, async (user) => {
  updateUser(user);

  if (!user || !token) {
    return;
  }

  try {
    await loadSession();
    if (isClaimable(latestSession)) {
      setPanel("Signed in successfully. You can claim the session now.", "idle");
    }
  } catch (error) {
    setSessionBadge("Error");
    statusText.textContent = "Could not verify session";
    setPanel(`Could not load this session: ${error.message}`, "error");
  }
});


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
    syncClaimButtonState();
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
    syncClaimButtonState();
  } catch (error) {
    setSessionBadge("Error");
    statusText.textContent = "Could not verify session";
    setPanel(`Could not load this session: ${error.message}`, "error");
    syncClaimButtonState();
  }
});
