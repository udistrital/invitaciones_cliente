# Sistema de Invitaciones

Proyecto base en Django para gestionar ceremonias de grado, graduandos e invitaciones digitales con validación posterior mediante QR.

## Stack inicial

- Python 3.9+
- Django 4.2 LTS
- PostgreSQL
- `uv` para gestión local de dependencias

## Requisitos previos

- Tener una base de datos PostgreSQL creada.
- Tener disponibles las variables de entorno requeridas.

## Variables de entorno

Usa `.env.example` como referencia:

```bash
cp .env.example .env
set -a
source .env
set +a
```

Variables obligatorias:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## Instalación

```bash
uv sync
createdb -h 127.0.0.1 -U postgres sistema_invitaciones
set -a
source .env
set +a
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

Si tu instancia PostgreSQL usa otro usuario, host o contraseña, ajusta primero el archivo `.env`.

## Ejecución local

```bash
set -a
source .env
set +a
uv run python manage.py runserver
```

Puntos de verificación iniciales:

- `http://127.0.0.1:8000/health/`
- `http://127.0.0.1:8000/admin/`

## Validaciones básicas

```bash
set -a
source .env
set +a
uv run python manage.py check
uv run python manage.py makemigrations --check
uv run python manage.py test
```

## Estructura inicial

```text
config/               Configuración Django
apps/core/            Utilidades compartidas y health check
apps/ceremonies/      Modelo de ceremonias
apps/graduates/       Modelo de graduandos
apps/invitations/     Invitaciones y registros de validación
docs/adr/             Decisiones arquitectónicas
```

## Alcance de esta fase

Esta fase deja listo:

- el arranque del proyecto,
- la conexión a PostgreSQL por variables de entorno,
- el modelo de datos inicial,
- el registro en admin,
- migraciones base,
- pruebas smoke.

Las fases siguientes cubrirán QR, PDF, importación masiva desde Excel y flujo de validación completo.
