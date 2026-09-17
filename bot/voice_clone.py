"""Zero-shot voice cloning via Replicate (Whisper STT + OpenVoice TTS).

Pipeline:
1. Transcribe the source voice note with openai/whisper.
2. Synthesize the transcript in the reference speaker's voice with
   chenxwh/openvoice (OpenVoice v2, native Spanish support).

Reference audio is stored on disk under data/voice_refs/{user_id}/
(or $VOICE_REFS_DIR/{user_id}/ when that env is set — use a Railway Volume).
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from urllib.request import urlretrieve

logger = logging.getLogger(__name__)

# Replicate models
WHISPER_MODEL = "openai/whisper"
OPENVOICE_MODEL = "chenxwh/openvoice"

# Default relative path (local / CWD). Override with VOICE_REFS_DIR for persistent volumes.
_DEFAULT_VOICE_REFS_DIR = Path("data") / "voice_refs"
REF_FILENAME = "reference.mp3"

# Default timeouts for Replicate calls (seconds)
DEFAULT_CLONE_TIMEOUT = 180


class VoiceCloneError(Exception):
    """Raised when voice cloning fails in a user-facing way."""


def get_voice_refs_root() -> Path:
    """Return the root directory for per-user voice reference clips.

    Honours VOICE_REFS_DIR when set (e.g. /data/voice_refs on a Railway Volume);
    otherwise uses data/voice_refs relative to the process CWD.
    """
    raw = (os.getenv("VOICE_REFS_DIR") or "").strip()
    return Path(raw) if raw else _DEFAULT_VOICE_REFS_DIR


# Back-compat alias (resolved at import; prefer get_voice_refs_root() for runtime).
VOICE_REFS_ROOT = get_voice_refs_root()


def get_user_ref_dir(user_id: int) -> Path:
    """Return the directory that holds this user's voice reference."""
    return get_voice_refs_root() / str(user_id)


def get_user_ref_path(user_id: int) -> Path:
    """Return the expected path of the saved reference MP3."""
    return get_user_ref_dir(user_id) / REF_FILENAME


def has_reference(user_id: int) -> bool:
    """Return True if a non-empty reference file exists for the user."""
    path = get_user_ref_path(user_id)
    return path.is_file() and path.stat().st_size > 0


def save_reference(user_id: int, source_path: str | Path) -> Path:
    """Save *source_path* as this user's reference audio (converted to MP3).

    Args:
        user_id: Telegram user id.
        source_path: Local path to voice/audio file (oga/ogg/mp3/wav/...).

    Returns:
        Path to the saved reference MP3.

    Raises:
        VoiceCloneError: If conversion or save fails.
    """
    source_path = Path(source_path)
    if not source_path.is_file():
        raise VoiceCloneError("No encontré el archivo de audio de referencia.")

    dest_dir = get_user_ref_dir(user_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / REF_FILENAME

    try:
        _convert_to_mp3(source_path, dest_path)
    except Exception as exc:
        logger.exception("Failed to save voice reference for user %s: %s", user_id, exc)
        raise VoiceCloneError("No pude guardar la voz de referencia.") from exc

    if not dest_path.is_file() or dest_path.stat().st_size == 0:
        raise VoiceCloneError("No pude guardar la voz de referencia.")

    logger.info("Saved voice reference for user %s at %s", user_id, dest_path)
    return dest_path


def clear_reference(user_id: int) -> bool:
    """Delete the user's reference if present. Returns True if deleted."""
    path = get_user_ref_path(user_id)
    if path.is_file():
        path.unlink()
        return True
    return False


def _convert_to_mp3(src: Path, dest: Path) -> None:
    """Convert any audio input to MP3 via ffmpeg (overwrites dest)."""
    # If already mp3, copy when possible to avoid quality loss; still re-encode
    # when extension differs or to normalize sample rate for TTS models.
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ar",
        "44100",
        "-ac",
        "1",
        "-b:a",
        "192k",
        str(dest),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        logger.error("ffmpeg failed converting %s: %s", src, result.stderr[-500:])
        raise VoiceCloneError("No pude convertir el audio de referencia a MP3.")


def _require_replicate_token(token: Optional[str]) -> str:
    if not token or not token.strip():
        raise VoiceCloneError(
            "La clonación de voz no está configurada (falta REPLICATE_API_TOKEN). "
            "Avisa al admin del bot."
        )
    return token.strip()


def _open_audio_for_replicate(path: Path):
    """Open a file handle suitable for the Replicate Python client."""
    return open(path, "rb")


def transcribe_audio(
    audio_path: str | Path,
    *,
    api_token: Optional[str] = None,
    language: str = "es",
) -> str:
    """Transcribe audio with openai/whisper on Replicate.

    Returns:
        Plain-text transcription (stripped).

    Raises:
        VoiceCloneError: On missing token, empty transcript, or API failure.
    """
    import replicate

    token = _require_replicate_token(api_token or os.getenv("REPLICATE_API_TOKEN"))
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise VoiceCloneError("No encontré el audio a transcribir.")

    logger.info("Transcribing audio via %s: %s", WHISPER_MODEL, audio_path.name)
    previous = os.environ.get("REPLICATE_API_TOKEN")
    os.environ["REPLICATE_API_TOKEN"] = token
    try:
        with _open_audio_for_replicate(audio_path) as audio_file:
            output = replicate.run(
                WHISPER_MODEL,
                input={
                    "audio": audio_file,
                    "language": language,
                    "translate": False,
                    "transcription": "plain text",
                    "temperature": 0,
                },
            )
    except VoiceCloneError:
        raise
    except Exception as exc:
        logger.exception("Whisper transcription failed: %s", exc)
        raise VoiceCloneError("No pude transcribir la nota de voz.") from exc
    finally:
        if previous is None:
            os.environ.pop("REPLICATE_API_TOKEN", None)
        else:
            os.environ["REPLICATE_API_TOKEN"] = previous

    text = ""
    if isinstance(output, dict):
        text = (output.get("transcription") or output.get("text") or "").strip()
    elif isinstance(output, str):
        text = output.strip()
    else:
        text = str(output or "").strip()

    if not text:
        raise VoiceCloneError(
            "No pude entender lo que dijiste en la nota de voz. Intenta de nuevo con más claridad."
        )
    return text


def synthesize_openvoice(
    text: str,
    reference_path: str | Path,
    *,
    api_token: Optional[str] = None,
    language: str = "ES",
    speed: float = 1.0,
) -> str:
    """Generate speech with chenxwh/openvoice using a reference speaker.

    Returns:
        URI (https URL) of the generated audio on Replicate delivery CDN.
    """
    import replicate

    token = _require_replicate_token(api_token or os.getenv("REPLICATE_API_TOKEN"))
    reference_path = Path(reference_path)
    if not reference_path.is_file():
        raise VoiceCloneError("No tienes una voz de referencia guardada.")

    logger.info("Synthesizing with %s (lang=%s, chars=%d)", OPENVOICE_MODEL, language, len(text))
    previous = os.environ.get("REPLICATE_API_TOKEN")
    os.environ["REPLICATE_API_TOKEN"] = token
    try:
        with _open_audio_for_replicate(reference_path) as ref_file:
            output = replicate.run(
                OPENVOICE_MODEL,
                input={
                    "audio": ref_file,
                    "text": text,
                    "language": language,
                    "speed": speed,
                },
            )
    except VoiceCloneError:
        raise
    except Exception as exc:
        logger.exception("OpenVoice synthesis failed: %s", exc)
        raise VoiceCloneError("No pude clonar la voz. Intenta de nuevo más tarde.") from exc
    finally:
        if previous is None:
            os.environ.pop("REPLICATE_API_TOKEN", None)
        else:
            os.environ["REPLICATE_API_TOKEN"] = previous

    if isinstance(output, str) and output.startswith("http"):
        return output
    # Some client versions return FileOutput-like objects
    url = getattr(output, "url", None) or str(output or "")
    if not url.startswith("http"):
        raise VoiceCloneError("La clonación no devolvió un audio válido.")
    return url


def download_url_to_file(url: str, dest_path: str | Path) -> Path:
    """Download a remote audio URL to dest_path."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urlretrieve(url, str(dest_path))
    except Exception as exc:
        logger.exception("Failed to download cloned audio from %s: %s", url, exc)
        raise VoiceCloneError("No pude descargar el audio clonado.") from exc
    if not dest_path.is_file() or dest_path.stat().st_size == 0:
        raise VoiceCloneError("No pude descargar el audio clonado.")
    return dest_path


def ensure_mp3(src: Path, dest: Path) -> Path:
    """Convert src to MP3 at dest if needed; return dest."""
    if src.suffix.lower() == ".mp3" and src.resolve() == dest.resolve():
        return dest
    _convert_to_mp3(src, dest)
    return dest


def clone_voice_pipeline(
    source_audio_path: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
    *,
    api_token: Optional[str] = None,
    whisper_language: str = "es",
    tts_language: str = "ES",
    correlation_id: Optional[str] = None,
) -> Path:
    """Full clone pipeline: STT → OpenVoice TTS → download → MP3 on disk.

    Args:
        source_audio_path: Voice note / content to speak.
        reference_path: Saved reference speaker audio.
        output_path: Destination MP3 path.
        api_token: Optional Replicate token (falls back to env).
        whisper_language: Language hint for Whisper.
        tts_language: OpenVoice language code (ES for Spanish).
        correlation_id: Optional id for log lines.

    Returns:
        Path to the output MP3.
    """
    cid = correlation_id or "no-cid"
    token = _require_replicate_token(api_token or os.getenv("REPLICATE_API_TOKEN"))

    # Replicate client reads REPLICATE_API_TOKEN from the environment
    previous = os.environ.get("REPLICATE_API_TOKEN")
    os.environ["REPLICATE_API_TOKEN"] = token
    try:
        logger.info("[%s] Voice clone: transcribing source", cid)
        text = transcribe_audio(
            source_audio_path,
            api_token=token,
            language=whisper_language,
        )
        logger.info("[%s] Voice clone: transcript length=%d", cid, len(text))

        logger.info("[%s] Voice clone: synthesizing with OpenVoice", cid)
        audio_url = synthesize_openvoice(
            text,
            reference_path,
            api_token=token,
            language=tts_language,
        )
        logger.info("[%s] Voice clone: downloading result", cid)

        output_path = Path(output_path)
        raw_path = output_path.with_suffix(".raw" + (Path(audio_url).suffix or ".wav"))
        download_url_to_file(audio_url, raw_path)

        # Normalize to MP3 for Telegram reply_audio
        if raw_path.suffix.lower() != ".mp3":
            ensure_mp3(raw_path, output_path)
            try:
                raw_path.unlink(missing_ok=True)
            except OSError:
                pass
        else:
            shutil.move(str(raw_path), str(output_path))

        return Path(output_path)
    finally:
        if previous is None:
            os.environ.pop("REPLICATE_API_TOKEN", None)
        else:
            os.environ["REPLICATE_API_TOKEN"] = previous


__all__ = [
    "VoiceCloneError",
    "WHISPER_MODEL",
    "OPENVOICE_MODEL",
    "VOICE_REFS_ROOT",
    "get_voice_refs_root",
    "get_user_ref_dir",
    "get_user_ref_path",
    "has_reference",
    "save_reference",
    "clear_reference",
    "transcribe_audio",
    "synthesize_openvoice",
    "clone_voice_pipeline",
]
