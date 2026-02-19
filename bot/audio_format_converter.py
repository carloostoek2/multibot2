"""Audio format conversion module using ffmpeg.

Provides AudioFormatConverter for converting audio files between different
formats (MP3, WAV, OGG, AAC, FLAC) with automatic format detection and
metadata preservation.
"""
import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict

from bot.error_handler import AudioFormatConversionError

logger = logging.getLogger(__name__)


class AudioFormatConverter:
    """Convert audio files between different formats using ffmpeg.

    Supported formats: mp3, wav, ogg, aac, flac
    Each format uses appropriate codec and quality settings.
    """

    # Format configuration: codec, bitrate, and extra options
    SUPPORTED_FORMATS = {
        "mp3": {
            "codec": "libmp3lame",
            "bitrate": "192k",
            "extra_options": ["-q:a", "2", "-map_metadata", "0", "-id3v2_version", "3"],
        },
        "wav": {
            "codec": "pcm_s16le",
            "bitrate": None,
            "extra_options": ["-map_metadata", "0"],
        },
        "ogg": {
            "codec": "libvorbis",
            "bitrate": "192k",
            "extra_options": ["-map_metadata", "0"],
        },
        "aac": {
            "codec": "aac",
            "bitrate": "192k",
            "extra_options": ["-map_metadata", "0"],
        },
        "flac": {
            "codec": "flac",
            "bitrate": None,
            "extra_options": ["-map_metadata", "0", "-compression_level", "5"],
        },
    }

    def __init__(self, input_path: str, output_path: str):
        """Initialize audio format converter.

        Args:
            input_path: Path to input audio file
            output_path: Path for converted output audio
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

    @staticmethod
    def get_supported_formats() -> list[str]:
        """Return list of supported audio output formats.

        Returns:
            List of supported format extensions
        """
        return ["mp3", "wav", "ogg", "aac", "flac"]

    def convert(self, output_format: str) -> bool:
        """Convert audio to specified format.

        Args:
            output_format: Target format (mp3, wav, ogg, aac, flac)

        Returns:
            True if conversion succeeded, False otherwise

        Raises:
            AudioFormatConversionError: If conversion fails
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise AudioFormatConversionError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise AudioFormatConversionError("El archivo de entrada no existe")

        # Validate output format
        output_format = output_format.lower().lstrip(".")
        if output_format not in self.get_supported_formats():
            logger.error(f"Unsupported output format: {output_format}")
            raise AudioFormatConversionError(f"Formato no soportado: {output_format}")

        # Log metadata preservation status
        self._log_metadata_preservation(output_format)

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get format configuration
        config = self.SUPPORTED_FORMATS.get(output_format, {})
        audio_codec = config.get("codec", "libmp3lame")
        bitrate = config.get("bitrate")
        extra_options = config.get("extra_options", [])

        # Build ffmpeg command for audio conversion
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-c:a", audio_codec,  # Audio codec
        ]

        # Add bitrate if specified (not for wav/flac)
        if bitrate:
            cmd.extend(["-b:a", bitrate])

        # Add extra format-specific options
        cmd.extend(extra_options)

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
            logger.info(f"Audio converted successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise AudioFormatConversionError(
                f"Error en la conversión: {e.stderr[:100]}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during audio conversion: {e}")
            raise AudioFormatConversionError(f"Error inesperado: {str(e)}") from e

    def _log_metadata_preservation(self, output_format: str) -> None:
        """Log metadata preservation status for the conversion.

        Args:
            output_format: Target format being converted to
        """
        if has_metadata_support(output_format):
            logger.info(f"Metadata will be preserved for {output_format} output")
        else:
            logger.warning(
                f"Metadata preservation limited for {output_format}: "
                "format has minimal metadata support"
            )

        # Log source metadata for debugging
        metadata = extract_metadata(str(self.input_path))
        if metadata:
            logger.debug(f"Source metadata fields: {list(metadata.keys())}")
            for key, value in metadata.items():
                logger.debug(f"  {key}: {value}")
        else:
            logger.debug("No metadata found in source file")


def extract_metadata(file_path: str) -> Optional[Dict[str, str]]:
    """Extract audio metadata using ffprobe.

    Extracts common metadata fields (title, artist, album, year, genre, comment)
    from audio files for debugging and logging purposes.

    Args:
        file_path: Path to the audio file

    Returns:
        Dictionary with metadata fields, or None if extraction fails
    """
    path = Path(file_path)

    if not path.exists():
        logger.warning(f"File not found for metadata extraction: {file_path}")
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format_tags",
                "-of", "json",
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.debug(f"ffprobe failed to extract metadata: {result.stderr}")
            return None

        data = json.loads(result.stdout)
        tags = data.get("format", {}).get("tags", {})

        if not tags:
            return None

        # Map common metadata fields (handle case variations)
        metadata = {}
        field_mapping = {
            "title": ["title", "TITLE", "Title"],
            "artist": ["artist", "ARTIST", "Artist", "author", "AUTHOR"],
            "album": ["album", "ALBUM", "Album"],
            "year": ["year", "YEAR", "Year", "date", "DATE"],
            "genre": ["genre", "GENRE", "Genre"],
            "comment": ["comment", "COMMENT", "Comment", "description"],
        }

        for standard_key, variants in field_mapping.items():
            for variant in variants:
                if variant in tags:
                    metadata[standard_key] = tags[variant]
                    break

        return metadata if metadata else None

    except FileNotFoundError:
        logger.debug("ffprobe is not available for metadata extraction")
        return None
    except json.JSONDecodeError:
        logger.debug("Failed to parse ffprobe metadata output")
        return None
    except subprocess.TimeoutExpired:
        logger.debug("Timeout while extracting metadata")
        return None
    except Exception as e:
        logger.debug(f"Error extracting metadata: {e}")
        return None


def has_metadata_support(format_name: str) -> bool:
    """Check if audio format supports metadata.

    Args:
        format_name: Audio format extension (mp3, wav, ogg, aac, flac)

    Returns:
        True if format supports metadata, False otherwise
    """
    # Formats with good metadata support
    supported_formats = {"mp3", "flac", "ogg", "aac"}
    # WAV has limited metadata support (mostly INFO chunks)
    limited_support = {"wav"}

    fmt = format_name.lower().lstrip(".")
    return fmt in supported_formats


def detect_audio_format(file_path: str) -> Optional[str]:
    """Detect audio file format using ffprobe.

    Args:
        file_path: Path to the audio file

    Returns:
        Detected format extension (mp3, wav, ogg, aac, flac) or None if cannot detect
    """
    path = Path(file_path)

    if not path.exists():
        logger.warning(f"File not found for format detection: {file_path}")
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=format_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.warning(f"ffprobe failed to detect format: {result.stderr}")
            return None

        format_name = result.stdout.strip().lower()
        if not format_name:
            return None

        # Map ffprobe format names to our supported formats
        format_mapping = {
            "mp3": "mp3",
            "wav": "wav",
            "ogg": "ogg",
            "opus": "ogg",
            "flac": "flac",
            "aac": "aac",
        }

        # ffprobe may return comma-separated format names like "mp3,mp2,mpa"
        for fmt in format_name.split(","):
            fmt = fmt.strip()
            if fmt in format_mapping:
                detected = format_mapping[fmt]
                logger.debug(f"Detected format: {detected} (from: {format_name})")
                return detected

        logger.warning(f"Unknown audio format: {format_name}")
        return None

    except FileNotFoundError:
        logger.error("ffprobe is not available")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("Timeout while detecting audio format")
        return None
    except Exception as e:
        logger.warning(f"Error detecting audio format: {e}")
        return None


def get_supported_audio_formats() -> list[str]:
    """Return list of supported audio formats for conversion.

    Returns:
        List of supported format extensions
    """
    return ["mp3", "wav", "ogg", "aac", "flac"]


__all__ = [
    "AudioFormatConverter",
    "detect_audio_format",
    "extract_metadata",
    "get_supported_audio_formats",
    "has_metadata_support",
]