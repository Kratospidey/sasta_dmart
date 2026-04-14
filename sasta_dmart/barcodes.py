from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


class BarcodeParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBarcode:
    raw_payload: str
    product_id: str
    unit_price: float


def build_sdm_payload(product_id: str, price: float) -> str:
    normalized_price = Decimal(str(price)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return f"SDM|pid={str(product_id).strip()}|price={normalized_price}"


def parse_sdm_payload(raw_payload: str) -> ParsedBarcode:
    payload = raw_payload.strip()
    if not payload:
        raise BarcodeParseError("blank payload")

    parts = payload.split("|")
    if parts[0] != "SDM":
        raise BarcodeParseError("unsupported prefix")

    fields: dict[str, str] = {}
    for segment in parts[1:]:
        if "=" not in segment:
            raise BarcodeParseError(f"malformed segment: {segment}")
        key, value = segment.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise BarcodeParseError(f"malformed segment: {segment}")
        fields[key] = value

    product_id = fields.get("pid", "").strip()
    if not product_id:
        raise BarcodeParseError("missing pid")

    price_text = fields.get("price", "").strip()
    if not price_text:
        raise BarcodeParseError("missing price")

    try:
        unit_price = Decimal(price_text).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except InvalidOperation as exc:
        raise BarcodeParseError("invalid price") from exc

    if unit_price < 0:
        raise BarcodeParseError("invalid price")

    return ParsedBarcode(
        raw_payload=payload,
        product_id=product_id,
        unit_price=float(unit_price),
    )


def select_first_supported_candidate(
    decoded_candidates: list[Any],
) -> tuple[ParsedBarcode | None, list[dict[str, Any]]]:
    debug_rows: list[dict[str, Any]] = []
    for candidate in decoded_candidates:
        barcode_type = str(getattr(candidate, "type", "UNKNOWN"))
        raw_data = getattr(candidate, "data", b"")
        try:
            payload = raw_data.decode("utf-8").strip()
        except Exception:
            debug_rows.append(
                {
                    "type": barcode_type,
                    "payload": "<decode-error>",
                    "status": "reject: undecodable bytes",
                    "accepted": False,
                }
            )
            continue

        if not payload:
            debug_rows.append(
                {
                    "type": barcode_type,
                    "payload": payload,
                    "status": "reject: blank payload",
                    "accepted": False,
                }
            )
            continue

        try:
            parsed = parse_sdm_payload(payload)
        except BarcodeParseError as exc:
            debug_rows.append(
                {
                    "type": barcode_type,
                    "payload": payload,
                    "status": f"reject: {exc}",
                    "accepted": False,
                }
            )
            continue

        debug_rows.append(
            {
                "type": barcode_type,
                "payload": payload,
                "status": "accept",
                "accepted": True,
            }
        )
        return parsed, debug_rows

    return None, debug_rows
