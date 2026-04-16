# Generated manually for backfill

from django.db import migrations, models


def fill_slugs(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    from django.utils.text import slugify

    for pk, name in Category.objects.values_list("id", "name"):
        base = slugify(f"{pk}-{name}", allow_unicode=True)[:200]
        if not base:
            base = slugify(pk, allow_unicode=True) or "category"
        slug = base
        n = 0
        while Category.objects.filter(slug=slug).exclude(pk=pk).exists():
            n += 1
            suffix = f"-{n}"
            slug = f"{base[: 220 - len(suffix)]}{suffix}"
        slug = slug[:220]
        Category.objects.filter(pk=pk).update(slug=slug)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0003_category_slug"),
    ]

    operations = [
        migrations.RunPython(fill_slugs, noop_reverse),
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                help_text="ЧПУ для ссылок на сайте (генерируется из кода и названия 1С).",
                max_length=220,
                unique=True,
                db_index=True,
            ),
        ),
    ]
