# Generated manually for unified orders (демо + каталог)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_onec_string_ids"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="catalog_orders",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_full_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
