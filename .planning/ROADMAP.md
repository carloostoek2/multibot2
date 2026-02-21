# Roadmap: Video Note Bot

**Project:** Video Note Bot
**Current Version:** v2.0 SHIPPED

## Milestones

- ✅ **v1.0 MVP** — Phases 1-2 (shipped 2026-02-14)
- ✅ **v2.0 Navaja Suiza de Audio** — Phases 3-8 (shipped 2026-02-21)

---

## Phase Overview

| Phase | Name | Requirements | Goal |
|-------|------|--------------|------|
| 3 | Voice Notes & Voice Message Processing | VN-01, VN-02, VN-03, VMP-01, VMP-02 | Usuarios pueden convertir archivos MP3 a notas de voz de Telegram y viceversa |
| 4 | Audio Split/Join | ASJ-01, ASJ-02, ASJ-03, ASJ-04, ASJ-05 | Usuarios pueden dividir archivos de audio en segmentos y unir múltiples archivos |
| 5 | Audio Format Conversion | AFC-01, AFC-02, AFC-03 | Usuarios pueden convertir archivos de audio entre múltiples formatos |
| 6 | Audio Enhancement | AE-01, AE-02, AE-03, AE-04 | Usuarios pueden aplicar mejoras de audio: bass boost, treble boost, y ecualización |
| 7 | Audio Effects | AFX-01, AFX-02, AFX-03, AFX-04 | Usuarios pueden aplicar efectos profesionales: reducción de ruido, compresión, normalización |
| 8 | Interfaz de usuario con menú inline | UI-01, UI-02, UI-03 | Usuarios pueden acceder a todas las funcionalidades vía menú inline contextual según tipo de archivo |

---

<details>
<summary>✅ v1.0 MVP (Phases 1-2) — SHIPPED 2026-02-14</summary>

- [x] Phase 1: Core Video Processing (3/3 plans) — completed 2026-02-13
- [x] Phase 1.1: Expandir procesamiento (3/3 plans) — completed 2026-02-13
- [x] Phase 2: Error Handling & Config (5/5 plans) — completed 2026-02-14

**Archive:** [v1.0 Roadmap](milestones/v1.0-ROADMAP.md) | [v1.0 Requirements](milestones/v1.0-REQUIREMENTS.md)

</details>

<details>
<summary>✅ v2.0 Navaja Suiza de Audio (Phases 3-8) — SHIPPED 2026-02-21</summary>

- [x] Phase 3: Voice Notes & Voice Message Processing (3/3 plans) — completed 2026-02-18
- [x] Phase 4: Audio Split/Join (3/3 plans) — completed 2026-02-18
- [x] Phase 5: Audio Format Conversion (3/3 plans) — completed 2026-02-19
- [x] Phase 6: Audio Enhancement (3/3 plans) — completed 2026-02-19
- [x] Phase 7: Audio Effects (4/4 plans) — completed 2026-02-20
- [x] Phase 8: Interfaz de usuario con menú inline (4/4 plans) — completed 2026-02-20

**Archive:** [v2.0 Roadmap](milestones/v2.0-ROADMAP.md) | [v2.0 Requirements](milestones/v2.0-REQUIREMENTS.md)

</details>

---

### 📋 Next Milestone (Planned)

No phases planned yet. Use `/gsd:new-milestone` to start planning v2.1 or v3.0.

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Video Processing | v1.0 | 3/3 | Complete | 2026-02-13 |
| 1.1. Expandir procesamiento | v1.0 | 3/3 | Complete | 2026-02-13 |
| 2. Error Handling & Config | v1.0 | 5/5 | Complete | 2026-02-14 |
| 3. Voice Notes & VMP | v2.0 | 3/3 | Complete | 2026-02-18 |
| 4. Audio Split/Join | v2.0 | 3/3 | Complete | 2026-02-18 |
| 5. Audio Format Conversion | v2.0 | 3/3 | Complete | 2026-02-19 |
| 6. Audio Enhancement | v2.0 | 3/3 | Complete | 2026-02-19 |
| 7. Audio Effects | v2.0 | 4/4 | Complete | 2026-02-20 |
| 8. Interfaz de usuario con menú inline | v2.0 | 4/4 | Complete | 2026-02-20 |

**Coverage:** 21/21 v2.0 requirements mapped ✓ (+ 3 UI requirements)

---

*Last updated: 2026-02-21 — v2.0 milestone complete*

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
*For v2.0 archive, see .planning/milestones/v2.0-ROADMAP.md*
