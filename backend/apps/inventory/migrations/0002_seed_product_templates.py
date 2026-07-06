from django.db import migrations

# key values are slugs (ProductTemplate.key is a SlugField) — hyphenated,
# independent of each fixture's underscored filename. Product/category
# counts and fixture_name below are taken directly from the real files
# under apps/inventory/fixtures/, not assumed.
TEMPLATES = [
    {
        "key": "provision-store",
        "name": "Provision Store",
        "description": "General goods, staples and daily essentials",
        "icon": "🏪",
        "fixture_name": "provision_store.json",
    },
    {
        "key": "boutique",
        "name": "Boutique / Clothing",
        "description": "Clothing, accessories and fashion",
        "icon": "👗",
        "fixture_name": "boutique.json",
    },
    {
        "key": "cosmetics",
        "name": "Cosmetics / Beauty",
        "description": "Beauty products, skincare, hair care",
        "icon": "💄",
        "fixture_name": "cosmetics.json",
    },
    {
        "key": "electronics",
        "name": "Electronics",
        "description": "Phones, accessories, small electronics",
        "icon": "📱",
        "fixture_name": "electronics.json",
    },
]


def seed_templates(apps, schema_editor):
    ProductTemplate = apps.get_model("inventory", "ProductTemplate")
    for template in TEMPLATES:
        ProductTemplate.objects.create(**template)


def unseed_templates(apps, schema_editor):
    ProductTemplate = apps.get_model("inventory", "ProductTemplate")
    ProductTemplate.objects.filter(
        key__in=[t["key"] for t in TEMPLATES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
