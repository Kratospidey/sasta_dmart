from __future__ import annotations

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

    return {
        "bill_id": bill_id,
        "generated_at": generated_at.isoformat(),
        "session_type": session_type,
        "customer": _default_customer(customer),
        "items": items,
        "total": round(total, 2),
        "pi_node": pi_node,
    }
