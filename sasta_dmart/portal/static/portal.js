async function refreshPortal() {
  const txBody = document.getElementById("txBody");
  if (!txBody) {
    return;
  }

  try {
    const response = await fetch("/api/transactions");
    const payload = await response.json();
    const rows = payload.transactions || [];

    if (!rows.length) {
      txBody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="empty-state">
              <p class="empty-title">The ledger is quiet for now.</p>
              <p class="empty-copy">Your next checkout will appear here once the Pi writes a transaction.</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    txBody.innerHTML = rows.map((tx) => {
      const customer = (tx.customer && (tx.customer.email || tx.customer.name)) || "Anonymous";
      const badgeClass = tx.session_type === "logged_in" ? "badge-gold" : "badge-green";
      const paymentType = tx.payment_type || "-";
      const total = Number(tx.total || 0).toFixed(2);
      return `
        <tr class="fade-row">
          <td><strong>${tx.bill_id || "-"}</strong></td>
          <td>${tx.generated_at || "-"}</td>
          <td><span class="badge ${badgeClass}">${tx.session_type || "-"}</span></td>
          <td>${customer}</td>
          <td>${paymentType}</td>
          <td>${tx.pi_node || "-"}</td>
          <td class="align-right">₹ ${total}</td>
        </tr>
      `;
    }).join("");
  } catch (error) {
    txBody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">
            <p class="empty-title">Could not refresh transactions.</p>
            <p class="empty-copy">Check Firebase connectivity and reload the dashboard.</p>
          </div>
        </td>
      </tr>
    `;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  refreshPortal();
  window.setInterval(refreshPortal, 5000);
});
