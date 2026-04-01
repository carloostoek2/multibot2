"""Screenshot extraction from videos using FFmpeg."""
import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from bot.temp_manager import TempManager

logger = logging.getLogger(__name__)


class ScreenshotProcessor:
    """Extracts screenshots (thumbnails) from videos using FFmpeg.

    Supports both automatic uniform distribution and manual timestamp selection.
    """

    def __init__(self, video_path: str, correlation_id: Optional[str] = None):
        """Initialize the screenshot processor.

        Args:
            video_path: Path to the input video file
            correlation_id: Optional correlation ID for logging
        """
        self.video_path = video_path
        self.correlation_id = correlation_id or "screenshot"
        self.temp_mgr = TempManager(correlation_id)
        self._duration: Optional[float] = None

    def _get_duration(self) -> float:
        """Get video duration in seconds using ffprobe.

        Returns:
            Video duration in seconds

        Raises:
            RuntimeError: If duration cannot be determined
        """
        if self._duration is not None:
            return self._duration

        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                self.video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])
            self._duration = duration
            logger.info(f"[{self.correlation_id}] Video duration: {duration:.2f}s")
            return duration
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"[{self.correlation_id}] Failed to get video duration: {e}")
            raise RuntimeError("No se pudo obtener la duración del video") from e

    async def extract_auto(self, count: int) -> List[str]:
        """Extract evenly distributed screenshots from the video.

        Args:
            count: Number of screenshots to extract

        Returns:
            List of paths to the generated screenshot files

        Raises:
            RuntimeError: If extraction fails
        """
        if count < 1:
            raise ValueError("Count must be at least 1")

        duration = self._get_duration()

        # Calculate evenly spaced timestamps (avoiding first and last second)
        # Leave some padding at start/end for better frames
        padding = min(1.0, duration * 0.01)  # 1% padding or 1 second, whichever is smaller
        effective_duration = duration - (2 * padding)

        if effective_duration <= 0:
            effective_duration = duration
            padding = 0

        timestamps = []
        for i in range(1, count + 1):
            timestamp = padding + (i * effective_duration / (count + 1))
            timestamps.append(timestamp)

        logger.info(f"[{self.correlation_id}] Extracting {count} screenshots at timestamps: {timestamps}")
        return await self._extract_at_timestamps(timestamps, duration)

    async def extract_at_times(self, timestamps: List[float]) -> List[str]:
        """Extract screenshots at specific timestamps.

        Args:
            timestamps: List of timestamps in seconds

        Returns:
            List of paths to the generated screenshot files

        Raises:
            RuntimeError: If extraction fails
            ValueError: If timestamps are invalid
        """
        if not timestamps:
            raise ValueError("At least one timestamp is required")

        duration = self._get_duration()

        # Validate timestamps
        for ts in timestamps:
            if ts < 0:
                raise ValueError(f"Tiempo negativo: {ts}")
            if ts > duration:
                raise ValueError(f"El tiempo {ts}s excede la duración del video ({duration:.2f}s)")

        logger.info(f"[{self.correlation_id}] Extracting {len(timestamps)} screenshots at: {timestamps}")
        return await self._extract_at_timestamps(timestamps, duration)

    async def _extract_at_timestamps(self, timestamps: List[float], duration: float) -> List[str]:
        """Internal method to extract screenshots at given timestamps.

        Args:
            timestamps: List of timestamps in seconds
            duration: Total video duration for validation

        Returns:
            List of paths to the generated screenshot files
        """
        screenshot_paths = []
        screenshot_dir = self.temp_mgr.get_subdir("screenshots")

        # Use asyncio to run extractions in parallel for better performance
        tasks = []
        for i, timestamp in enumerate(timestamps):
            output_path = os.path.join(screenshot_dir, f"screenshot_{i:03d}.jpg")
            tasks.append(self._extract_single(timestamp, output_path, duration))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[{self.correlation_id}] Failed to extract screenshot at {timestamps[i]}s: {result}")
                # Continue with other screenshots even if one fails
            else:
                screenshot_paths.append(result)

        if not screenshot_paths:
            raise RuntimeError("No se pudieron generar capturas de pantalla")

        logger.info(f"[{self.correlation_id}] Successfully extracted {len(screenshot_paths)} screenshots")
        return screenshot_paths

    async def _extract_single(self, timestamp: float, output_path: str, duration: float) -> str:
        """Extract a single screenshot at the given timestamp.

        Args:
            timestamp: Timestamp in seconds
            output_path: Path for the output image
            duration: Total video duration for seek optimization

        Returns:
            Path to the generated screenshot file

        Raises:
            RuntimeError: If extraction fails
        """
        # Use input seeking (-ss before -i) for faster seeking
        # For timestamps in the first half, use input seeking
        # For timestamps in the second half, use output seeking for accuracy
        if timestamp < duration / 2:
            # Input seeking (faster but less accurate for exact frame)
            cmd = [
                "ffmpeg",
                "-ss", f"{timestamp:.3f}",
                "-i", self.video_path,
                "-vframes", "1",
                "-q:v", "2",  # High quality (1-31, lower is better)
                "-y",  # Overwrite
                output_path
            ]
        else:
            # Output seeking (slower but more accurate)
            cmd = [
                "ffmpeg",
                "-i", self.video_path,
                "-ss", f"{timestamp:.3f}",
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                output_path
            ]

        try:
            # Run in executor to not block the event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, check=True)
            )

            if not os.path.exists(output_path):
                raise RuntimeError(f"Screenshot file not created: {output_path}")

            file_size = os.path.getsize(output_path)
            logger.debug(f"[{self.correlation_id}] Extracted screenshot at {timestamp:.2f}s -> {output_path} ({file_size} bytes)")
            return output_path

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            logger.error(f"[{self.correlation_id}] FFmpeg error at {timestamp:.2f}s: {stderr}")
            raise RuntimeError(f"Error de FFmpeg: {stderr}") from e

    def cleanup(self):
        """Clean up temporary files."""
        self.temp_mgr.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
