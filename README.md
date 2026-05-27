# Sistema de Invitaciones

Aplicacion web en Django para gestionar ceremonias de grado, graduandos e invitaciones digitales con QR, validacion de ingreso y backoffice operativo para Secretaria Academica.

## Descripcion del proyecto

El sistema cubre un flujo institucional simple:

- registrar ceremonias,
- registrar graduandos manualmente o cargarlos masivamente desde Excel,
- generar invitaciones digitales con token firmado y QR,
- validar invitaciones en ingreso,
- registrar trazabilidad operativa,
- operar el proceso desde backoffice y admin Django.

La solucion prioriza mantenibilidad y velocidad de entrega. Los QR y PDFs se generan bajo demanda en memoria; no se almacenan binarios en base de datos ni en disco.

## Arquitectura

La aplicacion sigue un monolito modular sobre Django 4.2:

- `apps/core`: utilidades compartidas, modelo base y comandos de apoyo.
- `apps/ceremonies`: dominio de ceremonias.
- `apps/graduates`: dominio de graduandos e importacion masiva desde Excel.
- `apps/invitations`: emision, token firmado, QR, PDF, validacion y trazabilidad.
- `apps/accounts`: autenticacion institucional por OIDC, consulta a `autenticacion_mid` y provision JIT para backoffice.
- `apps/backoffice`: interfaz operativa protegida para personal staff.
- `config/`: configuracion Django, URLs y entrypoints ASGI/WSGI.
- `docs/adr/`: decisiones de arquitectura.

Decisiones clave:

- PostgreSQL como base de datos principal.
- `openpyxl` para leer y generar archivos `.xlsx`.
- importacion en dos pasos: `validar -> confirmar`.
- bitacora persistida de cada lote de importacion.
- tokens firmados con `public_id + token_version`.
- QR y PDF generados en memoria.

## Requisitos

- Python 3.9 o superior
- PostgreSQL disponible
- `uv` recomendado para instalar dependencias y ejecutar localmente

Tambien puedes usar el entorno virtual local si ya existe `.venv`.

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

Variables adicionales:

- `USE_X_FORWARDED_FOR`
- `SSO_ENABLED`
- `OIDC_WSO2_SERVER_METADATA_URL`
- `OIDC_WSO2_CLIENT_ID`
- `OIDC_WSO2_CLIENT_SECRET`
- `OIDC_WSO2_SCOPES`
- `OIDC_WSO2_ROLE_CLAIM`
- `OIDC_WSO2_STAFF_ROLE`
- `OIDC_WSO2_EMAIL_CLAIM`
- `OIDC_WSO2_USERNAME_CLAIM`
- `OIDC_WSO2_NAME_CLAIM`
- `OIDC_POST_LOGOUT_REDIRECT_URL`
- `AUTHENTICATION_MID_ENABLED`
- `AUTHENTICATION_MID_USER_ROLE_URL`
- `AUTHENTICATION_MID_TIMEOUT_SECONDS`
- `AUTHENTICATION_MID_ROLE_FIELD`
- `AUTHENTICATION_MID_DOCUMENT_FIELD`
- `AUTHENTICATION_MID_COMPOSED_DOCUMENT_FIELD`
- `AUTHENTICATION_MID_EMAIL_FIELD`
- `AUTHENTICATION_MID_FAMILY_NAME_FIELD`
- `AUTHENTICATION_MID_STUDENT_CODE_FIELD`
- `AUTHENTICATION_MID_STATE_FIELD`

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
SSO_ENABLED=False
OIDC_WSO2_SERVER_METADATA_URL=
OIDC_WSO2_CLIENT_ID=
OIDC_WSO2_CLIENT_SECRET=
OIDC_WSO2_SCOPES=openid profile email
OIDC_WSO2_ROLE_CLAIM=roles
OIDC_WSO2_STAFF_ROLE=
OIDC_WSO2_EMAIL_CLAIM=email
OIDC_WSO2_USERNAME_CLAIM=preferred_username
OIDC_WSO2_NAME_CLAIM=name
OIDC_POST_LOGOUT_REDIRECT_URL=http://127.0.0.1:8000/gestion/
AUTHENTICATION_MID_ENABLED=False
AUTHENTICATION_MID_USER_ROLE_URL=https://autenticacion.portaloas.udistrital.edu.co/apioas/autenticacion_mid/v1/token/userRol
AUTHENTICATION_MID_TIMEOUT_SECONDS=10
AUTHENTICATION_MID_ROLE_FIELD=role
AUTHENTICATION_MID_DOCUMENT_FIELD=documento
AUTHENTICATION_MID_COMPOSED_DOCUMENT_FIELD=documento_compuesto
AUTHENTICATION_MID_EMAIL_FIELD=email
AUTHENTICATION_MID_FAMILY_NAME_FIELD=FamilyName
AUTHENTICATION_MID_STUDENT_CODE_FIELD=Codigo
AUTHENTICATION_MID_STATE_FIELD=Estado
```

### Autenticacion institucional

El acceso operativo a `/gestion/` puede funcionar de dos formas:

- con `SSO_ENABLED=False`, el flujo `/auth/login/wso2/` redirige al login local de Django admin para desarrollo o contingencia;
- con `SSO_ENABLED=True`, Django usa OIDC contra WSO2 y solo concede acceso backoffice a usuarios con el rol configurado en `OIDC_WSO2_STAFF_ROLE`.
- con `AUTHENTICATION_MID_ENABLED=True`, despues de recibir el token OIDC se consulta `autenticacion_mid` con `Authorization: Bearer <access_token>` y cuerpo `{"user": "<correo institucional>"}`; la respuesta institucional se guarda en sesion y sus roles se usan como fuente para la validacion de acceso.
- los perfiles de estudiante no crean usuario local; el usuario local sombra se mantiene solo para personal operativo que entra a backoffice.

Recomendacion institucional:

- Django solo con WSO2/Outlook OIDC como proveedor de autenticacion.
- `autenticacion_mid` como fuente de documento, codigo estudiantil, estado y roles institucionales.

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

Verificar que no existan cambios pendientes:

```bash
uv run python manage.py makemigrations --check
```

## Ejecucion local

Con variables ya cargadas:

```bash
uv run python manage.py runserver
```

## Ejecucion con Docker

El `compose.yaml` incluido esta pensado para desarrollo local y como base tecnica de despliegue. No es una configuracion productiva final: usa `runserver`, no configura HTTPS y requiere endurecer secretos y servidor WSGI para produccion.

Docker Compose usa los valores de `.env` si existe para secretos, base de datos y SSO. Para que el entorno local sea reproducible, `DEBUG=True` y `DB_HOST=db` quedan fijados dentro del compose.

Construir imagen:

```bash
docker compose build
```

Levantar Django y PostgreSQL:

```bash
docker compose up
```

Crear superusuario:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Ejecutar pruebas:

```bash
docker compose run --rm web python manage.py test
```

Puntos utiles:

- `GET /health/`
- `GET /admin/`
- `GET /auth/login/wso2/`
- `GET /auth/access-denied/`
- `GET /gestion/`
- `GET /gestion/ceremonias/plantilla-graduandos/`
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

Pruebas de importacion y backoffice:

```bash
uv run python manage.py test apps.graduates.tests_imports apps.backoffice.tests
```

Pruebas de autenticacion institucional:

```bash
uv run python manage.py test apps.accounts.tests
```

## Flujo funcional

### 1. Configuracion operativa

- Crear ceremonia.
- Crear graduandos manualmente o cargarlos desde Excel.
- La regla actual del flujo masivo es 3 invitaciones totales por graduando.
- Crear puntos de acceso si se validara en sitio.
- Ingresar al backoffice con SSO institucional por WSO2 o, en desarrollo, con el login local de Django si `SSO_ENABLED=False`.

### 2. Importacion masiva de graduandos

La carga masiva funciona en dos pasos: `validar -> confirmar`.

Formas de entrada:

- crear una ceremonia sin archivo,
- crear una ceremonia con archivo `.xlsx` opcional,
- cargar el archivo despues sobre una ceremonia ya creada.

Plantilla oficial:

- `GET /gestion/ceremonias/plantilla-graduandos/`

Columnas esperadas:

- `codigo_estudiantil`
- `tipo_documento`
- `numero_documento`
- `nombre_completo`
- `correo_institucional`
- `programa_academico`

Reglas del flujo:

- el preview no guarda graduandos ni crea invitaciones,
- la confirmacion solo se habilita si no hay errores,
- el lote es todo o nada,
- si el graduando no existe, se crea con `invitation_quota = 3`,
- si ya existe, se actualiza y se completan invitaciones faltantes hasta 3,
- si ya tiene 3 invitaciones, no se crean duplicados,
- si ya tiene mas de 3 invitaciones, la fila queda bloqueada para revision manual.

Rutas del flujo:

- `GET/POST /gestion/ceremonias/<pk>/graduandos/importar/`
- `GET /gestion/ceremonias/<pk>/graduandos/importaciones/<batch_id>/preview/`
- `POST /gestion/ceremonias/<pk>/graduandos/importaciones/<batch_id>/confirmar/`

### 3. Emision de invitaciones

Por backoffice:

- `/gestion/graduandos/` para generar por graduando.
- `/gestion/ceremonias/` para generar por ceremonia.

Por comando:

```bash
uv run python manage.py issue_invitations --graduate-id 1
uv run python manage.py issue_invitations --ceremony-code GRADOS-2026-01
```

### 4. Activos generados

- URL de validacion con token firmado
- PDF de invitacion
- QR derivado de la URL de validacion

Rutas relevantes:

- `GET /invitaciones/validar/?token=...`
- `POST /invitaciones/usar/`
- `GET /invitaciones/descargar/?token=...`
- `GET /invitaciones/qr/<public_id>/` solo para personal `is_staff`

### 5. Validacion de ingreso

- El QR lleva a la pantalla de validacion.
- El sistema muestra si la invitacion esta valida, usada, anulada o no existe.
- Personal `is_staff` puede marcarla como usada.
- Cada consulta genera trazabilidad operativa.

### 6. Regeneracion y anulacion

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
- las invitaciones iniciales segun el cupo configurado en cada graduando demo.

Esto deja el proyecto listo para revisar el flujo funcional desde `/gestion/` y `/admin/`.

## Seguridad y operacion

- El QR y los enlaces usan token firmado; modificar el token invalida la firma.
- El acceso a `/gestion/` usa SSO institucional por OIDC cuando `SSO_ENABLED=True`.
- El usuario local de backoffice se aprovisiona al primer login usando `issuer + sub` como identidad estable.
- El rol institucional configurado en WSO2 controla la asignacion de `is_staff` para backoffice.
- `/admin/` se mantiene como contingencia tecnica local y no como entrada operativa principal.
- Los QR preview directos requieren sesion staff.
- La carga masiva guarda solo metadatos y snapshot de validacion; no persiste el Excel original.
- La confirmacion del lote es transaccional y no permite importacion parcial en esta fase.
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
