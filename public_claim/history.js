import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import {
  GoogleAuthProvider,
  getAuth,
  getRedirectResult,
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js";
import { get, getDatabase, ref } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-database.js";
import { normalizePurchaseHistory } from "./history_state.mjs";


const config = window.PUBLIC_CLAIM_CONFIG;
if (!config) {
  throw new Error("Missing PUBLIC_CLAIM_CONFIG. Generate public_claim/config.js first.");
}

const firebaseApp = initializeApp(config);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();
const database = getDatabase(firebaseApp);

const signInBtn = document.getElementById("historySignInBtn");
const signOutBtn = document.getElementById("historySignOutBtn");
const userText = document.getElementById("historyUserText");
const statusText = document.getElementById("historyStatusText");
const statusPanel = document.getElementById("historyStatusPanel");
const historyList = document.getElementById("historyList");


function setPanel(message, variant = "idle") {
  statusPanel.textContent = message;
  statusPanel.className = `status-panel status-${variant}`;
}


function formatCurrency(total) {
  return `₹ ${Number(total || 0).toFixed(2)}`;
}


function renderSignedOutState() {
  historyList.innerHTML = `
    <article class="history-empty">
      <p class="empty-title">Sign in to view your purchase history.</p>
      <p class="empty-copy">Only purchases attached to your own account will appear here.</p>
    </article>
  `;
}


function renderEmptyHistory() {
  historyList.innerHTML = `
    <article class="history-empty">
      <p class="empty-title">No purchases found yet.</p>
      <p class="empty-copy">Your next signed-in checkout will appear here after the Pi saves it.</p>
    </article>
  `;
}


function renderHistory(rows) {
  if (!rows.length) {
    renderEmptyHistory();
    return;
  }

  historyList.innerHTML = rows.map((row) => {
    const lineItems = row.items.length
      ? `
        <details class="history-detail">
          <summary>View line items</summary>
          <ul class="history-items">
            ${row.items.map((item) => `
              <li>
                <span>${item.name || "Item"}</span>
                <span>x${Number(item.qty || 0)}</span>
                <span>${formatCurrency(item.line_total || 0)}</span>
              </li>
            `).join("")}
          </ul>
        </details>
      `
      : "";

    return `
      <article class="history-card">
        <div class="history-card-head">
          <div>
            <span class="label">Bill ID</span>
            <strong>${row.bill_id}</strong>
          </div>
          <span class="pill">${row.payment_type}</span>
        </div>
        <div class="history-grid">
          <div class="meta-row">
            <span class="meta-label">Time</span>
            <span class="meta-value">${row.generated_at}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Total</span>
            <span class="meta-value">${formatCurrency(row.total)}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Items</span>
            <span class="meta-value">${row.item_summary || `${row.item_count} items`}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Pi node</span>
            <span class="meta-value">${row.pi_node || "-"}</span>
          </div>
        </div>
        ${lineItems}
      </article>
    `;
  }).join("");
}


async function loadHistory(user) {
  if (!user) {
    statusText.textContent = "Sign-in required";
    setPanel("Sign in with Google to load your account-specific purchases.", "idle");
    renderSignedOutState();
    return;
  }

  statusText.textContent = "Loading purchases";
  setPanel("Loading purchases attached to your account...", "idle");

  try {
    const snapshot = await get(ref(database, `customer_transactions/${user.uid}`));
    const rows = normalizePurchaseHistory(snapshot.val());

    statusText.textContent = rows.length ? `${rows.length} purchase(s)` : "No purchases yet";
    setPanel(
      rows.length
        ? "Showing purchases attached to your signed-in account."
        : "No purchases found yet for this account.",
      rows.length ? "success" : "idle",
    );
    renderHistory(rows);
  } catch (error) {
    statusText.textContent = "History load failed";
    setPanel(`Could not load purchase history: ${error.message}`, "error");
    historyList.innerHTML = `
      <article class="history-empty">
        <p class="empty-title">Could not load purchase history.</p>
        <p class="empty-copy">Check Firebase Rules and try again.</p>
      </article>
    `;
  }
}


async function handleSignIn() {
  try {
    const result = await signInWithPopup(auth, provider);
    await loadHistory(result.user);
  } catch (error) {
    const code = String(error?.code || "");
    if (code.includes("popup") || code.includes("operation-not-supported")) {
      await signInWithRedirect(auth, provider);
      return;
    }

    statusText.textContent = "Sign-in failed";
    setPanel(`Google sign-in failed: ${error.message}`, "error");
  }
}


signInBtn.addEventListener("click", handleSignIn);
signOutBtn.addEventListener("click", async () => {
  await signOut(auth);
});


onAuthStateChanged(auth, async (user) => {
  userText.textContent = user ? (user.email || user.displayName || "Signed in") : "Not signed in";
  signInBtn.hidden = Boolean(user);
  signOutBtn.hidden = !user;

  await loadHistory(user);
});


window.addEventListener("DOMContentLoaded", async () => {
  try {
    const result = await getRedirectResult(auth);
    if (result?.user) {
      await loadHistory(result.user);
      setPanel("Signed in successfully. Loading your purchase history.", "success");
    }
  } catch (error) {
    statusText.textContent = "Sign-in failed";
    setPanel(`Google sign-in failed: ${error.message}`, "error");
  }
});
