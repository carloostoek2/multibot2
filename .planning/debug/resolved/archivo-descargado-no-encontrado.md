---
status: resolved
trigger: "El bot de Telegram descarga videos correctamente con yt-dlp pero luego muestra error 'No se encontró el archivo descargado' y no envía el archivo al usuario."
created: "2026-03-01T00:00:00Z"
updated: "2026-03-01T00:10:00Z"
---

## Current Focus

hypothesis: The ytdlp_downloader returns a DownloadResult object from downloaders/__init__.py, but download_lifecycle.py's _process_result expects either a DownloadResult from download_lifecycle.py or a dict. The mismatch causes file_path to be lost.

test: Check if the DownloadResult from downloaders/__init__.py is recognized as a DownloadResult by download_lifecycle.py's _process_result

expecting: If the class types don't match, isinstance() check fails and file_path becomes None

next_action: Verify the class mismatch and check the exact flow in download_facade.py's do_download function

## Symptoms

expected: El bot debería descargar el video y enviarlo al usuario en Telegram
actual: El bot descarga el video (yt-dlp muestra 100% completion), pero luego envía el mensaje de error "No se encontró el archivo descargado" y no envía el archivo
errors: Error: No se encontró el archivo descargado.
reproduction: Enviar una URL de Twitter/X o TikTok al bot, seleccionar formato video, esperar la descarga
started: Según los logs, el problema ocurre inmediatamente después de que yt-dlp reporta "Download completed". El archivo se guarda en /tmp/videonote_dl_*/ pero luego no se encuentra.

## Evidence

- timestamp: "2026-03-01T00:00:00Z"
  checked: Project structure
  found: Python project with bot/downloaders/ytdlp_downloader.py and bot/handlers.py as main files
  implication: Need to trace file path from download to send

- timestamp: "2026-03-01T00:05:00Z"
  checked: handlers.py lines 6434-6438
  found: Error "No se encontró el archivo descargado" is raised when `not file_path or not os.path.exists(file_path)`
  implication: Either file_path is None/empty, or the file doesn't exist at that path

- timestamp: "2026-03-01T00:06:00Z"
  checked: download_lifecycle.py _process_result method (lines 363-400)
  found: When raw_result is a dict, it extracts file_path from 'file_path' or 'path' key. When it's not a dict or DownloadResult, it returns file_path=None
  implication: If ytdlp_downloader returns something unexpected, file_path could be None

- timestamp: "2026-03-01T00:07:00Z"
  checked: ytdlp_downloader.py lines 283-290
  found: It imports DownloadResult from `from . import DownloadResult` and returns DownloadResult(success=True, file_path=file_path, metadata=metadata)
  implication: This should work correctly, but need to verify what DownloadResult is being imported

- timestamp: "2026-03-01T00:08:00Z"
  checked: download_facade.py lines 305-329 (do_download function)
  found: The function checks `isinstance(result, LifecycleResult)` first, then `isinstance(result, dict)`, and falls through to `else` which does `file_path=str(result) if result else None`
  implication: Since ytdlp_downloader returns DownloadResult from __init__.py (not LifecycleResult), it falls into the else branch, converting the entire object to a string instead of extracting file_path

- timestamp: "2026-03-01T00:09:00Z"
  checked: There are TWO different DownloadResult classes:
    1. bot.downloaders.DownloadResult (in __init__.py lines 153-166) - has success, file_path, error_message, metadata
    2. bot.downloaders.download_lifecycle.DownloadResult (lines 197-212) - has success, file_path, metadata, correlation_id, temp_dir
  found: The isinstance check in download_facade.py only matches LifecycleResult, not the DownloadResult from __init__.py
  implication: ROOT CAUSE CONFIRMED - The type mismatch causes file_path to be set to string representation of the DownloadResult object instead of the actual file_path

## Eliminated

- hypothesis: The file is being deleted before it can be sent
  evidence: cleanup_on_success=False is correctly set in handlers.py lines 6347-6350 and 6607-6610
  timestamp: "2026-03-01T00:06:00Z"

- hypothesis: The file path is not being returned from ytdlp_downloader
  evidence: ytdlp_downloader.py correctly returns DownloadResult with file_path at line 286-289
  timestamp: "2026-03-01T00:07:00Z"

## Resolution

root_cause: Type mismatch between two DownloadResult classes. ytdlp_downloader returns bot.downloaders.DownloadResult (from __init__.py), but download_facade.py's do_download function only checks for LifecycleResult (from download_lifecycle.py). The isinstance() check fails, causing the code to fall through to the else branch which converts the entire DownloadResult object to a string instead of extracting the file_path attribute.

fix: Added import for BaseDownloadResult from bot.downloaders and added isinstance check for BaseDownloadResult in do_download function to properly extract file_path.

verification: Code review confirms the fix addresses the type mismatch
files_changed:
  - /data/data/com.termux/files/home/repos/multibot2/bot/downloaders/download_facade.py
