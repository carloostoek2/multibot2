---
created: 2026-03-11T06:16:24.806Z
title: Crear servicio de menú para consistencia de flujos y navegación
area: ui
files:
  - bot/handlers/
  - bot/services/
---

## Problem

Actualmente cada flujo (video, audio, descarga, etc.) implementa sus propios menús inline de forma inconsistente:
- Diferentes patrones de callback
- Navegación "Atrás" implementada de distintas maneras
- Cancelación en pasos intermedios no siempre funciona igual
- Estados del flujo dispersos en user_data sin estructura común

Esto genera:
- Código duplicado en handlers
- UX inconsistente para el usuario
- Dificultad para mantener y agregar nuevos flujos
- Bugs de navegación cuando el usuario usa "Atrás" o "Cancelar"

## Solution

Crear un `MenuService` (o `FlowNavigator`) que provea:

1. **Definición declarativa de flujos**: Cada flujo se define como un grafo de estados con transiciones permitidas
2. **Navegación automática**: Botón "Atrás" que funciona sin código adicional del handler
3. **Estado centralizado**: SessionState que rastrea el flujo actual, paso, y datos temporales
4. **Callbacks unificados**: Patrón consistente `flow:action:step` para todos los menús
5. **Helpers para builders**: Funciones para crear teclados inline con navegación incluida

Estructura propuesta:
```python
class FlowNavigator:
    def register_flow(self, flow_id: str, steps: list[FlowStep])
    def handle_callback(self, callback_data: str) -> FlowAction
    def go_back(self, session: SessionState) -> str  # retorna nuevo paso
    def build_keyboard(self, step: FlowStep) -> InlineKeyboardMarkup
```

Flujos a migrar:
- Conversión de video → nota de video
- Procesamiento de audio (split, join, efectos)
- Descarga de URLs (con menú simplificado)
- Configuración del bot
