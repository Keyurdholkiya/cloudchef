from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_add_chef_slug_safely"),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(default="Home", max_length=80)),
                ("full_name", models.CharField(max_length=120)),
                ("phone_number", models.CharField(max_length=15)),
                ("address_line", models.CharField(max_length=255)),
                ("landmark", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(max_length=120)),
                ("state", models.CharField(max_length=120)),
                ("pincode", models.CharField(max_length=12)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_addresses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_map_query",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_phone",
            field=models.CharField(blank=True, max_length=15),
        ),
    ]
