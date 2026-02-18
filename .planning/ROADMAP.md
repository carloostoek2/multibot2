# Roadmap: Video Note Bot

**Project:** Video Note Bot
**Current Version:** v2.0 IN PROGRESS

## Milestones

- ✅ **v1.0 MVP** — Phases 1-2 (shipped 2026-02-14)
- 🚧 **v2.0 Navaja Suiza de Audio** — Phases 3-7 (in progress)

---

## Phase Overview

| Phase | Name | Requirements | Goal |
|-------|------|--------------|------|
| 3 | Voice Notes & Voice Message Processing | VN-01, VN-02, VN-03, VMP-01, VMP-02 | Usuarios pueden convertir archivos MP3 a notas de voz de Telegram y viceversa |
| 4 | Audio Split/Join | ASJ-01, ASJ-02, ASJ-03, ASJ-04, ASJ-05 | Usuarios pueden dividir archivos de audio en segmentos y unir múltiples archivos |
| 5 | Audio Format Conversion | AFC-01, AFC-02, AFC-03 | Usuarios pueden convertir archivos de audio entre múltiples formatos |
| 6 | Audio Enhancement | AE-01, AE-02, AE-03, AE-04 | Usuarios pueden aplicar mejoras de audio: bass boost, treble boost, y ecualización |
| 7 | Audio Effects | AFX-01, AFX-02, AFX-03, AFX-04 | Usuarios pueden aplicar efectos profesionales: reducción de ruido, compresión, normalización |

---

## Phase 3: Voice Notes & Voice Message Processing

**Goal:** Usuarios pueden convertir archivos MP3 a notas de voz de Telegram y viceversa.

**Requirements:** VN-01, VN-02, VN-03, VMP-01, VMP-02

**Dependencies:** None (builds on v1.0 foundation)

**Success Criteria:**

1. Usuario envía archivo MP3 y recibe nota de audio (voice note) de Telegram en formato OGG Opus
2. Archivos MP3 de más de 20 minutos son truncados automáticamente al límite de Telegram
3. Usuario envía nota de voz (voice message) y recibe archivo MP3 descargable
4. Bot detecta automáticamente notas de voz entrantes sin necesidad de comandos
5. Conversión preserva calidad de audio dentro de límites razonables de tamaño

**Plans:** 3 plans

Plans:
- [x] 03-01-PLAN.md — Crear módulo audio_processor.py con clases de conversión (VoiceNoteConverter, VoiceToMp3Converter), configuración y validación
- [x] 03-02-PLAN.md — Implementar handler para archivos de audio a voice notes (MP3 → OGG Opus)
- [x] 03-03-PLAN.md — Implementar detección automática y conversión de voice messages a MP3

---

## Phase 4: Audio Split/Join

**Goal:** Usuarios pueden dividir archivos de audio en segmentos y unir múltiples archivos.

**Requirements:** ASJ-01, ASJ-02, ASJ-03, ASJ-04, ASJ-05

**Dependencies:** Phase 3 (usa infraestructura de procesamiento de audio)

**Success Criteria:**

1. Usuario puede usar comando /split_audio para dividir audio en segmentos de duración especificada (ej: cada 30 segundos)
2. Usuario puede usar comando /split_audio para dividir audio en N segmentos iguales
3. Usuario puede usar comando /join_audio para unir múltiples archivos de audio en uno solo
4. Split genera archivos numerados secuencialmente (part1, part2, etc.)
5. Join acepta múltiples archivos en un solo mensaje o en secuencia

**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md — Crear AudioSplitter class para dividir archivos de audio por duración o número de partes
- [x] 04-02-PLAN.md — Crear AudioJoiner class para unir múltiples archivos de audio
- [x] 04-03-PLAN.md — Implementar comandos /split_audio y /join_audio con handlers

---

## Phase 5: Audio Format Conversion

**Goal:** Usuarios pueden convertir archivos de audio entre múltiples formatos.

**Requirements:** AFC-01, AFC-02, AFC-03

**Dependencies:** Phase 3 (usa infraestructura base de conversión)

**Success Criteria:**

1. Usuario puede usar comando /convert_audio con selección de formato de salida (MP3, WAV, OGG, AAC, FLAC)
2. Conversión soporta todos los formatos: MP3, WAV, OGG, AAC, FLAC
3. Metadatos del audio (título, artista, etc.) se preservan cuando el formato lo permite
4. Bot detecta formato de entrada automáticamente
5. Archivos convertidos mantienen calidad apropiada para el formato seleccionado

---

## Phase 6: Audio Enhancement

**Goal:** Usuarios pueden aplicar mejoras de audio: bass boost, treble boost, y ecualización.

**Requirements:** AE-01, AE-02, AE-03, AE-04

**Dependencies:** Phase 3 (usa infraestructura de procesamiento ffmpeg)

**Success Criteria:**

1. Usuario puede usar comando /bass_boost con parámetro de intensidad para aumentar frecuencias bajas
2. Usuario puede usar comando /treble_boost con parámetro de intensidad para aumentar frecuencias altas
3. Usuario puede usar comando /equalize para ajustar 3 bandas: bass, mid, treble
4. Parámetros de intensidad son ajustables (ej: nivel 1-10 o porcentaje)
5. Procesamiento aplica filtros ffmpeg apropiados sin distorsión excesiva

---

## Phase 7: Audio Effects

**Goal:** Usuarios pueden aplicar efectos profesionales: reducción de ruido, compresión, normalización.

**Requirements:** AFX-01, AFX-02, AFX-03, AFX-04

**Dependencies:** Phase 3, Phase 6 (usa infraestructura de filtros ffmpeg)

**Success Criteria:**

1. Usuario puede usar comando /denoise para aplicar reducción de ruido de fondo
2. Usuario puede usar comando /compress para aplicar compresión de rango dinámico
3. Usuario puede usar comando /normalize para normalizar el volumen del audio
4. Nivel de efecto es ajustable donde aplique (intensidad de reducción de ruido, ratio de compresión)
5. Efectos pueden combinarse en pipeline (ej: denoise → normalize)

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Video Processing | v1.0 | 3/3 | Complete | 2026-02-13 |
| 1.1. Expandir procesamiento | v1.0 | 3/3 | Complete | 2026-02-13 |
| 2. Error Handling & Config | v1.0 | 5/5 | Complete | 2026-02-14 |
| 3. Voice Notes & VMP | v2.0 | 3/3 | Complete | 2026-02-18 |
| 4. Audio Split/Join | v2.0 | 3/3 | Complete | 2026-02-18 |
| 5. Audio Format Conversion | v2.0 | 0/3 | Pending | — |
| 6. Audio Enhancement | v2.0 | 0/4 | Pending | — |
| 7. Audio Effects | v2.0 | 0/4 | Pending | — |

**Coverage:** 21/21 v2.0 requirements mapped ✓

---

## Technical Notes

**Common Patterns (from v1.0):**
- Usar TempManager para limpieza automática de archivos temporales
- Usar BotConfig para parámetros configurables
- Usar ffmpeg para todo procesamiento de audio
- Validación pre-procesamiento: tamaño, integridad, espacio en disco
- Manejo de errores con retry logic y correlation IDs
- Procesamiento síncrono (un archivo a la vez)

**Audio-Specific Considerations:**
- Voice notes de Telegram requieren formato OGG Opus
- Duración máxima voice notes: ~20 minutos
- Preservar calidad de audio en conversiones
- Metadatos ID3 cuando aplique

---

*For v1.0 archive, see .planning/milestones/v1.0-ROADMAP.md*

*Last updated: 2026-02-18 — Phase 4 complete*
