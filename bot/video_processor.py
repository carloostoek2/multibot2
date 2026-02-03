"""Video processing module using ffmpeg."""
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Process videos to Telegram video note format using ffmpeg.

    Video note requirements:
    - Square format 1:1 (circular display)
    - Max resolution 640x640
    - Max duration 60 seconds
    - MP4 format compatible with Telegram
    """

    def __init__(self, input_path: str, output_path: str):
        """Initialize video processor.

        Args:
            input_path: Path to input video file
            output_path: Path for processed output video
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
        """Process video to Telegram video note format.

        Applies:
        - Center crop to 1:1 aspect ratio (square)
        - Scale to max 640x640 maintaining aspect ratio
        - Limit duration to 60 seconds
        - MP4 output with reasonable quality

        Returns:
            True if processing succeeded, False otherwise
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            return False

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            return False

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command for video note format
        # 1. Crop to square (1:1) centered: crop=ih:ih takes height as width, centered
        # 2. Scale to max 640x640 with aspect ratio preservation
        # 3. Limit to 60 seconds
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-t", "60",  # Limit duration to 60 seconds
            "-vf", "crop=ih:ih,scale=640:640:force_original_aspect_ratio=decrease",  # Square crop + scale
            "-c:v", "libx264",  # Video codec
            "-preset", "medium",  # Encoding speed/compression tradeoff
            "-crf", "23",  # Quality (lower = better, 23 is default)
            "-pix_fmt", "yuv420p",  # Pixel format for compatibility
            "-c:a", "aac",  # Audio codec
            "-b:a", "128k",  # Audio bitrate
            "-movflags", "+faststart",  # Web optimization
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
            logger.info(f"Video processed successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during video processing: {e}")
            return False

    @staticmethod
    def process_video(input_path: str, output_path: str) -> bool:
        """Static method to process video in one call.

        Args:
            input_path: Path to input video file
            output_path: Path for processed output video

        Returns:
            True if processing succeeded, False otherwise
        """
        processor = VideoProcessor(input_path, output_path)
        return processor.process()
