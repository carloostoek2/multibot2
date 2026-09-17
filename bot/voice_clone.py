"""True voice-to-voice cloning via Replicate FreeVC (timbre swap, keep prosody).

Pipeline:
1. Convert Telegram source (OGG/Opus) and reference to a FreeVC-friendly format (WAV).
2. Run jagilley/free-vc with model_type FreeVC (24kHz) — changes timbre only.
3. Download the result and normalize to MP3 for Telegram reply_audio.

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

# Replicate model — must pin a version hash.
# Unpinned "owner/name" hits POST /v1/models/.../predictions and returns 404
# with replicate>=1.x for these community models.
FREEVC_MODEL = (
    "jagilley/free-vc:e4f2ff8a1d3779a2411e119dfad7d451d5f3314a8cd7003a88f88ce4c3b18d95"
)
# Exact OpenAPI enum value (not "FreeVC (24k)").
FREEVC_MODEL_TYPE = "FreeVC (24kHz)"

# Default relative path (local / CWD). Override with VOICE_REFS_DIR for persistent volumes.
_DEFAULT_VOICE_REFS_DIR = Path("data") / "voice_refs"
REF_FILENAME = "reference.mp3"

# Default timeout for the FreeVC Replicate call (seconds). FreeVC can take ~4 min.
DEFAULT_CLONE_TIMEOUT = 300


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


def _convert_to_wav(src: Path, dest: Path) -> None:
    """Convert any audio input to 16-bit PCM WAV (FreeVC-friendly)."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "24000",
        "-ac",
        "1",
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
        logger.error("ffmpeg failed converting %s to wav: %s", src, result.stderr[-500:])
        raise VoiceCloneError("No pude convertir el audio al formato requerido.")


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


def _extract_output_url(output) -> str:
    """Normalize Replicate output to an https URL string."""
    if isinstance(output, str) and output.startswith("http"):
        return output
    url = getattr(output, "url", None) or str(output or "")
    if not url.startswith("http"):
        raise VoiceCloneError("La clonación no devolvió un audio válido.")
    return url


def run_freevc(
    source_audio_path: str | Path,
    reference_path: str | Path,
    *,
    api_token: Optional[str] = None,
    model_type: str = FREEVC_MODEL_TYPE,
    correlation_id: Optional[str] = None,
) -> str:
    """Run FreeVC voice conversion on Replicate.

    Args:
        source_audio_path: Content / rhythm to keep (WAV/MP3 preferred).
        reference_path: Target speaker timbre.
        api_token: Optional Replicate token (falls back to env).
        model_type: FreeVC OpenAPI enum value.
        correlation_id: Optional id for log lines.

    Returns:
        URI (https URL) of the converted audio on Replicate delivery CDN.
    """
    import replicate

    cid = correlation_id or "no-cid"
    token = _require_replicate_token(api_token or os.getenv("REPLICATE_API_TOKEN"))
    source_audio_path = Path(source_audio_path)
    reference_path = Path(reference_path)

    if not source_audio_path.is_file():
        raise VoiceCloneError("No encontré el audio de origen.")
    if not reference_path.is_file():
        raise VoiceCloneError("No tienes una voz de referencia guardada.")

    logger.info(
        "[%s] FreeVC run model=%s type=%s src=%s ref=%s",
        cid,
        FREEVC_MODEL,
        model_type,
        source_audio_path.name,
        reference_path.name,
    )

    previous = os.environ.get("REPLICATE_API_TOKEN")
    os.environ["REPLICATE_API_TOKEN"] = token
    try:
        with _open_audio_for_replicate(source_audio_path) as src_file, _open_audio_for_replicate(
            reference_path
        ) as ref_file:
            output = replicate.run(
                FREEVC_MODEL,
                input={
                    "source_audio": src_file,
                    "reference_audio": ref_file,
                    "model_type": model_type,
                },
            )
    except VoiceCloneError:
        raise
    except Exception as exc:
        logger.exception("[%s] FreeVC conversion failed: %s", cid, exc)
        raise VoiceCloneError("No pude clonar la voz. Intenta de nuevo más tarde.") from exc
    finally:
        if previous is None:
            os.environ.pop("REPLICATE_API_TOKEN", None)
        else:
            os.environ["REPLICATE_API_TOKEN"] = previous

    return _extract_output_url(output)


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
    correlation_id: Optional[str] = None,
) -> Path:
    """Full FreeVC pipeline: convert → FreeVC 24kHz → download → MP3 on disk.

    Args:
        source_audio_path: Voice note / content whose rhythm/prosody to keep.
        reference_path: Saved reference speaker audio (timbre target).
        output_path: Destination MP3 path.
        api_token: Optional Replicate token (falls back to env).
        correlation_id: Optional id for log lines.

    Returns:
        Path to the output MP3.
    """
    cid = correlation_id or "no-cid"
    token = _require_replicate_token(api_token or os.getenv("REPLICATE_API_TOKEN"))
    source_audio_path = Path(source_audio_path)
    reference_path = Path(reference_path)
    output_path = Path(output_path)

    # Work next to the output so TempManager cleanup still covers intermediates.
    work_dir = output_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    src_wav = work_dir / f"{output_path.stem}_src.wav"
    ref_wav = work_dir / f"{output_path.stem}_ref.wav"

    previous = os.environ.get("REPLICATE_API_TOKEN")
    os.environ["REPLICATE_API_TOKEN"] = token
    try:
        logger.info("[%s] Voice clone: converting source to WAV", cid)
        _convert_to_wav(source_audio_path, src_wav)

        logger.info("[%s] Voice clone: converting reference to WAV", cid)
        _convert_to_wav(reference_path, ref_wav)

        logger.info("[%s] Voice clone: running FreeVC (%s)", cid, FREEVC_MODEL_TYPE)
        audio_url = run_freevc(
            src_wav,
            ref_wav,
            api_token=token,
            model_type=FREEVC_MODEL_TYPE,
            correlation_id=cid,
        )
        logger.info("[%s] Voice clone: downloading result", cid)

        raw_suffix = Path(audio_url.split("?", 1)[0]).suffix or ".wav"
        raw_path = output_path.with_suffix(".raw" + raw_suffix)
        download_url_to_file(audio_url, raw_path)

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
        for tmp in (src_wav, ref_wav):
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        if previous is None:
            os.environ.pop("REPLICATE_API_TOKEN", None)
        else:
            os.environ["REPLICATE_API_TOKEN"] = previous


__all__ = [
    "VoiceCloneError",
    "FREEVC_MODEL",
    "FREEVC_MODEL_TYPE",
    "VOICE_REFS_ROOT",
    "get_voice_refs_root",
    "get_user_ref_dir",
    "get_user_ref_path",
    "has_reference",
    "save_reference",
    "clear_reference",
    "run_freevc",
    "clone_voice_pipeline",
]
