from django.db import models


INSTITUTIONAL_SCHEMA = "invitaciones_grado"


def schema_table(table_name: str) -> str:
    return f'"{INSTITUTIONAL_SCHEMA}"."{table_name}"'


class TimeStampedModel(models.Model):
    id = models.AutoField(primary_key=True)
    is_active = models.BooleanField(
        "activo",
        default=True,
        db_column="activo",
    )
    created_at = models.DateTimeField(
        "fecha de creacion",
        auto_now_add=True,
        db_column="fecha_creacion",
    )
    updated_at = models.DateTimeField(
        "fecha de modificacion",
        auto_now=True,
        db_column="fecha_modificacion",
    )

    class Meta:
        abstract = True
