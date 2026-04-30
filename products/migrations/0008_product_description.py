# Generated manually — aligns with products.Product.description

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0007_alter_category_id_alter_category_is_active_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Текст для карточки товара на сайте; заполняется вручную в админке.",
                verbose_name="Описание",
            ),
        ),
    ]
