from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="chefsuser",
            name="sound_theme",
            field=models.CharField(default="classic", max_length=40),
        ),
        migrations.AddField(
            model_name="order",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_notification_sent",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="is_cancelled",
            field=models.BooleanField(default=False),
        ),
    ]
