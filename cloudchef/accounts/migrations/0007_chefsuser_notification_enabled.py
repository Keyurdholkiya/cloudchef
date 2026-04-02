from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_savedaddress_order_delivery_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="chefsuser",
            name="notification_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
