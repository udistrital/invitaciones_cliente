from django.db import migrations

from apps.core.schema import create_schema_sql


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql=create_schema_sql(),
            reverse_sql='DROP SCHEMA IF EXISTS "invitaciones_grado" CASCADE;',
        ),
    ]
