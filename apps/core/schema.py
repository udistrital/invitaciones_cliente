INSTITUTIONAL_SCHEMA = "invitaciones_grado"
INSTITUTIONAL_FALLBACK_SCHEMA = "public"
INSTITUTIONAL_SEARCH_PATH = (
    f"{INSTITUTIONAL_SCHEMA},{INSTITUTIONAL_FALLBACK_SCHEMA}"
)


def schema_table(table_name: str) -> str:
    return f'"{INSTITUTIONAL_SCHEMA}"."{table_name}"'


def create_schema_sql() -> str:
    return f'CREATE SCHEMA IF NOT EXISTS "{INSTITUTIONAL_SCHEMA}";'


def set_search_path_sql() -> str:
    return f"SET search_path TO {INSTITUTIONAL_SCHEMA}, {INSTITUTIONAL_FALLBACK_SCHEMA};"
