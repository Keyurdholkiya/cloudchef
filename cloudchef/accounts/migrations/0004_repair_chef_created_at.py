from django.db import migrations


def add_created_at_if_missing(apps, schema_editor):
    table_name = "accounts_chef"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]

        if "created_at" not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN created_at datetime")
            cursor.execute(
                f"UPDATE {table_name} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_dish_order"),
    ]

    operations = [
        migrations.RunPython(add_created_at_if_missing, migrations.RunPython.noop),
    ]
