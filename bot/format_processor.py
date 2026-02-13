"""Format conversion and audio extraction module using ffmpeg.

Provides FormatConverter for converting videos between different formats
and AudioExtractor for extracting audio tracks from videos.
"""
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FormatConverter:
    """Convert videos between different formats using ffmpeg.

    Supported output formats: mp4, avi, mov, mkv, webm
    """

    # Format to codec mapping
    VIDEO_CODECS = {
        "mp4": "libx264",
        "avi": "libx264",
        "mov": "libx264",
        "mkv": "libx264",
        "webm": "libvpx-vp9",
    }

    # Audio codecs by format
    AUDIO_CODECS = {
        "mp4": "aac",
        "avi": "aac",
        "mov": "aac",
        "mkv": "aac",
        "webm": "libopus",
    }

    def __init__(self, input_path: str, output_path: str):
        """Initialize format converter.

        Args:
            input_path: Path to input video file
            output_path: Path for converted output video
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
        """Return list of supported output formats.

        Returns:
            List of supported format extensions
        """
        return ["mp4", "avi", "mov", "mkv", "webm"]

    def convert(self, output_format: str) -> bool:
        """Convert video to specified format.

        Args:
            output_format: Target format (mp4, avi, mov, mkv, webm)

        Returns:
            True if conversion succeeded, False otherwise
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            return False

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            return False

        # Validate output format
        output_format = output_format.lower().lstrip(".")
        if output_format not in self.get_supported_formats():
            logger.error(f"Unsupported output format: {output_format}")
            return False

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine codecs
        video_codec = self.VIDEO_CODECS.get(output_format, "libx264")
        audio_codec = self.AUDIO_CODECS.get(output_format, "aac")

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-c:v", video_codec,  # Video codec
            "-c:a", audio_codec,  # Audio codec
            "-movflags", "+faststart",  # Web optimization
            str(self.output_path),  # Output file
        ]

        # Add format-specific options
        if output_format == "mp4":
            cmd.extend(["-pix_fmt", "yuv420p"])  # Pixel format for compatibility
        elif output_format == "webm":
            cmd.extend(["-b:v", "1M"])  # Video bitrate for VP9

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Video converted successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during format conversion: {e}")
            return False


class AudioExtractor:
    """Extract audio tracks from videos using ffmpeg.

    Supported output formats: mp3, aac, wav, ogg
    """

    # Audio codec and bitrate configuration
    AUDIO_CONFIG = {
        "mp3": {"codec": "libmp3lame", "bitrate": "192k"},
        "aac": {"codec": "aac", "bitrate": "128k"},
        "wav": {"codec": "pcm_s16le", "bitrate": None},
        "ogg": {"codec": "libvorbis", "bitrate": "128k"},
    }

    def __init__(self, input_path: str, output_path: str):
        """Initialize audio extractor.

        Args:
            input_path: Path to input video file
            output_path: Path for extracted audio output
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
            List of supported audio format extensions
        """
        return ["mp3", "aac", "wav", "ogg"]

    def extract(self, output_format: str = "mp3") -> bool:
        """Extract audio track from video.

        Args:
            output_format: Target audio format (mp3, aac, wav, ogg)

        Returns:
            True if extraction succeeded, False otherwise
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            return False

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            return False

        # Validate output format
        output_format = output_format.lower().lstrip(".")
        if output_format not in self.get_supported_formats():
            logger.error(f"Unsupported audio format: {output_format}")
            return False

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get codec configuration
        config = self.AUDIO_CONFIG.get(output_format, {})
        audio_codec = config.get("codec", "libmp3lame")
        bitrate = config.get("bitrate")

        # Build ffmpeg command for audio extraction
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-vn",  # No video (audio only)
            "-c:a", audio_codec,  # Audio codec
        ]

        # Add bitrate if specified (not for wav)
        if bitrate:
            cmd.extend(["-b:a", bitrate])

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
            logger.info(f"Audio extracted successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during audio extraction: {e}")
            return False
