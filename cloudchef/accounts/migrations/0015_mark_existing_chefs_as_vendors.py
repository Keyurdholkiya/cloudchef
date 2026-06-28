from django.db import migrations


def mark_existing_chefs_as_vendors(apps, schema_editor):
    Chef = apps.get_model("accounts", "Chef")
    User = apps.get_model("accounts", "chefsUser")
    owner_ids = Chef.objects.values_list("chef_owner_id", flat=True)
    User.objects.filter(id__in=owner_ids).update(role="VENDOR")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0014_notification_scope")]
    operations = [migrations.RunPython(mark_existing_chefs_as_vendors, migrations.RunPython.noop)]
