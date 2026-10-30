# Video Note Bot

Bot de Telegram que convierte videos en notas de video circulares (video notes).

## Descripción

Este bot recibe videos de cualquier formato y los convierte automáticamente en notas de video circulares de Telegram, listas para compartir. El procesamiento es automático: solo envías un video y recibes la nota de video de vuelta.

**Características:**
- Conversión automática a formato circular
- Recorte centrado a proporción 1:1
- Redimensionamiento a 640x640 píxeles
- Límite automático de 60 segundos
- Sin audio (formato video note)

Historial de cambios: [CHANGELOG.md](CHANGELOG.md).

## Requisitos

Antes de comenzar, asegúrate de tener:

- **Python 3.9** o superior
- **ffmpeg** instalado en tu sistema
- Un **token de bot de Telegram** (obtenido de [@BotFather](https://t.me/botfather))

### Verificar requisitos

```bash
# Verificar Python
python --version  # Debe ser 3.9+

# Verificar ffmpeg
ffmpeg -version   # Debe mostrar información de ffmpeg
```

## Instalación

Sigue estos pasos para instalar el bot:

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd videonote-bot
```

### 2. Crear entorno virtual

```bash
python -m venv venv
```

### 3. Activar entorno virtual

**Linux/macOS:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

## Configuración

### 1. Crear archivo de configuración

```bash
cp .env.example .env
```

### 2. Obtener token de bot

1. Abre Telegram y busca [@BotFather](https://t.me/botfather)
2. Envía el comando `/newbot`
3. Sigue las instrucciones para crear tu bot
4. Copia el token proporcionado

### 3. Configurar variables de entorno

Edita el archivo `.env` y reemplaza `your_bot_token_here` con tu token:

```bash
BOT_TOKEN=tu_token_aqui
```

### 4. Clonación de voz (opcional)

«Clonar voz» puede usar un servidor Seed-VC propio por HTTP o FreeVC en Replicate:

- `VOICE_CLONE_BACKEND`: `auto` (por defecto; Seed-VC si `/health` responde con el modelo cargado y, si no, Replicate), `seedvc` (sin respaldo) o `replicate`.
- `REPLICATE_API_TOKEN`: solo hace falta si se usa Replicate.
- `SEEDVC_URL_FILE` y `SEEDVC_API_KEY_FILE`: archivos con la URL base y la clave de Seed-VC (por defecto `/home/ubuntu/seedvc-colab/url.txt` y `/home/ubuntu/seedvc-colab/api_key`). Se leen en cada clonación; URL vacía = Seed-VC apagado.
- Arranque bajo demanda: `SEEDVC_START_REQUEST_FILE` y `SEEDVC_STATE_FILE` (por defecto `start_request` y `state` en `/home/ubuntu/seedvc-colab/`), `SEEDVC_START_WAIT` (150 s), `SEEDVC_POLL_INTERVAL` (5 s) y `SEEDVC_DOWN_GRACE` (15 s).
- `VOICE_CLONE_TIMEOUT`: plazo de la clonación; el bot nunca usa menos de 300 s.

Detalle en `CHANGELOG.md` (2026-09-23 y 2026-10-26).

## Ejecución

Para iniciar el bot:

```bash
python run.py
```

Verás un mensaje como:
```
Starting bot...
```

El bot está funcionando cuando ves mensajes de log indicando que está escuchando mensajes.

Para detener el bot, presiona `Ctrl+C`.

## Uso

Una vez que el bot está ejecutándose:

1. **Busca tu bot en Telegram** por el nombre que le diste a @BotFather
2. **Envía `/start`** para recibir el mensaje de bienvenida
3. **Envía cualquier video** al bot (como archivo o video normal)
4. **Espera unos segundos** mientras procesa
5. **Recibe tu video note** circular listo para usar

### Ejemplo de uso

```
Usuario: /start
Bot: ¡Hola! Envíame un video y lo convertiré en una nota de video circular.
     El video debe ser de máximo 60 segundos.

Usuario: [envía video de 10 segundos]
Bot: [envía video note circular del mismo contenido]
```

## Limitaciones

- **Duración máxima:** 60 segundos (los videos más largos se truncan automáticamente)
- **Procesamiento:** Síncrono (un video a la vez)
- **Formato de salida:** MP4 sin audio
- **Resolución:** 640x640 píxeles máximo

## Solución de problemas

### Error "No pude descargar el video"

- Verifica tu conexión a internet
- Intenta con un video más pequeño
- El archivo podría estar corrupto

### Error "Hubo un problema procesando el video"

- Asegúrate de que sea un video válido
- Verifica que ffmpeg esté instalado correctamente
- Intenta con otro formato de video

### Error "El video tardó demasiado en procesarse"

- El video es muy largo o pesado
- Intenta con un video más corto
- El servidor podría estar sobrecargado

### El bot no responde

- Verifica que el token en `.env` sea correcto
- Asegúrate de que el entorno virtual esté activado
- Revisa los logs para ver errores

## Estructura del proyecto

```
videonote-bot/
├── bot/
│   ├── __init__.py
│   ├── config.py          # Configuración y variables de entorno
│   ├── error_handler.py   # Manejo centralizado de errores
│   ├── handlers.py        # Handlers de mensajes de Telegram
│   ├── main.py            # Punto de entrada principal
│   ├── temp_manager.py    # Gestión de archivos temporales
│   └── video_processor.py # Procesamiento con ffmpeg
├── .env                   # Variables de entorno (no incluir en git)
├── .env.example           # Ejemplo de variables de entorno
├── .gitignore
├── README.md              # Este archivo
├── requirements.txt       # Dependencias de Python
└── run.py                 # Script de ejecución
```

## Desarrollo

Para contribuir o modificar el bot:

1. Activa el entorno virtual
2. Instala dependencias de desarrollo (si las hay)
3. Realiza tus cambios
4. Prueba localmente antes de desplegar

## Licencia

Este proyecto es de código abierto. Consulta el archivo LICENSE para más detalles.

---

**Nota:** Este bot está diseñado para uso personal y educativo. Asegúrate de cumplir con los términos de servicio de Telegram al usarlo.
