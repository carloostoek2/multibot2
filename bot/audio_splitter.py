"""Audio splitting module for dividing audio files into segments.

Provides functionality to split audio files by duration or number of parts.
Supports common audio formats: MP3, OGG, WAV, AAC, FLAC.
"""
import shutil
import subprocess
import logging
import os
from pathlib import Path
from typing import List

from bot.error_handler import AudioSplitError

logger = logging.getLogger(__name__)


class AudioSplitter:
    """Split audio files into multiple segments.

    Supports splitting by:
    - Duration: Create segments of N seconds each
    - Number of parts: Divide audio into N equal parts

    Supports common formats: MP3, OGG, WAV, AAC, FLAC
    """

    # Supported audio formats
    SUPPORTED_FORMATS = {'.mp3', '.ogg', '.oga', '.wav', '.aac', '.flac', '.m4a', '.wma'}

    def __init__(self, input_path: str, output_dir: str):
        """Initialize audio splitter.

        Args:
            input_path: Path to input audio file
            output_dir: Directory for output segments

        Raises:
            AudioSplitError: If input file format is not supported
        """
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self._basename = self.input_path.stem
        self._ext = self.input_path.suffix.lower()

        # Validate input format
        if self._ext not in self.SUPPORTED_FORMATS:
            logger.error(f"Unsupported audio format: {self._ext}")
            raise AudioSplitError(f"Formato de audio no soportado: {self._ext}")

    @staticmethod
    def _check_ffmpeg() -> bool:
        """Check if ffmpeg is installed and available.

        Returns:
            True if ffmpeg is available, False otherwise
        """
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def _check_ffprobe() -> bool:
        """Check if ffprobe is installed and available.

        Returns:
            True if ffprobe is available, False otherwise
        """
        return shutil.which("ffprobe") is not None

    def get_audio_duration(self) -> float:
        """Get total audio duration using ffprobe.

        Returns:
            Duration in seconds

        Raises:
            AudioSplitError: If ffprobe is not available or fails
        """
        if not self._check_ffprobe():
            logger.error("ffprobe is not installed or not in PATH")
            raise AudioSplitError("ffprobe no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise AudioSplitError(f"Archivo no encontrado: {self.input_path}")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(self.input_path),
        ]

        try:
            logger.debug(f"Running ffprobe: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            duration = float(result.stdout.strip())
            logger.debug(f"Audio duration: {duration} seconds")
            return duration

        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed with code {e.returncode}")
            logger.error(f"ffprobe stderr: {e.stderr}")
            raise AudioSplitError("No pude obtener la duración del audio") from e
        except ValueError as e:
            logger.error(f"Could not parse duration from ffprobe output: {e}")
            raise AudioSplitError("Duración del audio inválida") from e
        except Exception as e:
            logger.error(f"Unexpected error getting audio duration: {e}")
            raise AudioSplitError("Error obteniendo duración del audio") from e

    def split_by_duration(self, segment_duration: int) -> List[str]:
        """Split audio into segments of specified duration.

        Args:
            segment_duration: Duration of each segment in seconds (must be >= 5)

        Returns:
            List of paths to output segment files

        Raises:
            AudioSplitError: If splitting fails or segment duration is invalid
        """
        if segment_duration < 5:
            raise AudioSplitError("La duración mínima por segmento es 5 segundos")

        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise AudioSplitError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise AudioSplitError(f"Archivo no encontrado: {self.input_path}")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build output pattern
        output_pattern = self.output_dir / f"{self._basename}_part%03d{self._ext}"

        # Build ffmpeg command for segmenting by duration
        # Use -c copy for lossless splitting when possible
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-c", "copy",  # Copy streams without re-encoding
            "-map", "0",  # Map all streams from input
            "-segment_time", str(segment_duration),  # Segment duration
            "-f", "segment",  # Use segment muxer
            "-reset_timestamps", "1",  # Reset timestamps at each segment
            str(output_pattern),  # Output pattern
        ]

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            # Collect output files
            output_files = sorted([
                str(f) for f in self.output_dir.glob(f"{self._basename}_part*{self._ext}")
            ])

            logger.info(f"Audio split into {len(output_files)} segments by duration")
            return output_files

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise AudioSplitError("Error dividiendo el audio por duración") from e
        except Exception as e:
            logger.error(f"Unexpected error during audio splitting: {e}")
            raise AudioSplitError("Error inesperado al dividir el audio") from e

    def split_by_parts(self, num_parts: int) -> List[str]:
        """Split audio into specified number of equal parts.

        Args:
            num_parts: Number of parts to create (must be >= 1, max 20)

        Returns:
            List of paths to output segment files

        Raises:
            AudioSplitError: If splitting fails or number of parts is invalid
        """
        if num_parts < 1:
            raise AudioSplitError("El número de partes debe ser al menos 1")

        if num_parts > 20:
            raise AudioSplitError("El número máximo de partes es 20")

        if num_parts == 1:
            # No splitting needed, return original file
            return [str(self.input_path)]

        # Get total duration
        total_duration = self.get_audio_duration()

        # Calculate segment duration
        segment_duration = total_duration / num_parts

        # Ensure minimum segment duration of 5 seconds
        if segment_duration < 5:
            max_parts = int(total_duration // 5)
            raise AudioSplitError(
                f"El audio es muy corto para dividir en {num_parts} partes. "
                f"Máximo recomendado: {max_parts} partes."
            )

        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise AudioSplitError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise AudioSplitError(f"Archivo no encontrado: {self.input_path}")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build output pattern
        output_pattern = self.output_dir / f"{self._basename}_part%03d{self._ext}"

        # Build ffmpeg command for segmenting by calculated duration
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-c", "copy",  # Copy streams without re-encoding
            "-map", "0",  # Map all streams from input
            "-segment_time", str(segment_duration),  # Calculated segment duration
            "-f", "segment",  # Use segment muxer
            "-reset_timestamps", "1",  # Reset timestamps at each segment
            str(output_pattern),  # Output pattern
        ]

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            # Collect output files
            output_files = sorted([
                str(f) for f in self.output_dir.glob(f"{self._basename}_part*{self._ext}")
            ])

            logger.info(f"Audio split into {len(output_files)} equal parts")
            return output_files

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise AudioSplitError("Error dividiendo el audio en partes") from e
        except Exception as e:
            logger.error(f"Unexpected error during audio splitting: {e}")
            raise AudioSplitError("Error inesperado al dividir el audio") from e
