# Sistema de Invitaciones

Aplicacion web en Django para administrar ceremonias de grado, graduandos e invitaciones digitales con validacion por QR, trazabilidad de ingreso y un backoffice operativo para Secretaria Academica.

## Descripcion del proyecto

El sistema cubre un flujo institucional simple:

- registrar ceremonias y graduandos,
- definir cupos de invitaciones por graduando,
- emitir invitaciones con codigo y token firmado,
- generar QR y PDF bajo demanda,
- validar invitaciones en ingreso,
- registrar trazabilidad de consultas y usos,
- operar el proceso desde admin Django y backoffice.

La solucion prioriza mantenibilidad y velocidad de entrega. No almacena archivos binarios en base de datos ni en disco para QR/PDF; ambos se reconstruyen cuando se necesitan.

## Arquitectura

La aplicacion sigue un monolito modular sobre Django 4.2:

- `apps/core`: utilidades compartidas y health check.
- `apps/ceremonies`: dominio de ceremonias.
- `apps/graduates`: dominio de graduandos.
- `apps/invitations`: emision, token firmado, QR, PDF, validacion y trazabilidad.
- `apps/backoffice`: interfaz operativa para personal staff.
- `config/`: configuracion Django, URLs y entrypoints ASGI/WSGI.
- `docs/adr/`: decisiones de arquitectura.

Decisiones clave:

- PostgreSQL como base de datos principal.
- Tokens firmados con `public_id + token_version`.
- Regeneracion por rotacion de `token_version`.
- QR y PDF generados en memoria.
- Backoffice simple sobre vistas Django protegidas por `is_staff`.

## Requisitos

- Python 3.9 o superior
- PostgreSQL disponible
- `uv` recomendado para dependencias y ejecucion local

Tambien puedes usar el entorno virtual incluido localmente si ya existe `.venv`.

## Instalacion

1. Crea y ajusta variables de entorno en `.env`.
2. Sincroniza dependencias:

```bash
uv sync
```

3. Crea la base de datos si aun no existe:

```bash
createdb -h 127.0.0.1 -U postgres sistema_invitaciones
```

4. Ejecuta migraciones:

```bash
uv run python manage.py migrate
```

5. Crea un usuario administrador o staff:

```bash
uv run python manage.py createsuperuser
```

## Variables de entorno

Variables obligatorias:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `APP_BASE_URL`

Variables adicionales del proyecto:

- `USE_X_FORWARDED_FOR`

Ejemplo base en `.env.example`:

```env
SECRET_KEY=change-me-with-a-secure-random-value
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DB_NAME=sistema_invitaciones
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
APP_BASE_URL=http://127.0.0.1:8000
USE_X_FORWARDED_FOR=False
```

### Cargar `.env` en PowerShell

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -notmatch '^\s*#' -and $_ -match '=') {
        $name, $value = $_ -split '=', 2
        Set-Item -Path "Env:$name" -Value $value
    }
}
```

## Migraciones

Aplicar migraciones:

```bash
uv run python manage.py migrate
```

Verificar que no existan cambios de modelo pendientes:

```bash
uv run python manage.py makemigrations --check
```

## Ejecucion local

Con variables ya cargadas:

```bash
uv run python manage.py runserver
```

Puntos utiles:

- `GET /health/`
- `GET /admin/`
- `GET /gestion/`
- `GET /invitaciones/validar/?token=...`

## Pruebas

El proyecto usa el framework de pruebas de Django con `django.test.TestCase`.

Chequeos recomendados:

```bash
uv run python manage.py check
uv run python manage.py makemigrations --check
uv run python manage.py test
```

Suite smoke minima de invitaciones:

```bash
uv run python manage.py test apps.invitations.tests_smoke
```

Suite completa:

```bash
uv run python manage.py test
```

## Flujo funcional

### 1. Configuracion operativa

- Crear ceremonia.
- Crear graduandos.
- Definir `invitation_quota`.
- Crear puntos de acceso si se validara en sitio.

### 2. Emision de invitaciones

Por backoffice:

- `/gestion/graduandos/` para generar por graduando.
- `/gestion/ceremonias/` para generar por ceremonia.

Por comando:

```bash
uv run python manage.py issue_invitations --graduate-id 1
uv run python manage.py issue_invitations --ceremony-code GRADOS-2026-01
```

### 3. Activos generados

- URL de validacion con token firmado
- PDF de invitacion
- QR derivado de la URL de validacion

Rutas relevantes:

- `GET /invitaciones/validar/?token=...`
- `POST /invitaciones/usar/`
- `GET /invitaciones/descargar/?token=...`
- `GET /invitaciones/qr/<public_id>/` solo para personal `is_staff`

### 4. Validacion de ingreso

- El QR lleva a la pantalla de validacion.
- El sistema muestra si la invitacion esta valida, usada, anulada o no existe.
- Personal `is_staff` puede marcarla como usada.
- Cada consulta genera trazabilidad operativa.

### 5. Regeneracion y anulacion

Regeneracion:

- rota `token_version`,
- invalida QR y enlaces anteriores,
- mantiene el mismo registro de invitacion,
- solo se permite para invitaciones no usadas y no anuladas.

Comando:

```bash
uv run python manage.py regenerate_invitation --code INV-XXXXXXXXXXXX
```

Backoffice:

- detalle de invitacion en `/gestion/invitaciones/<pk>/`

Anulacion:

- disponible para invitaciones no usadas,
- bloquea el uso posterior.

## Datos semilla / carga inicial

Se incluye un comando idempotente para cargar datos demo locales:

```bash
uv run python manage.py seed_demo_data
```

El comando crea o reutiliza:

- una ceremonia demo,
- dos puntos de acceso,
- dos graduandos,
- sus invitaciones iniciales.

Esto deja el proyecto listo para revisar el flujo funcional desde `/gestion/` y `/admin/`.

## Seguridad y operacion

- El QR y los enlaces usan token firmado; modificar el token invalida la firma.
- Los QR preview directos requieren sesion staff.
- Las respuestas asociadas a token usan politicas para reducir cacheo y fuga por `Referer`.
- La IP real no usa `X-Forwarded-For` salvo configuracion explicita.
- QR y PDF se generan en memoria; no hay archivos temporales persistentes del flujo.
- Para despliegues institucionales se recomienda `DEBUG=False`, `APP_BASE_URL` con `https://` y `SECRET_KEY` real.

## Mejoras futuras

Ver `docs/FUTURE_IMPROVEMENTS.md`.

## Que falta para produccion

- pipeline CI con pruebas y validaciones automaticas,
- configuracion de despliegue segura por ambiente,
- monitoreo y logging estructurado,
- backup y restauracion de PostgreSQL,
- politicas de acceso, rotacion de secretos y operacion institucional,
- endurecimiento HTTP completo en un entorno HTTPS real,
- proceso formal de provisionamiento de usuarios staff,
- pruebas automatizadas ejecutadas en CI y no solo localmente.
