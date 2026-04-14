from __future__ import annotations

from pathlib import Path

from generate_barcodes import run


def test_run_upsert_and_generate_creates_catalog_entry_and_png(tmp_path: Path):
    catalog_path = tmp_path / "products.json"
    output_dir = tmp_path / "barcodes"

    exit_code = run(
        [
            "--catalog-path",
            str(catalog_path),
            "--output-dir",
            str(output_dir),
            "--product-id",
            "00004",
            "--name",
            "Milk",
            "--price",
            "45.00",
            "--category",
            "dairy",
            "--upsert-catalog",
            "--generate",
        ]
    )

    assert exit_code == 0
    assert output_dir.joinpath("00004-milk-45_00.png").exists()
    assert "00004" in catalog_path.read_text(encoding="utf-8")


def test_run_generate_existing_catalog_product_uses_default_price(tmp_path: Path):
    catalog_path = tmp_path / "products.json"
    catalog_path.write_text(
        '[{"product_id": "00001", "name": "Apple", "default_price": 60.0}]',
        encoding="utf-8",
    )

    exit_code = run(
        [
            "--catalog-path",
            str(catalog_path),
            "--output-dir",
            str(tmp_path / "barcodes"),
            "--product-id",
            "00001",
            "--generate",
        ]
    )

    assert exit_code == 0


def test_run_generate_missing_product_without_create_input_fails(
    tmp_path: Path,
    capsys,
):
    catalog_path = tmp_path / "products.json"
    catalog_path.write_text("[]", encoding="utf-8")

    exit_code = run(
        [
            "--catalog-path",
            str(catalog_path),
            "--product-id",
            "00099",
            "--generate",
        ]
    )

    assert exit_code == 1
    assert "missing product" in capsys.readouterr().err.lower()
