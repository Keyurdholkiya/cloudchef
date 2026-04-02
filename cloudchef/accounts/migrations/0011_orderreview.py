from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_dish_available_until"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rating", models.PositiveSmallIntegerField(default=5)),
                ("feedback", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("chef", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="accounts.chef")),
                ("dish", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="accounts.dish")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="review", to="accounts.order")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_reviews", to="accounts.chefsuser")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
