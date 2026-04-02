from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_orderreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="review_prompt_disabled",
            field=models.BooleanField(default=False),
        ),
    ]
