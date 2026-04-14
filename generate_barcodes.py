from __future__ import annotations

import argparse
import sys
from pathlib import Path
import re

from barcode import Code128
from barcode.writer import ImageWriter

from sasta_dmart.barcodes import build_sdm_payload
from sasta_dmart.product_catalog import (
    ProductCatalogError,
    default_catalog_path,
    load_product_catalog,
    save_product_catalog,
    upsert_product,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upsert products and generate Sasta Dmart barcode PNGs.")
    parser.add_argument("--catalog-path", default=str(default_catalog_path()))
    parser.add_argument("--output-dir", default="barcodes")
    parser.add_argument("--product-id")
    parser.add_argument("--name")
    parser.add_argument("--price")
    parser.add_argument("--category")
    parser.add_argument("--upsert-catalog", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--all", action="store_true")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.all and args.product_id:
        print("--all cannot be combined with --product-id", file=sys.stderr)
        return 1
    if not args.all and not args.product_id:
        print("Provide --product-id or use --all.", file=sys.stderr)
        return 1
    if not args.upsert_catalog and not args.generate and not args.all:
        print("Nothing to do. Use --upsert-catalog, --generate, or --all.", file=sys.stderr)
        return 1

    catalog_path = Path(args.catalog_path)
    output_dir = Path(args.output_dir)
    rows = _load_catalog_rows(catalog_path, allow_missing=args.upsert_catalog)

    if args.upsert_catalog:
        if not args.product_id or not args.name or args.price is None:
            print(
                "Catalog upsert requires --product-id, --name, and --price.",
                file=sys.stderr,
            )
            return 1
        default_price = _parse_price(args.price)
        created, rows = upsert_product(
            rows,
            {
                "product_id": args.product_id,
                "name": args.name,
                "default_price": default_price,
                "category": args.category,
            },
        )
        save_product_catalog(catalog_path, rows)
        print(
            f"Catalog entry {'created' if created else 'updated'}: "
            f"{args.product_id} ({args.name})"
        )

    if args.all:
        if not rows:
            print("Product catalog is empty. Nothing to generate.", file=sys.stderr)
            return 1
        for product in rows:
            _generate_product_barcode(product, output_dir, price_override=None)
        return 0

    if not args.generate:
        return 0

    products = {row["product_id"]: row for row in rows}
    product = products.get(args.product_id)
    if product is None:
        print(
            f"Missing product {args.product_id} in catalog and not enough input to generate.",
            file=sys.stderr,
        )
        return 1

    price_override = _parse_price(args.price) if args.price is not None else None
    _generate_product_barcode(product, output_dir, price_override=price_override)
    return 0


def _load_catalog_rows(catalog_path: Path, *, allow_missing: bool) -> list[dict]:
    try:
        return load_product_catalog(catalog_path, as_index=False)
    except ProductCatalogError:
        if allow_missing and not catalog_path.exists():
            return []
        raise


def _parse_price(price_text: str) -> float:
    try:
        return round(float(price_text), 2)
    except ValueError as exc:
        raise SystemExit(f"Invalid price value: {price_text!r}") from exc


def _generate_product_barcode(
    product: dict,
    output_dir: Path,
    *,
    price_override: float | None,
) -> Path:
    unit_price = price_override if price_override is not None else product["default_price"]
    payload = build_sdm_payload(product["product_id"], unit_price)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{product['product_id']}-{_slugify(product['name'])}-"
        f"{unit_price:.2f}".replace(".", "_")
    )
    target = output_dir / filename
    writer = ImageWriter()
    barcode = Code128(payload, writer=writer)
    saved_base = Path(
        barcode.save(
            str(target),
            options={
                "write_text": False,
                "quiet_zone": 2,
                "module_height": 12,
                "module_width": 0.25,
            },
        )
    )
    output_path = saved_base.with_suffix(".png")
    print(f"Encoded payload: {payload}")
    print(f"Saved barcode: {output_path}")
    return output_path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"


if __name__ == "__main__":
    raise SystemExit(run())
