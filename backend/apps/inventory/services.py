"""
Loads a ProductTemplate's seed data (categories + products) onto a
branch during first-run setup (design doc B.7 step 2 / API E.6
POST /setup/load-template/).

Seed data files (fixtures/provision_store.json etc.) are plain JSON, NOT
Django `loaddata` fixtures — loaddata fixtures carry hardcoded PKs and
branch_id, whereas the whole point here is to stamp the *caller's*
branch_id onto freshly-generated UUIDs at load time, once, for whichever
branch is running setup. The four ProductTemplate rows themselves
(key/name/description/icon/fixture_name) ARE plain Django model rows,
seeded once via migrations/0002_seed_product_templates.py.
"""
import json
from pathlib import Path

from django.db import transaction

from .models import Category, Product, ProductTemplate

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TemplateNotFoundError(Exception):
    pass


@transaction.atomic
def load_template(template_key: str, branch_id: str) -> dict:
    """
    Idempotent-ish by category name (get_or_create), but NOT by product —
    calling this twice for the same branch will duplicate products. The
    setup wizard only ever calls it once, immediately after POST /setup/,
    while Branch.setup_complete is still being finalised.
    """
    try:
        template = ProductTemplate.objects.get(key=template_key)
    except ProductTemplate.DoesNotExist as exc:
        raise TemplateNotFoundError(f"No product template with key '{template_key}'") from exc

    fixture_path = FIXTURES_DIR / template.fixture_name
    with open(fixture_path, encoding="utf-8") as fh:
        data = json.load(fh)

    categories_by_name = {}
    for cat in data.get("categories", []):
        category, _ = Category.objects.get_or_create(
            branch_id=branch_id,
            name=cat["name"],
            defaults={
                "description": cat.get("description", ""),
                "sort_order": cat.get("sort_order", 0),
            },
        )
        categories_by_name[cat["name"]] = category

    created_products = []
    for prod in data.get("products", []):
        category = categories_by_name[prod["category"]]
        product = Product.objects.create(
            branch_id=branch_id,
            name=prod["name"],
            category=category,
            unit=prod.get("unit", "unit"),
            retail_price=prod["retail_price"],
            bulk_price=prod.get("bulk_price"),
            bulk_min_qty=prod.get("bulk_min_qty"),
            stock_level=prod.get("stock_level", 0),
            low_stock_threshold=prod.get("low_stock_threshold", 5),
            source="template",
        )
        created_products.append(product)

    return {
        "template": template.name,
        "categories_created": len(categories_by_name),
        "products_created": len(created_products),
    }

def list_templates() -> list[dict]:
    """
    Read-only counterpart to load_template() -- returns each
    ProductTemplate's static fields plus counts/preview names read
    directly from its fixture file. Never touches the database beyond
    the initial ProductTemplate query, so it's safe to call from an
    AllowAny endpoint (design doc E.6 -- the setup wizard's step 2 has
    to render before any account exists to authenticate as).

    This exists so the frontend never has to hardcode template names,
    icons, or product counts -- that duplication was flagged as an
    open item after the setup-wizard frontend session and this closes
    it.
    """
    templates = []
    for template in ProductTemplate.objects.all().order_by("name"):
        fixture_path = FIXTURES_DIR / template.fixture_name
        with open(fixture_path, encoding="utf-8") as fh:
            data = json.load(fh)
        templates.append({
            "key": template.key,
            "name": template.name,
            "description": template.description,
            "icon": template.icon,
            "category_count": len(data.get("categories", [])),
            "product_count": len(data.get("products", [])),
            "preview_products": [p["name"] for p in data.get("products", [])[:9]],
        })
    return templates
