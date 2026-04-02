from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_cartitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="scope",
            field=models.CharField(
                choices=[("customer", "Customer"), ("chef", "Chef"), ("global", "Global")],
                default="customer",
                max_length=20,
            ),
        ),
    ]
