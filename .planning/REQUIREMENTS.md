# Requirements: Video Note Bot

**Defined:** 2025-02-03
**Core Value:** El usuario envía un video y recibe inmediatamente una nota de video circular, sin fricción ni pasos intermedios.

## v1 Requirements

### Core Functionality

- [ ] **CORE-01**: Bot detecta automáticamente cuando un usuario envía un video
- [ ] **CORE-02**: Bot descarga el video recibido para procesamiento
- [ ] **CORE-03**: Bot convierte el video a formato 1:1 (cuadrado) centrado
- [ ] **CORE-04**: Bot envía el resultado como nota de video de Telegram
- [ ] **CORE-05**: Proceso completo sin necesidad de comandos del usuario

### Video Processing

- [ ] **PROC-01**: Videos se recortan a formato circular usando ffmpeg
- [ ] **PROC-02**: Duración máxima respetada (60 segundos, truncar si es mayor)
- [ ] **PROC-03**: Resolución de salida apropiada para video notes (max 640x640)
- [ ] **PROC-04**: Calidad de video razonable manteniendo tamaño de archivo manejable

### Error Handling

- [ ] **ERR-01**: Notificar al usuario si el video no puede procesarse
- [ ] **ERR-02**: Limpiar archivos temporales después de procesamiento (exitoso o fallido)
- [ ] **ERR-03**: Timeout razonable para evitar bloqueos en videos problemáticos

### Bot Configuration

- [ ] **CONF-01**: Configuración mediante variables de entorno (BOT_TOKEN)
- [ ] **CONF-02**: Logging básico de operaciones

## v2 Requirements

### Features

- **FEAT-01**: Soporte para videos enviados como archivo (document) en lugar de video
- **FEAT-02**: Barra de progreso mientras se procesa el video
- **FEAT-03**: Estadísticas de uso (cuántos videos procesados)
- **FEAT-04**: Opción de ajustar el punto de recorte (centrado/arriba/abajo)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Múltiples videos simultáneos | Simplifica MVP, procesamiento uno a la vez |
| Panel web de administración | Overkill para funcionalidad simple |
| Base de datos | No es necesario persistir estado |
| Soporte para otros formatos de salida | Solo video notes, requisito específico |
| Procesamiento asíncrono con colas | Overkill para MVP, procesamiento directo |
| Edición de video (filtros, etc) | Fuera del scope, solo conversión de formato |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Complete |
| CORE-02 | Phase 1 | Complete |
| CORE-03 | Phase 1 | Complete |
| CORE-04 | Phase 1 | Complete |
| CORE-05 | Phase 1 | Complete |
| PROC-01 | Phase 1 | Complete |
| PROC-02 | Phase 1 | Complete |
| PROC-03 | Phase 1 | Complete |
| PROC-04 | Phase 1 | Complete |
| ERR-01 | Phase 2 | Complete |
| ERR-02 | Phase 2 | Complete |
| ERR-03 | Phase 2 | Complete |
| CONF-01 | Phase 2 | Complete |
| CONF-02 | Phase 2 | Complete |

**Coverage:**
- v1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2025-02-03*
*Last updated: 2025-02-03 after initial definition*
