function buildFallbackItemCount(items) {
  return items.reduce((total, item) => total + Number(item.qty || 0), 0);
}


function buildFallbackItemSummary(items) {
  if (!items.length) {
    return "No items";
  }

  return items
    .map((item) => `${item.name || "Item"} x${Number(item.qty || 0)}`)
    .join(", ");
}


export function normalizePurchaseHistory(records) {
  return Object.entries(records || {})
    .map(([transactionId, record]) => {
      const items = Array.isArray(record?.items) ? record.items : [];
      const itemCount = Number.isFinite(record?.item_count)
        ? Number(record.item_count)
        : buildFallbackItemCount(items);

      return {
        transaction_id: record?.transaction_id || transactionId,
        bill_id: record?.bill_id || transactionId,
        generated_at: record?.generated_at || "-",
        generated_at_ms: Number(record?.generated_at_ms || 0),
        total: Number(record?.total || 0),
        payment_type: record?.payment_type || "-",
        item_count: itemCount,
        item_summary: record?.item_summary || buildFallbackItemSummary(items),
        pi_node: record?.pi_node || "-",
        customer: record?.customer || null,
        items,
      };
    })
    .sort((left, right) => right.generated_at_ms - left.generated_at_ms);
}
