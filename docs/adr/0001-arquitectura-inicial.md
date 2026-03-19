# ADR 0001: Arquitectura inicial del proyecto

## Estado

Aprobado

## Contexto

El proyecto parte desde cero y debe entregar una primera versión funcional rápidamente, con administración simple, trazabilidad y base clara para crecer.

## Decisión

Se adopta un monolito modular en `Django 4.2 LTS` con `PostgreSQL`.

La primera versión se organiza en apps separadas por dominio:

- `core`
- `ceremonies`
- `graduates`
- `invitations`

## Justificación

- Django reduce tiempo de entrega porque ya incluye ORM, migraciones, autenticación y panel administrativo.
- El panel de administración nativo cubre la necesidad de una interfaz operativa inicial sin introducir un frontend separado.
- PostgreSQL es consistente con el entorno objetivo institucional y soporta bien el crecimiento posterior.
- El monolito modular evita complejidad prematura y mantiene separación clara por dominio.

## Consecuencias

- La aplicación prioriza velocidad de entrega y mantenibilidad sobre separación microservicios.
- La validación QR, la generación de PDF y la importación Excel se agregan en fases posteriores sobre esta base.
- La configuración depende de variables de entorno y no de utilidades externas para cargarlas automáticamente.
