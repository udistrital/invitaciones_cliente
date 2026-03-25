# Mejoras Futuras

Lista corta de mejoras recomendadas para evolucionar el proyecto despues de la revision tecnica inicial.

## Prioridad alta

- Configurar un pipeline CI que ejecute `check`, `makemigrations --check` y tests en cada cambio.
- Externalizar configuracion sensible para despliegues institucionales con secretos reales y `DEBUG=False`.
- Incorporar almacenamiento y entrega controlada de PDFs si el flujo requiere distribucion masiva por correo o portal.
- Definir respaldo y restauracion de PostgreSQL con criterios de operacion y auditoria.

## Prioridad media

- Agregar importacion masiva de graduandos desde Excel o CSV con validaciones de negocio.
- Incorporar expiracion temporal opcional para tokens de invitacion si el proceso operativo lo exige.
- Mejorar observabilidad con logging estructurado y alertas basicas para errores de validacion y acceso.
- Agregar paginacion y filtros mas avanzados en backoffice cuando el volumen crezca.

## Prioridad baja

- Refinar el diseno visual del PDF institucional con plantilla aprobada por comunicaciones.
- Agregar exportes administrativos de invitados, accesos y trazabilidad.
- Incorporar pruebas end-to-end de navegacion para los flujos criticos del backoffice.
