from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import uuid


def _coerce_utc(now_utc: str | datetime | None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if isinstance(now_utc, datetime):
        return now_utc.astimezone(timezone.utc)
    return datetime.fromisoformat(now_utc).astimezone(timezone.utc)


def _default_customer(customer: dict[str, Any] | None) -> dict[str, Any]:
    if customer:
        return {
            "uid": customer.get("uid"),
            "email": customer.get("email"),
            "name": customer.get("name"),
        }
    return {"uid": None, "email": None, "name": "Anonymous"}


def _build_item_summary(items: list[dict[str, Any]]) -> str:
    return ", ".join(f"{item['name']} x{item['qty']}" for item in items)


def build_transaction_payload(
    cart_items: list[dict[str, Any]],
    session_type: str,
    customer: dict[str, Any] | None,
    pi_node: str,
    now_utc: str | datetime | None = None,
    bill_suffix: str | None = None,
) -> dict[str, Any]:
    generated_at = _coerce_utc(now_utc)
    items: list[dict[str, Any]] = []
    total = 0.0

    for item in cart_items:
        line_total = round(item["qty"] * item["unit_price"], 2)
        total += line_total
        items.append(
            {
                "product_id": item["product_id"],
                "name": item["name"],
                "qty": item["qty"],
                "unit_price": round(item["unit_price"], 2),
                "line_total": line_total,
                "barcode": item["barcode"],
            }
        )

    suffix = bill_suffix or uuid.uuid4().hex[:6].upper()
    bill_id = f"BILL-{generated_at.strftime('%Y%m%d-%H%M%S')}-{suffix}"
    item_count = sum(item["qty"] for item in items)

    return {
        "bill_id": bill_id,
        "generated_at": generated_at.isoformat(),
        "generated_at_ms": int(generated_at.timestamp() * 1000),
        "session_type": session_type,
        "customer": _default_customer(customer),
        "items": items,
        "total": round(total, 2),
        "item_count": item_count,
        "item_summary": _build_item_summary(items),
        "pi_node": pi_node,
    }


def build_customer_history_record(
    transaction_id: str,
    transaction: dict[str, Any],
) -> dict[str, Any]:
    return {
        "transaction_id": transaction_id,
        "bill_id": transaction["bill_id"],
        "generated_at": transaction["generated_at"],
        "generated_at_ms": transaction["generated_at_ms"],
        "total": transaction["total"],
        "payment_type": transaction["payment_type"],
        "item_count": transaction["item_count"],
        "item_summary": transaction["item_summary"],
        "pi_node": transaction["pi_node"],
        "customer": deepcopy(transaction["customer"]),
        "items": deepcopy(transaction["items"]),
    }


def build_transaction_write_map(
    transaction_id: str,
    transaction: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    updates = {
        f"transactions/{transaction_id}": deepcopy(transaction),
    }

    customer_uid = transaction.get("customer", {}).get("uid")
    if customer_uid:
        updates[f"customer_transactions/{customer_uid}/{transaction_id}"] = (
            build_customer_history_record(transaction_id, transaction)
        )

    return updates
