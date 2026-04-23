from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0009_mysql_compatible_unique_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="special_instructions",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
