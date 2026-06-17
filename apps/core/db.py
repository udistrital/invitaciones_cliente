from django.db.backends.signals import connection_created

from apps.core.schema import set_search_path_sql


def bootstrap_postgresql_schema(sender, connection, **kwargs):
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(set_search_path_sql())


def register_connection_bootstrap():
    connection_created.connect(
        bootstrap_postgresql_schema,
        dispatch_uid="apps.core.bootstrap_postgresql_schema",
    )
