# Миграция: поле created_at для номенклатуры 1С и авто-новинки по пороговой дате.

from datetime import datetime

from django.db import migrations, models
from django.utils import timezone


# Для уже существующих строк нет истории «первого импорта»: ставим очень старую дату,
# чтобы они не попадали в автоматические новинки; у новых товаров после миграции
# корректно выставляет auto_now_add.


def forwards_backfill_created_at(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    sentinel = timezone.make_aware(datetime(2000, 1, 1, 0, 0, 0), timezone.get_current_timezone())
    Product.objects.all().update(created_at=sentinel)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_product_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="created_at",
            field=models.DateTimeField(
                db_index=True,
                help_text="Заполняется при первой загрузке номенклатуры из 1С; для новинок на сайте используется вместе с датой SHOP_NEW_ARRIVALS_AUTO_SINCE.",
                null=True,
                verbose_name="Первое появление в каталоге",
            ),
        ),
        migrations.RunPython(forwards_backfill_created_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                db_index=True,
                help_text="Заполняется при первой загрузке номенклатуры из 1С; для новинок на сайте используется вместе с датой SHOP_NEW_ARRIVALS_AUTO_SINCE.",
                verbose_name="Первое появление в каталоге",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["is_active", "created_at"], name="products_pr_is_acti_defdf1_idx"),
        ),
    ]
