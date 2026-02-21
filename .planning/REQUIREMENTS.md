# Requirements: v3.0 Downloader

## Overview

Milestone v3.0 adds media download capabilities to the Video Note Bot, allowing users to download videos and audio from popular platforms (YouTube, Instagram, TikTok, Twitter/X, Facebook) for subsequent processing with the existing video note and audio tools.

---

## v1 Requirements (v3.0 Downloader)

### Core Download Infrastructure

- [ ] **DL-01** — Bot can detect and parse URLs from supported platforms
- [ ] **DL-02** — Bot validates URL format and accessibility before download
- [ ] **DL-03** — Bot extracts media metadata (title, duration, uploader, thumbnail)
- [ ] **DL-04** — Download infrastructure supports both video and audio extraction
- [ ] **DL-05** — Downloaded files are validated for integrity and format
- [ ] **DL-06** — Bot auto-detects URLs in any message (no command required)
- [ ] **DL-07** — Generic video URL support (any URL containing video file)

### Platform Support

**YouTube**
- [ ] **YT-01** — Download YouTube videos (regular, Shorts)
- [ ] **YT-02** — Extract audio-only from YouTube videos
- [ ] **YT-03** — Support age-restricted content (if technically possible)
- [ ] **YT-04** — Handle playlists (optional, single video default)

**Instagram**
- [ ] **IG-01** — Download Instagram posts (single video)
- [ ] **IG-02** — Download Instagram Reels
- [ ] **IG-03** — Download Instagram Stories (if accessible)

**TikTok**
- [ ] **TT-01** — Download TikTok videos (no watermark preferred)
- [ ] **TT-02** — Handle TikTok slideshows with video conversion

**Twitter/X**
- [ ] **TW-01** — Download Twitter/X video posts
- [ ] **TW-02** — Handle multiple video variants (quality selection)

**Facebook**
- [ ] **FB-01** — Download Facebook public videos
- [ ] **FB-02** — Handle Facebook Reels

**Generic Video URLs**
- [ ] **GV-01** — Detect direct video file URLs (.mp4, .webm, .mov, etc.)
- [ ] **GV-02** — Extract video from HTML pages with video tags
- [ ] **GV-03** — Follow redirects to find actual video file
- [ ] **GV-04** — Validate content-type before download

### Quality & Format

- [ ] **QF-01** — Download maximum available quality by default
- [ ] **QF-02** — Video format preference: MP4 (H.264) for compatibility
- [ ] **QF-03** — Audio format preference: MP3 320k or source quality
- [ ] **QF-04** — Automatic format conversion if source incompatible
- [ ] **QF-05** — File size limits respected (Telegram bot constraints)

### Download Management

- [ ] **DM-01** — Unlimited concurrent downloads supported
- [ ] **DM-02** — Each download tracked with unique correlation ID
- [ ] **DM-03** — Downloads isolated in separate temp directories
- [ ] **DM-04** — Failed downloads cleaned up automatically
- [ ] **DM-05** — Download queue with fair scheduling

### Progress Tracking

- [ ] **PT-01** — Real-time percentage progress displayed to user
- [ ] **PT-02** — Progress updates sent every 5-10% or 3-5 seconds
- [ ] **PT-03** — Progress message includes: percentage, downloaded/total size, speed
- [ ] **PT-04** — Progress bar visualization (ASCII or emoji)
- [ ] **PT-05** — Final "complete" message with file info

### User Interface

- [ ] **UI-01** — `/download <url>` command initiates download
- [ ] **UI-02** — Auto-detect URL in any message and offer download menu
- [ ] **UI-03** — Inline menu for format selection (video/audio) when URL detected
- [ ] **UI-04** — Confirmation prompt before large downloads (>50MB)
- [ ] **UI-05** — Cancel button during active download
- [ ] **UI-06** — Recent downloads list (last 5, ephemeral)

### Error Handling

- [ ] **EH-01** — Graceful handling of unavailable/private content
- [ ] **EH-02** — Clear error messages for unsupported URLs
- [ ] **EH-03** — Retry logic for transient network failures
- [ ] **EH-04** — Timeout handling for stalled downloads
- [ ] **EH-05** — Rate limit detection and backoff for platform restrictions

### Integration

- [ ] **INT-01** — Downloaded videos can be processed to video notes
- [ ] **INT-02** — Downloaded audio can be processed with audio tools
- [ ] **INT-03** — Inline menu offers "Download + Convert" flow
- [ ] **INT-04** — Download history not persisted (privacy)

---

## Future Requirements (Deferred to v3.1+)

| ID | Requirement | Reason |
|----|-------------|--------|
| F-01 | Playlist/batch downloads | Complex UI, edge cases |
| F-02 | Subtitle/caption extraction | Low priority |
| F-03 | Custom quality selection (720p, 1080p) | Max quality is default |
| F-04 | Download history persistence | Privacy preference |
| F-05 | Scheduled downloads | Complex, low demand |
| F-06 | Live stream recording | Technical complexity |

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Private/account-required content | Authentication complexity, TOS concerns |
| DRM-protected content | Legal/technical barriers |
| 4K/8K downloads | File size limits, processing time |
| Real-time streaming | Different use case |
| Upload to cloud storage | Out of project scope |

---

## Platform Support Matrix

| Platform | Video | Audio | Metadata | Notes |
|----------|-------|-------|----------|-------|
| YouTube | ✓ | ✓ | ✓ | Priority platform |
| Instagram | ✓ | ✓ | ✓ | Posts, Reels, Stories |
| TikTok | ✓ | ✓ | ✓ | No watermark preferred |
| Twitter/X | ✓ | ✓ | ✓ | Video posts only |
| Facebook | ✓ | ✓ | ✓ | Public videos only |
| Generic URLs | ✓ | ✓ | ✗ | Direct video files |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DL-01 | Phase 9 | Pending |
| DL-02 | Phase 9 | Pending |
| DL-03 | Phase 9 | Pending |
| DL-04 | Phase 9 | Pending |
| DL-05 | Phase 9 | Pending |
| DL-06 | Phase 9 | Pending |
| DL-07 | Phase 9 | Pending |
| YT-01 | Phase 10 | Pending |
| YT-02 | Phase 10 | Pending |
| YT-03 | Phase 10 | Pending |
| YT-04 | Phase 10 | Pending |
| IG-01 | Phase 10 | Pending |
| IG-02 | Phase 10 | Pending |
| IG-03 | Phase 10 | Pending |
| TT-01 | Phase 10 | Pending |
| TT-02 | Phase 10 | Pending |
| TW-01 | Phase 10 | Pending |
| TW-02 | Phase 10 | Pending |
| FB-01 | Phase 10 | Pending |
| FB-02 | Phase 10 | Pending |
| GV-01 | Phase 10 | Pending |
| GV-02 | Phase 10 | Pending |
| GV-03 | Phase 10 | Pending |
| GV-04 | Phase 10 | Pending |
| QF-01 | Phase 9 | Pending |
| QF-02 | Phase 9 | Pending |
| QF-03 | Phase 9 | Pending |
| QF-04 | Phase 9 | Pending |
| QF-05 | Phase 9 | Pending |
| DM-01 | Phase 11 | Pending |
| DM-02 | Phase 11 | Pending |
| DM-03 | Phase 11 | Pending |
| DM-04 | Phase 11 | Pending |
| DM-05 | Phase 11 | Pending |
| PT-01 | Phase 11 | Pending |
| PT-02 | Phase 11 | Pending |
| PT-03 | Phase 11 | Pending |
| PT-04 | Phase 11 | Pending |
| PT-05 | Phase 11 | Pending |
| UI-01 | Phase 12 | Pending |
| UI-02 | Phase 12 | Pending |
| UI-03 | Phase 12 | Pending |
| UI-04 | Phase 12 | Pending |
| UI-05 | Phase 12 | Pending |
| UI-06 | Phase 12 | Pending |
| EH-01 | Phase 9 | Pending |
| EH-02 | Phase 9 | Pending |
| EH-03 | Phase 11 | Pending |
| EH-04 | Phase 11 | Pending |
| EH-05 | Phase 11 | Pending |
| INT-01 | Phase 12 | Pending |
| INT-02 | Phase 12 | Pending |
| INT-03 | Phase 12 | Pending |
| INT-04 | Phase 12 | Pending |

---

*Created: 2026-02-21 for v3.0 Downloader milestone*
