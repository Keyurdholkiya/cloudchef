from django.db import migrations, models
from django.utils.text import slugify


def add_and_fill_chef_slug(apps, schema_editor):
    table_name = "accounts_chef"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]

        if "chef_slug" not in columns:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN chef_slug varchar(140) NOT NULL DEFAULT ''"
            )

        cursor.execute(f"SELECT id, chef_name, chef_slug FROM {table_name}")
        rows = cursor.fetchall()
        for chef_id, chef_name, chef_slug in rows:
            if chef_slug:
                continue
            value = slugify(chef_name or "") or f"chef-{chef_id}"
            cursor.execute(
                f"UPDATE {table_name} SET chef_slug = ? WHERE id = ?",
                [value, chef_id],
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_repair_chef_created_at"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_and_fill_chef_slug, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="chef",
                    name="chef_slug",
                    field=models.SlugField(default="", max_length=140),
                    preserve_default=False,
                ),
            ],
        ),
    ]
