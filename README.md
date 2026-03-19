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
apps/invitations/     Invitaciones, puntos de acceso y registros de validación
docs/adr/             Decisiones arquitectónicas
```

## Modelo de dominio actual

- Una `Ceremony` agrupa graduandos y puntos de acceso.
- Un `Graduate` pertenece a una ceremonia y define su `invitation_quota`.
- Una `Invitation` pertenece a un graduando, tiene `sequence_number`, `public_id`, `code`, `token_version` y estado.
- Un `AccessPoint` representa una puerta, filtro o punto operativo de validación para una ceremonia.
- Un `ValidationLog` registra cada intento de validación con resultado, usuario, punto de acceso, dispositivo, IP y agente de usuario.

La estrategia del QR queda preparada para token firmado con `public_id + token_version`, sin almacenar el token en texto plano ni su hash persistente.

## Emision de invitaciones

La generacion de activos se hace bajo demanda:

- el token se firma con `public_id + token_version`,
- el QR se genera como PNG en memoria,
- el PDF se genera en memoria con ReportLab,
- no se almacenan archivos binarios en base de datos ni en disco,
- si una invitacion debe regenerarse, se rota `token_version` y los activos se reconstruyen con el nuevo token.

Rutas disponibles:

- `GET /invitaciones/validar/?token=...`
- `POST /invitaciones/usar/`
- `GET /invitaciones/descargar/?token=...`
- `GET /invitaciones/qr/<public_id>/`

Comandos disponibles:

```bash
uv run python manage.py issue_invitations --graduate-id 1
uv run python manage.py issue_invitations --ceremony-code GRADOS-2026-01
uv run python manage.py regenerate_invitation --code INV-XXXXXXXXXXXX
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

## Probar la generacion localmente

1. Crea una ceremonia y un graduando desde `/admin/`.
2. Asegura que el graduando tenga `academic_program` y `invitation_quota` configurados.
3. Genera las invitaciones:

```bash
set -a
source .env
set +a
uv run python manage.py issue_invitations --graduate-id <ID_DEL_GRADUANDO>
```

4. El comando imprimira las URLs de validacion y descarga del PDF.
5. Abre la URL `descargar` en el navegador para ver el PDF.
6. Abre la URL `validar` para comprobar que el token firmado es verificable.
7. Si necesitas invalidar el QR anterior y regenerar la invitacion:

```bash
set -a
source .env
set +a
uv run python manage.py regenerate_invitation --code <CODIGO_INVITACION>
```

La nueva URL de validacion dejara de coincidir con el token anterior porque cambia `token_version`.

## Flujo de validacion en ingreso

- El QR dirige a `GET /invitaciones/validar/?token=...`.
- La pantalla muestra uno de estos estados: valida, ya utilizada, anulada o inexistente.
- Cada consulta registra trazabilidad basica en `ValidationLog`.
- Marcar una invitacion como usada requiere sesion autenticada de personal `is_staff`.
- El marcado se hace con `POST /invitaciones/usar/` y usa bloqueo transaccional para evitar doble uso accidental.
- La vista esta optimizada para celular y puede asociar un punto de acceso activo cuando exista.

### Probar el flujo localmente

1. Crea o reutiliza un usuario con permisos de staff:

```bash
set -a
source .env
set +a
uv run python manage.py createsuperuser
```

2. Desde `/admin/`, crea:
- una ceremonia
- uno o mas puntos de acceso para esa ceremonia
- un graduando con `academic_program` y `invitation_quota`

3. Genera las invitaciones:

```bash
set -a
source .env
set +a
uv run python manage.py issue_invitations --graduate-id <ID_DEL_GRADUANDO>
```

4. Abre en el navegador del celular o del computador la URL `validar` que imprime el comando.
5. Confirma que la pantalla muestre `Invitacion valida`.
6. Inicia sesion en `/admin/login/` con el usuario staff y vuelve a la URL de validacion.
7. Usa el boton `Marcar como usada`.
8. Recarga o escanea de nuevo el mismo QR: ahora debe mostrarse `Invitacion ya utilizada`.

### Verificar trazabilidad

En `/admin/` revisa:

- `Invitaciones`: estado `Usada`, fecha y usuario de validacion.
- `Registros de validacion`: resultado, IP, user agent, punto de acceso y si la accion marco la invitacion como usada.

## Interfaz administrativa para Secretaria Academica

Ademas del admin tecnico de Django, el proyecto incluye un backoffice minimo en:

- `GET /gestion/`

Funciones disponibles:

- crear y editar ceremonias,
- registrar y editar graduandos,
- definir el numero de invitaciones por graduando,
- generar invitaciones por graduando o por ceremonia,
- listar invitaciones generadas,
- consultar estado de validacion,
- descargar el PDF de una invitacion,
- anular invitaciones no usadas.

### Uso basico

1. Inicia sesion con un usuario `is_staff`.
2. Abre `/gestion/`.
3. Crea la ceremonia en `Ceremonias`.
4. Registra graduandos en `Graduandos`.
5. Usa `Generar` para emitir invitaciones.
6. Consulta y administra el resultado en `Invitaciones`.

### Notas operativas

- La anulacion de invitaciones bloquea su uso posterior.
- No se permite anular una invitacion que ya fue utilizada.
- El backoffice reutiliza la autenticacion de Django y mantiene el codigo simple; no reemplaza el admin tecnico, lo complementa.
