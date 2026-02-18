"""Audio processing module for voice notes and audio conversion using ffmpeg.

Provides VoiceNoteConverter for converting audio files (MP3, etc.) to Telegram
voice note format (OGG Opus), and VoiceToMp3Converter for converting voice
notes back to MP3 format.
"""
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class VoiceNoteConverter:
    """Convert audio files to Telegram voice note format (OGG Opus).

    Voice note requirements:
    - OGG container format
    - Opus audio codec (optimized for voice)
    - Max duration 20 minutes (Telegram limit)
    - Efficient bitrate for voice (24k default)
    """

    # Maximum duration for voice notes in seconds (20 minutes)
    MAX_DURATION_SECONDS = 1200

    def __init__(self, input_path: str, output_path: str):
        """Initialize voice note converter.

        Args:
            input_path: Path to input audio file (MP3, WAV, etc.)
            output_path: Path for converted voice note output (OGG)
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

    @staticmethod
    def _check_ffmpeg() -> bool:
        """Check if ffmpeg is installed and available.

        Returns:
            True if ffmpeg is available, False otherwise
        """
        return shutil.which("ffmpeg") is not None

    def _get_audio_duration(self) -> Optional[float]:
        """Get duration of input audio file using ffprobe.

        Returns:
            Duration in seconds, or None if cannot be determined
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(self.input_path)
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    return float(result.stdout.strip())
                except ValueError:
                    return None
            return None

        except Exception as e:
            logger.warning(f"Could not determine audio duration: {e}")
            return None

    def process(self) -> bool:
        """Convert audio file to Telegram voice note format (OGG Opus).

        Applies:
        - Opus codec optimized for voice
        - 24k bitrate for efficient voice transmission
        - Truncation to 20 minutes if needed
        - OGG container format

        Returns:
            True if conversion succeeded, False otherwise
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            return False

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            return False

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check duration and determine if truncation is needed
        duration = self._get_audio_duration()
        if duration and duration > self.MAX_DURATION_SECONDS:
            logger.warning(
                f"Audio duration ({duration:.1f}s) exceeds maximum "
                f"({self.MAX_DURATION_SECONDS}s), will be truncated"
            )

        # Build ffmpeg command for voice note conversion
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-c:a", "libopus",  # Opus codec for voice
            "-b:a", "24k",  # Bitrate optimized for voice
            "-application", "voip",  # Optimize for voice communication
            "-vbr", "on",  # Variable bitrate for efficiency
        ]

        # Add duration limit if audio is too long
        if duration and duration > self.MAX_DURATION_SECONDS:
            cmd.extend(["-t", str(self.MAX_DURATION_SECONDS)])

        # Add output file
        cmd.append(str(self.output_path))

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Voice note converted successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during voice note conversion: {e}")
            return False


class VoiceToMp3Converter:
    """Convert voice notes (OGG Opus) to MP3 format.

    Converts Telegram voice notes back to MP3 format with good quality
    for playback on standard audio players.
    """

    def __init__(self, input_path: str, output_path: str):
        """Initialize voice to MP3 converter.

        Args:
            input_path: Path to input voice note (OGG Opus)
            output_path: Path for converted MP3 output
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

    @staticmethod
    def _check_ffmpeg() -> bool:
        """Check if ffmpeg is installed and available.

        Returns:
            True if ffmpeg is available, False otherwise
        """
        return shutil.which("ffmpeg") is not None

    def process(self) -> bool:
        """Convert voice note to MP3 format.

        Applies:
        - MP3 codec (libmp3lame) for wide compatibility
        - 192k bitrate for good voice quality
        - Preserves metadata if present

        Returns:
            True if conversion succeeded, False otherwise
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            return False

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            return False

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command for MP3 conversion
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-c:a", "libmp3lame",  # MP3 codec
            "-b:a", "192k",  # Good quality bitrate for voice
            "-q:a", "2",  # Quality setting (2 = high quality)
            "-map_metadata", "0",  # Preserve metadata
            "-id3v2_version", "3",  # ID3v2.3 for compatibility
            str(self.output_path),  # Output file
        ]

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Voice note converted to MP3 successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during MP3 conversion: {e}")
            return False


@staticmethod
def get_audio_duration(file_path: str) -> Tuple[Optional[float], Optional[str]]:
    """Get audio file duration using ffprobe.

    Args:
        file_path: Path to the audio file

    Returns:
        Tuple of (duration, error_message)
        - duration: Duration in seconds, or None if failed
        - error_message: None if success, error description if failed
    """
    path = Path(file_path)

    if not path.exists():
        return None, "El archivo no existe"

    if path.stat().st_size == 0:
        return None, "El archivo está vacío"

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return None, "No se pudo leer la duración del audio"

        duration_str = result.stdout.strip()
        if not duration_str:
            return None, "El archivo no tiene información de duración"

        try:
            duration = float(duration_str)
            if duration <= 0:
                return None, "Duración inválida"
            return duration, None
        except ValueError:
            return None, "Formato de duración inválido"

    except FileNotFoundError:
        return None, "ffprobe no está disponible"
    except subprocess.TimeoutExpired:
        return None, "Tiempo de espera agotado al leer el audio"
    except Exception as e:
        logger.warning(f"Error getting audio duration: {e}")
        return None, f"Error al obtener duración: {str(e)}"


@staticmethod
def is_opus_ogg(file_path: str) -> bool:
    """Check if file is a valid OGG Opus voice note.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file is OGG Opus format, False otherwise
    """
    path = Path(file_path)

    if not path.exists():
        return False

    # Check file extension first
    if path.suffix.lower() not in ['.ogg', '.oga']:
        return False

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            codec = result.stdout.strip().lower()
            return codec == "opus"

        return False

    except Exception:
        return False


__all__ = [
    "VoiceNoteConverter",
    "VoiceToMp3Converter",
    "get_audio_duration",
    "is_opus_ogg",
]
