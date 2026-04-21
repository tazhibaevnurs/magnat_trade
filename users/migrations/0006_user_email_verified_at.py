from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_user_active_session_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Когда пользователь подтвердил email.",
                null=True,
            ),
        ),
    ]
