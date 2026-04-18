# Связь операций склада демо-товара с единым orders.Order

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_unify_delivery_and_guest"),
        ("shop", "0002_cartitem_catalog_product"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventorytransaction",
            name="catalog_order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="demo_inventory_transactions",
                to="orders.order",
            ),
        ),
    ]
