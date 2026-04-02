from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_user_sound_theme_order_cancel_and_delivery_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="available_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
