# Video Note Bot

## What This Is

Un bot de Telegram que recibe videos enviados por usuarios y los convierte automáticamente en notas de video (video notes) circulares de Telegram, sin necesidad de comandos ni interacción adicional.

## Core Value

El usuario envía un video y recibe inmediatamente una nota de video circular, sin fricción ni pasos intermedios.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] El bot recibe videos automáticamente cuando un usuario los envía
- [ ] Procesa el video recortándolo a formato circular (video note)
- [ ] Envía el resultado de vuelta como nota de video de Telegram
- [ ] No requiere comandos ni interacción adicional del usuario
- [ ] Maneja los límites técnicos de Telegram para video notes

### Out of Scope

- Soporte para múltiples videos simultáneos — el MVP se enfoca en uno a la vez
- Edición manual del recorte circular — el recorte es automático centrado
- Compresión avanzada de video — usar configuraciones razonables por defecto
- Panel de administración o estadísticas — no es necesario para MVP
- Soporte para otros formatos de salida — solo video notes

## Context

Las notas de video de Telegram son videos circulares que se reproducen en burbujas tipo chat. Tienen restricciones específicas:
- Máximo generalmente 1 minuto de duración
- Formato 1:1 (cuadrado) que se muestra como círculo
- Tamaño de archivo limitado

El bot debe procesar videos de cualquier duración pero respetar los límites de Telegram, posiblemente recortando si es necesario.

## Constraints

- **Tech stack**: Python con python-telegram-bot (más maduro para este caso de uso)
- **Procesamiento**: ffmpeg para manipulación de video
- **Hosting**: Debe funcionar en entornos con recursos limitados (CPU/memoria)
- **Formato de salida**: Video note de Telegram (circular, 1:1)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| python-telegram-bot | Librería más estable para bots de Telegram en Python | — Pending |
| ffmpeg | Standard para procesamiento de video | — Pending |
| Procesamiento síncrono | Simplifica MVP, un video a la vez | — Pending |

---
*Last updated: 2025-02-03 after initialization*
