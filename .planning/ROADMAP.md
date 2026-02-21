# Roadmap: Video Note Bot

**Project:** Video Note Bot
**Current Version:** v3.0 IN PROGRESS

---

## Milestones

- ✅ **v1.0 MVP** — Phases 1-2 (shipped 2026-02-14)
- ✅ **v2.0 Navaja Suiza de Audio** — Phases 3-8 (shipped 2026-02-21)
- 🔄 **v3.0 Downloader** — Phases 9-12 (in progress)

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
| **9** | **Downloader Core Infrastructure** | DL-01~07, QF-01~05, EH-01~02 | Bot detecta URLs automáticamente y descarga videos de cualquier fuente |
| **10** | **Platform Handlers** | YT-01~04, IG-01~03, TT-01~02, TW-01~02, FB-01~02, GV-01~04 | Soporte específico para YouTube, Instagram, TikTok, Twitter/X, Facebook y URLs genéricas |
| **11** | **Download Management & Progress** | DM-01~05, PT-01~05, EH-03~05 | Descargas concurrentes con progreso en tiempo real y manejo robusto de errores |
| **12** | **Integration & Polish** | UI-01~06, INT-01~04 | Integración completa con herramientas existentes de video/audio |

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

<details>
<summary>🔄 v3.0 Downloader (Phases 9-12) — IN PROGRESS</summary>

### Phase 9: Downloader Core Infrastructure

**Goal:** Establish the foundation for media downloading with URL detection, validation, and generic download capabilities.

**Dependencies:** v2.0 complete (phases 3-8)

**Requirements:** DL-01, DL-02, DL-03, DL-04, DL-05, DL-06, DL-07, QF-01, QF-02, QF-03, QF-04, QF-05, EH-01, EH-02

**Plans:** 4 plans

**Plan list:**
- [x] 09-01-PLAN.md — URL Detection and Validation (auto-detect URLs, entity extraction, URL classification) — completed 2026-02-21
- [x] 09-02-PLAN.md — Base Downloader Architecture (abstract interface, DownloadOptions, exception hierarchy) — completed 2026-02-21
- [x] 09-03-PLAN.md — yt-dlp Integration (platform downloader with metadata extraction and progress hooks) — completed 2026-02-21
- [x] 09-04-PLAN.md — Generic HTTP Downloader (direct video URL support with streaming and integrity validation) — completed 2026-02-21

**Success Criteria:**
1. Bot automatically detects URLs in any message without requiring /download command
2. URLs are validated for format and accessibility before processing
3. Generic video URLs (.mp4, .webm, .mov) can be downloaded directly
4. Media metadata (title, duration, size) is extracted and displayed
5. Downloaded files pass integrity validation
6. Maximum quality is fetched by default with format conversion as needed
7. Clear error messages for invalid, private, or unsupported URLs

---

### Phase 10: Platform Handlers

**Goal:** Implement platform-specific downloaders for YouTube, Instagram, TikTok, Twitter/X, Facebook, and generic HTML pages.

**Dependencies:** Phase 9 complete

**Requirements:** YT-01, YT-02, YT-03, YT-04, IG-01, IG-02, IG-03, TT-01, TT-02, TW-01, TW-02, FB-01, FB-02, GV-01, GV-02, GV-03, GV-04

**Success Criteria:**
1. YouTube videos and Shorts download successfully (video and audio modes)
2. Instagram posts, Reels, and Stories download successfully
3. TikTok videos download without watermark when possible
4. Twitter/X video posts download with best available quality
5. Facebook public videos and Reels download successfully
6. Generic HTML pages with video tags are parsed and video extracted
7. Direct video file URLs are followed through redirects and downloaded
8. Each platform handler provides appropriate metadata

---

### Phase 11: Download Management & Progress

**Goal:** Implement concurrent download management, real-time progress tracking, and robust error handling.

**Dependencies:** Phase 10 complete

**Requirements:** DM-01, DM-02, DM-03, DM-04, DM-05, PT-01, PT-02, PT-03, PT-04, PT-05, EH-03, EH-04, EH-05

**Success Criteria:**
1. Multiple downloads can run concurrently without interference
2. Each download has unique correlation ID for tracing
3. Downloads are isolated in separate temp directories
4. Failed downloads are cleaned up automatically
5. Real-time percentage progress is displayed (updates every 5-10%)
6. Progress shows: percentage bar, downloaded/total size, speed
7. Retry logic handles transient network failures (3 attempts)
8. Rate limit detection triggers appropriate backoff
9. Stalled downloads timeout and fail gracefully

---

### Phase 12: Integration & Polish

**Goal:** Integrate downloads with existing video/audio processing tools and finalize the user experience.

**Dependencies:** Phase 11 complete

**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, INT-01, INT-02, INT-03, INT-04

**Success Criteria:**
1. /download command works with explicit URL argument
2. Inline menu appears automatically when URL is detected in message
3. Format selection menu offers video/audio options
4. Large downloads (>50MB) show confirmation prompt
5. Cancel button is available during active download
6. Downloaded videos can be converted to video notes via inline menu
7. Downloaded audio can be processed with audio tools via inline menu
8. "Download + Convert" flow works end-to-end
9. Recent downloads list shows last 5 items (ephemeral, per session)

</details>

---

## Progress

```
v3.0 Downloader
[████░░░░░░░░░░░░░░░░] 25% (1/4 phases)

Phase 9:  Downloader Core Infrastructure    [██████████] 100% (4/4 plans) — completed 2026-02-21
Phase 10: Platform Handlers                 [░░░░░░░░░░] 0% (0/N plans)
Phase 11: Download Management & Progress    [░░░░░░░░░░] 0% (0/N plans)
Phase 12: Integration & Polish              [░░░░░░░░░░] 0% (0/N plans)
```

---

## Historical Progress

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

---

## Requirements Coverage

### v3.0 Downloader (54 requirements)

| Category | Count | Phase |
|----------|-------|-------|
| Core Download (DL) | 7 | 9 |
| YouTube (YT) | 4 | 10 |
| Instagram (IG) | 3 | 10 |
| TikTok (TT) | 2 | 10 |
| Twitter/X (TW) | 2 | 10 |
| Facebook (FB) | 2 | 10 |
| Generic Video (GV) | 4 | 10 |
| Quality & Format (QF) | 5 | 9 |
| Download Management (DM) | 5 | 11 |
| Progress Tracking (PT) | 5 | 11 |
| User Interface (UI) | 6 | 12 |
| Error Handling (EH) | 5 | 9, 11 |
| Integration (INT) | 4 | 12 |
| **Total** | **54** | **4 phases** |

**Coverage:** 54/54 v3.0 requirements mapped ✓

---

## Technical Notes

**Common Patterns (from v1.0-v2.0):**
- Usar TempManager para limpieza automática de archivos temporales
- Usar BotConfig para parámetros configurables
- Usar ffmpeg para todo procesamiento de audio
- Validación pre-procesamiento: tamaño, integridad, espacio en disco
- Manejo de errores con retry logic y correlation IDs
- Procesamiento síncrono (un archivo a la vez)

**v3.0 Downloader Considerations:**
- yt-dlp para descarga de plataformas populares
- aiohttp/httpx para descargas concurrentes
- Progreso en tiempo real via callbacks
- Límites de tamaño de Telegram (20MB para bots, 50MB con files API)
- Manejo de rate limits por plataforma

---

*Last updated: 2026-02-21 — Phase 9 complete (4/4 plans executed)*

*For v1.0 archive, see .planning/milestones/v1.0-ROADMAP.md*
*For v2.0 archive, see .planning/milestones/v2.0-ROADMAP.md*
