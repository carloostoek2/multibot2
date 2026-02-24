"""Video-audio merging module for adding audio tracks to videos.

Provides functionality to merge a video file with an audio file,
replacing or adding audio tracks to the video.
"""
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

from bot.error_handler import VideoMergeError

logger = logging.getLogger(__name__)


class VideoAudioMerger:
    """Merge video with audio files.

    Supports:
    - Replace existing audio track in video
    - Add audio track to silent video
    - Adjust audio volume
    - Trim audio to match video duration
    """

    def __init__(self, video_path: str, audio_path: str, output_path: str):
        """Initialize video-audio merger.

        Args:
            video_path: Path to input video file
            audio_path: Path to input audio file
            output_path: Path for the merged output file
        """
        self.video_path = Path(video_path)
        self.audio_path = Path(audio_path)
        self.output_path = Path(output_path)

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
        """Get video duration using ffprobe.

        Returns:
            Duration in seconds

        Raises:
            VideoMergeError: If ffprobe fails
        """
        if not self._check_ffprobe():
            logger.error("ffprobe is not installed or not in PATH")
            raise VideoMergeError("ffprobe no está disponible")

        if not self.video_path.exists():
            logger.error(f"Video file not found: {self.video_path}")
            raise VideoMergeError(f"Archivo de video no encontrado: {self.video_path}")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(self.video_path),
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
            raise VideoMergeError("No pude obtener la duración del video") from e
        except ValueError as e:
            logger.error(f"Could not parse duration from ffprobe output: {e}")
            raise VideoMergeError("Duración del video inválida") from e
        except Exception as e:
            logger.error(f"Unexpected error getting video duration: {e}")
            raise VideoMergeError("Error obteniendo duración del video") from e

    def get_audio_duration(self) -> float:
        """Get audio duration using ffprobe.

        Returns:
            Duration in seconds

        Raises:
            VideoMergeError: If ffprobe fails
        """
        if not self._check_ffprobe():
            logger.error("ffprobe is not installed or not in PATH")
            raise VideoMergeError("ffprobe no está disponible")

        if not self.audio_path.exists():
            logger.error(f"Audio file not found: {self.audio_path}")
            raise VideoMergeError(f"Archivo de audio no encontrado: {self.audio_path}")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(self.audio_path),
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
            raise VideoMergeError("No pude obtener la duración del audio") from e
        except ValueError as e:
            logger.error(f"Could not parse duration from ffprobe output: {e}")
            raise VideoMergeError("Duración del audio inválida") from e
        except Exception as e:
            logger.error(f"Unexpected error getting audio duration: {e}")
            raise VideoMergeError("Error obteniendo duración del audio") from e

    def merge(
        self,
        volume: float = 1.0,
        trim_audio: bool = True,
        replace_audio: bool = True
    ) -> bool:
        """Merge video with audio file.

        Args:
            volume: Volume multiplier (1.0 = 100%, 0.5 = 50%, 2.0 = 200%)
            trim_audio: If True, trim audio to match video duration
            replace_audio: If True, replace existing audio; if False, add as new stream

        Returns:
            True if merge succeeded, False otherwise

        Raises:
            VideoMergeError: If merge fails
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise VideoMergeError("ffmpeg no está disponible")

        if not self.video_path.exists():
            logger.error(f"Video file not found: {self.video_path}")
            raise VideoMergeError(f"Archivo de video no encontrado: {self.video_path}")

        if not self.audio_path.exists():
            logger.error(f"Audio file not found: {self.audio_path}")
            raise VideoMergeError(f"Archivo de audio no encontrado: {self.audio_path}")

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get durations to determine if trimming is needed
        video_duration = self.get_video_duration()
        audio_duration = self.get_audio_duration()

        logger.info(f"Video duration: {video_duration:.2f}s, Audio duration: {audio_duration:.2f}s")

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.video_path),  # Input video
            "-i", str(self.audio_path),  # Input audio
        ]

        # Build filter complex for volume adjustment and trimming
        filters = []

        # Apply volume adjustment
        if volume != 1.0:
            filters.append(f"volume={volume}")

        # Trim audio to match video duration if needed
        if trim_audio and audio_duration > video_duration:
            filters.append(f"atrim=0:{video_duration}")

        # Build filter string
        if filters:
            filter_str = ",".join(filters)
            cmd.extend([
                "-filter_complex", f"[1:a]{filter_str}[audio]",
                "-map", "0:v",  # Take video from first input
                "-map", "[audio]",  # Take processed audio
            ])
        else:
            cmd.extend([
                "-map", "0:v",  # Take video from first input
                "-map", "1:a",  # Take audio from second input
            ])

        # Add encoding options
        cmd.extend([
            "-c:v", "copy",  # Copy video stream (no re-encoding)
            "-c:a", "aac",  # AAC audio codec for compatibility
            "-b:a", "192k",  # Audio bitrate
            "-shortest",  # End when shortest stream ends
            "-movflags", "+faststart",  # Web optimization
            str(self.output_path),
        ])

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"Video and audio merged successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise VideoMergeError("Error uniendo video con audio") from e
        except Exception as e:
            logger.error(f"Unexpected error during video-audio merge: {e}")
            raise VideoMergeError("Error inesperado al unir video con audio") from e

    @staticmethod
    def merge_video_audio(
        video_path: str,
        audio_path: str,
        output_path: str,
        volume: float = 1.0,
        trim_audio: bool = True
    ) -> bool:
        """Static method to merge video and audio in one call.

        Args:
            video_path: Path to input video file
            audio_path: Path to input audio file
            output_path: Path for merged output file
            volume: Volume multiplier (default 1.0)
            trim_audio: If True, trim audio to match video duration

        Returns:
            True if merge succeeded, False otherwise
        """
        merger = VideoAudioMerger(video_path, audio_path, output_path)
        return merger.merge(volume=volume, trim_audio=trim_audio)
