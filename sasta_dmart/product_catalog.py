from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ProductCatalogError(RuntimeError):
    pass


REQUIRED_FIELDS = ("product_id", "name", "default_price")


def default_catalog_path() -> Path:
    return Path(__file__).resolve().with_name("products.json")


def load_product_catalog(
    path: Path | str | None = None,
    *,
    as_index: bool = True,
) -> dict[str, dict[str, Any]] | list[dict[str, Any]]:
    catalog_path = Path(path) if path is not None else default_catalog_path()
    try:
        rows = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProductCatalogError(f"Missing product catalog: {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise ProductCatalogError(f"Invalid product catalog JSON: {catalog_path}") from exc

    if not isinstance(rows, list):
        raise ProductCatalogError("Product catalog must be a JSON list of product rows.")

    validated_rows = [_validate_row(row) for row in rows]
    if as_index:
        return {row["product_id"]: row for row in validated_rows}
    return validated_rows


def save_product_catalog(path: Path | str | None, rows: list[dict[str, Any]]) -> None:
    catalog_path = Path(path) if path is not None else default_catalog_path()
    validated_rows = [_validate_row(row) for row in rows]
    ordered_rows = sorted(validated_rows, key=lambda row: row["product_id"])
    catalog_path.write_text(json.dumps(ordered_rows, indent=2) + "\n", encoding="utf-8")


def upsert_product(
    rows: list[dict[str, Any]],
    product: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    validated_product = _validate_row(product)
    updated_rows = [_validate_row(row) for row in rows]
    for index, row in enumerate(updated_rows):
        if row["product_id"] == validated_product["product_id"]:
            updated_rows[index] = validated_product
            return False, sorted(updated_rows, key=lambda item: item["product_id"])
    updated_rows.append(validated_product)
    return True, sorted(updated_rows, key=lambda item: item["product_id"])


def _validate_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ProductCatalogError("Each product catalog row must be a JSON object.")

    missing_fields = [field for field in REQUIRED_FIELDS if field not in row]
    if missing_fields:
        raise ProductCatalogError(
            f"Product catalog row is missing required fields: {', '.join(sorted(missing_fields))}"
        )

    product_id = str(row["product_id"]).strip()
    name = str(row["name"]).strip()
    category = row.get("category")

    if not product_id:
        raise ProductCatalogError("Product catalog row has an empty product_id.")
    if not name:
        raise ProductCatalogError("Product catalog row has an empty name.")

    try:
        default_price = round(float(row["default_price"]), 2)
    except (TypeError, ValueError) as exc:
        raise ProductCatalogError(
            f"Invalid default_price for product {product_id!r}: {row['default_price']!r}"
        ) from exc

    validated = {
        "product_id": product_id,
        "name": name,
        "default_price": default_price,
    }
    if category is not None and str(category).strip():
        validated["category"] = str(category).strip()
    return validated
