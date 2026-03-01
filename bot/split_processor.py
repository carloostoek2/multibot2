"""Video splitting module for dividing videos into segments.

Provides functionality to split videos by duration or number of parts.
"""
import shutil
import subprocess
import logging
import os
from pathlib import Path
from typing import List

from bot.error_handler import VideoSplitError

logger = logging.getLogger(__name__)


class VideoSplitter:
    """Split videos into multiple segments.

    Supports splitting by:
    - Duration: Create segments of N seconds each
    - Number of parts: Divide video into N equal parts
    - Time range: Extract segment from start_time to end_time
    """

    def __init__(self, input_path: str, output_dir: str):
        """Initialize video splitter.

        Args:
            input_path: Path to input video file
            output_dir: Directory for output segments
        """
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self._basename = self.input_path.stem
        self._ext = self.input_path.suffix

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

    def get_video_duration(self) -> float:
        """Get total video duration using ffprobe.

        Returns:
            Duration in seconds

        Raises:
            VideoSplitError: If ffprobe is not available or fails
        """
        if not self._check_ffprobe():
            logger.error("ffprobe is not installed or not in PATH")
            raise VideoSplitError("ffprobe no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise VideoSplitError(f"Archivo no encontrado: {self.input_path}")

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
            logger.debug(f"Video duration: {duration} seconds")
            return duration

        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed with code {e.returncode}")
            logger.error(f"ffprobe stderr: {e.stderr}")
            raise VideoSplitError("No pude obtener la duración del video") from e
        except ValueError as e:
            logger.error(f"Could not parse duration from ffprobe output: {e}")
            raise VideoSplitError("Duración del video inválida") from e
        except Exception as e:
            logger.error(f"Unexpected error getting video duration: {e}")
            raise VideoSplitError("Error obteniendo duración del video") from e

    def split_by_duration(self, segment_duration: int) -> List[str]:
        """Split video into segments of specified duration.

        Args:
            segment_duration: Duration of each segment in seconds (must be >= 5)

        Returns:
            List of paths to output segment files

        Raises:
            VideoSplitError: If splitting fails
        """
        if segment_duration < 5:
            raise VideoSplitError("La duración mínima por segmento es 5 segundos")

        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise VideoSplitError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise VideoSplitError(f"Archivo no encontrado: {self.input_path}")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build output pattern
        output_pattern = self.output_dir / f"{self._basename}_part%03d{self._ext}"

        # Build ffmpeg command for segmenting by duration
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

            logger.info(f"Video split into {len(output_files)} segments by duration")
            return output_files

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise VideoSplitError("Error dividiendo el video por duración") from e
        except Exception as e:
            logger.error(f"Unexpected error during video splitting: {e}")
            raise VideoSplitError("Error inesperado al dividir el video") from e

    def split_by_parts(self, num_parts: int) -> List[str]:
        """Split video into specified number of equal parts.

        Args:
            num_parts: Number of parts to create (must be >= 1)

        Returns:
            List of paths to output segment files

        Raises:
            VideoSplitError: If splitting fails
        """
        if num_parts < 1:
            raise VideoSplitError("El número de partes debe ser al menos 1")

        if num_parts == 1:
            # No splitting needed, return original file
            return [str(self.input_path)]

        # Get total duration
        total_duration = self.get_video_duration()

        # Calculate segment duration
        segment_duration = total_duration / num_parts

        # Ensure minimum segment duration of 5 seconds
        if segment_duration < 5:
            max_parts = int(total_duration // 5)
            raise VideoSplitError(
                f"El video es muy corto para dividir en {num_parts} partes. "
                f"Máximo recomendado: {max_parts} partes."
            )

        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise VideoSplitError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise VideoSplitError(f"Archivo no encontrado: {self.input_path}")

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

            logger.info(f"Video split into {len(output_files)} equal parts")
            return output_files

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise VideoSplitError("Error dividiendo el video en partes") from e
        except Exception as e:
            logger.error(f"Unexpected error during video splitting: {e}")
            raise VideoSplitError("Error inesperado al dividir el video") from e

    def split_by_time_range(self, start_time: float, end_time: float) -> str:
        """Extract a segment from the video between start and end times.

        Args:
            start_time: Start time in seconds (e.g., 30.5 for 30 seconds and 500ms)
            end_time: End time in seconds (must be greater than start_time)

        Returns:
            Path to the extracted segment file

        Raises:
            VideoSplitError: If splitting fails or times are invalid
        """
        if start_time < 0:
            raise VideoSplitError("El tiempo de inicio no puede ser negativo")

        if end_time <= start_time:
            raise VideoSplitError("El tiempo final debe ser mayor al tiempo de inicio")

        duration = end_time - start_time
        if duration < 1:
            raise VideoSplitError("La duración mínima es 1 segundo")

        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise VideoSplitError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise VideoSplitError(f"Archivo no encontrado: {self.input_path}")

        # Get video duration to validate end_time
        video_duration = self.get_video_duration()
        if end_time > video_duration:
            logger.warning(f"End time ({end_time}s) exceeds video duration ({video_duration}s), adjusting")
            end_time = video_duration

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build output filename
        output_filename = f"{self._basename}_{int(start_time)}s_to_{int(end_time)}s{self._ext}"
        output_path = self.output_dir / output_filename

        # Build ffmpeg command for extracting time range
        # Using re-encoding instead of -c copy to avoid keyframe issues
        # that cause frozen frames or black screens when cutting at non-keyframes
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-ss", str(start_time),  # Start time
            "-t", str(duration),  # Duration (end - start)
            "-c:v", "libx264",  # Re-encode video for accurate cutting
            "-preset", "fast",  # Fast encoding preset
            "-crf", "23",  # Quality setting (lower = better)
            "-c:a", "aac",  # Re-encode audio
            "-b:a", "128k",  # Audio bitrate
            "-pix_fmt", "yuv420p",  # Pixel format for compatibility
            "-movflags", "+faststart",  # Web optimization
            str(output_path),
        ]

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"Video segment extracted: {output_path}")
            return str(output_path)

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise VideoSplitError("Error extrayendo segmento del video") from e
        except Exception as e:
            logger.error(f"Unexpected error during video segment extraction: {e}")
            raise VideoSplitError("Error inesperado al extraer segmento") from e
