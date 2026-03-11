---
created: 2026-03-11T06:19:02.806Z
title: Crear servicio batch para descargas por lotes desde Instagram
area: downloader
files:
  - bot/services/batch/
  - bot/handlers/batch_download.py
  - bot/services/download/
---

## Problem

Actualmente el bot solo puede procesar una URL a la vez. Los usuarios que quieren descargar múltiples posts de Instagram deben enviar una URL, esperar a que termine, y luego enviar la siguiente. Esto es tedioso cuando se quieren descargar 5-10 posts.

## Solution

Crear un `BatchDownloadService` que permita:

1. **Recepción múltiple**: Aceptar 5-10 URLs de Instagram en un solo mensaje (una por línea o separadas por espacios)
2. **Procesamiento cola**: Encolar las descargas y procesarlas secuencialmente o con concurrencia limitada
3. **Progreso agregado**: Mostrar progreso general (3/10 completadas) además del progreso individual
4. **Resumen final**: Al terminar, mostrar estadísticas (exitosas, fallidas, tamaño total)
5. **Manejo de errores granular**: Si una URL falla, continuar con las demás y reportar cuáles fallaron

Arquitectura propuesta:
```python
class BatchDownloadService:
    def __init__(self, download_facade: DownloadFacade)
    async def process_batch(
        self,
        urls: list[str],
        user_id: int,
        progress_callback: Callable[[BatchProgress], Awaitable[None]]
    ) -> BatchResult

@dataclass
class BatchProgress:
    total: int
    completed: int
    failed: int
    current_url: str
    current_progress: float  # % de la descarga actual

@dataclass
class BatchResult:
    successful: list[DownloadedFile]
    failed: list[tuple[str, str]]  # (url, error_message)
    total_size: int
    duration_seconds: float
```

Flujo de validación (Instagram primero):
- Detectar todas las URLs de Instagram en el mensaje
- Validar que sean posts/reels válidos antes de iniciar
- Procesar con límite de concurrencia (ej: 2 simultáneas)
- Enviar archivos a medida que se completan (no esperar al final)

Consideraciones:
- Límite de rate de Telegram (20 msgs/minuto en grupos)
- Límite de memoria si se acumulan archivos grandes
- Posibilidad de cancelar el batch en curso
- Integración con DownloadFacade existente
