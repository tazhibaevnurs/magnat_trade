from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_order_customer_comment"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="special_instructions",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
