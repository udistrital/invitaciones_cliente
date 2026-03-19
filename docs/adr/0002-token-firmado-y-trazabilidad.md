# ADR 0002: Token firmado y trazabilidad de validación

## Estado

Aprobado

## Contexto

El modelo inicial de invitaciones guardaba un `token_hash`, pero eso dejaba abierta una decisión importante: cómo regenerar el QR sin persistir secretos en texto plano y cómo capturar trazabilidad suficiente del proceso de ingreso.

## Decisión

- La invitación usará un token firmado a partir de `public_id` y `token_version`.
- El modelo no almacenará el token completo ni un hash persistente del token.
- La validación registrará usuario autenticado opcional, punto de acceso por ceremonia, etiqueta de dispositivo, IP y `user_agent`.
- El resultado operativo exitoso quedará resumido también en la propia `Invitation` mediante `used_by`, `used_access_point`, `used_device_label`, `used_from_ip` y `used_at`.

## Justificación

- El token firmado permite regenerar la invitación sin guardar secretos reutilizables en base de datos.
- `token_version` deja espacio para rotación futura del QR sin rediseñar el modelo.
- El punto de acceso por ceremonia mejora auditoría, operación en sitio y reportes.
- El resumen de uso en `Invitation` acelera consultas administrativas, mientras `ValidationLog` conserva el historial completo.

## Consecuencias

- La lógica de firma y verificación del QR deberá implementarse en la siguiente fase.
- La regla `sequence_number <= invitation_quota` se valida en modelo/servicio, no como constraint SQL entre tablas.
- La trazabilidad queda preparada para escenarios con operador autenticado y también para validación anónima asistida por dispositivo/punto de acceso.
