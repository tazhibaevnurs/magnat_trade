from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_manager_and_wholesale_request"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="active_session_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Ключ сессии Django: одновременно только один активный вход (не staff).",
                max_length=40,
            ),
        ),
    ]
