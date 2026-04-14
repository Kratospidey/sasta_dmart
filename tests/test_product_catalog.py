from __future__ import annotations

from pathlib import Path

import pytest

from sasta_dmart.product_catalog import (
    ProductCatalogError,
    load_product_catalog,
    save_product_catalog,
    upsert_product,
)


def test_load_product_catalog_indexes_seed_rows(tmp_path: Path):
    catalog_path = tmp_path / "products.json"
    catalog_path.write_text(
        """
        [
          {"product_id": "00001", "name": "Apple", "default_price": 60.0},
          {"product_id": "00002", "name": "Bottle", "default_price": 25.0}
        ]
        """.strip(),
        encoding="utf-8",
    )

    products = load_product_catalog(catalog_path)

    assert products["00001"]["name"] == "Apple"
    assert products["00002"]["default_price"] == 25.0


def test_upsert_product_creates_and_updates_rows(tmp_path: Path):
    catalog_path = tmp_path / "products.json"
    save_product_catalog(catalog_path, [])

    created, rows = upsert_product(
        load_product_catalog(catalog_path, as_index=False),
        {"product_id": "00004", "name": "Milk", "default_price": 45.0, "category": "dairy"},
    )
    assert created is True

    updated, rows = upsert_product(
        rows,
        {"product_id": "00004", "name": "Milk", "default_price": 49.0, "category": "dairy"},
    )
    assert updated is False
    assert rows[0]["default_price"] == 49.0


def test_load_product_catalog_rejects_missing_required_fields(tmp_path: Path):
    catalog_path = tmp_path / "products.json"
    catalog_path.write_text('[{"product_id": "00001", "name": "Apple"}]', encoding="utf-8")

    with pytest.raises(ProductCatalogError):
        load_product_catalog(catalog_path)
