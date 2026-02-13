"""Video joining module for concatenating multiple videos.

Provides functionality to merge multiple video files into a single continuous video.
"""
import shutil
import subprocess
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

from bot.error_handler import VideoJoinError

logger = logging.getLogger(__name__)


class VideoJoiner:
    """Join multiple videos into a single continuous video.

    Uses ffmpeg concat demuxer for quality preservation when possible,
    or re-encodes to a common format when videos have incompatible codecs.
    """

    def __init__(self, output_path: str):
        """Initialize video joiner.

        Args:
            output_path: Path for the joined output video
        """
        self.output_path = Path(output_path)
        self._input_videos: List[str] = []

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

    def add_video(self, video_path: str) -> None:
        """Add a video to the join list.

        Args:
            video_path: Path to the video file to add

        Raises:
            VideoJoinError: If the video file doesn't exist
        """
        path = Path(video_path)
        if not path.exists():
            logger.error(f"Input file not found: {video_path}")
            raise VideoJoinError(f"Archivo no encontrado: {video_path}")

        self._input_videos.append(str(path.absolute()))
        logger.debug(f"Added video to join list: {video_path}")

    def _get_video_info(self, video_path: str) -> Tuple[str, str, str]:
        """Get video codec, audio codec, and container format using ffprobe.

        Args:
            video_path: Path to the video file

        Returns:
            Tuple of (video_codec, audio_codec, container_format)

        Raises:
            VideoJoinError: If ffprobe fails
        """
        if not self._check_ffprobe():
            logger.error("ffprobe is not installed or not in PATH")
            raise VideoJoinError("ffprobe no está disponible")

        # Get video codec
        video_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            video_path,
        ]

        # Get audio codec
        audio_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            video_path,
        ]

        # Get container format
        format_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=format_name",
            "-of", "csv=p=0",
            video_path,
        ]

        try:
            video_result = subprocess.run(
                video_cmd, capture_output=True, text=True, check=True
            )
            video_codec = video_result.stdout.strip() or "unknown"

            audio_result = subprocess.run(
                audio_cmd, capture_output=True, text=True, check=False
            )
            audio_codec = audio_result.stdout.strip() or "none"

            format_result = subprocess.run(
                format_cmd, capture_output=True, text=True, check=True
            )
            container_format = format_result.stdout.strip() or "unknown"

            return video_codec, audio_codec, container_format

        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed: {e.stderr}")
            raise VideoJoinError("No pude analizar el formato del video") from e

    def _need_normalization(self) -> bool:
        """Check if videos need format normalization before concatenation.

        Returns:
            True if videos have incompatible formats and need re-encoding
        """
        if len(self._input_videos) < 2:
            return False

        # Get info for first video as reference
        ref_video_codec, ref_audio_codec, ref_container = self._get_video_info(
            self._input_videos[0]
        )

        logger.debug(
            f"Reference video - codec: {ref_video_codec}, "
            f"audio: {ref_audio_codec}, container: {ref_container}"
        )

        for video_path in self._input_videos[1:]:
            video_codec, audio_codec, container = self._get_video_info(video_path)
            logger.debug(
                f"Checking {video_path} - codec: {video_codec}, "
                f"audio: {audio_codec}, container: {container}"
            )

            # Check if codecs match
            if video_codec != ref_video_codec:
                logger.info(
                    f"Video codec mismatch: {ref_video_codec} vs {video_codec}"
                )
                return True

            if audio_codec != ref_audio_codec:
                logger.info(
                    f"Audio codec mismatch: {ref_audio_codec} vs {audio_codec}"
                )
                return True

        return False

    def _normalize_videos(self, temp_dir: str) -> List[str]:
        """Convert videos to a common compatible format for concatenation.

        Re-encodes all videos to H.264 video codec and AAC audio codec in MP4
        container, which is widely compatible.

        Args:
            temp_dir: Directory for temporary normalized files

        Returns:
            List of paths to normalized video files

        Raises:
            VideoJoinError: If normalization fails
        """
        normalized_paths = []
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)

        logger.info("Normalizing videos to common format (H.264 + AAC)")

        for i, video_path in enumerate(self._input_videos):
            output_path = temp_path / f"normalized_{i:03d}.mp4"

            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output if exists
                "-i", video_path,  # Input file
                "-c:v", "libx264",  # H.264 video codec
                "-preset", "medium",  # Encoding speed/quality balance
                "-crf", "23",  # Quality level (lower is better)
                "-c:a", "aac",  # AAC audio codec
                "-b:a", "128k",  # Audio bitrate
                "-movflags", "+faststart",  # Web optimization
                "-pix_fmt", "yuv420p",  # Pixel format for compatibility
                str(output_path),
            ]

            try:
                logger.debug(f"Normalizing video {i+1}/{len(self._input_videos)}: {video_path}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                normalized_paths.append(str(output_path))
                logger.debug(f"Normalized: {output_path}")

            except subprocess.CalledProcessError as e:
                logger.error(f"ffmpeg failed with code {e.returncode}")
                logger.error(f"ffmpeg stderr: {e.stderr}")
                raise VideoJoinError(f"Error normalizando video {i+1}") from e

        logger.info(f"All {len(normalized_paths)} videos normalized successfully")
        return normalized_paths

    def _create_concat_file(self, video_paths: List[str], concat_file_path: str) -> str:
        """Create ffmpeg concat demuxer file list.

        The concat demuxer format is:
            file '/path/to/video1.mp4'
            file '/path/to/video2.mp4'

        Args:
            video_paths: List of video file paths to concatenate
            concat_file_path: Path for the concat list file

        Returns:
            Path to the created concat file
        """
        with open(concat_file_path, "w", encoding="utf-8") as f:
            for video_path in video_paths:
                # Escape single quotes in path by replacing ' with '\''
                escaped_path = video_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        logger.debug(f"Created concat file: {concat_file_path}")
        return concat_file_path

    def join_videos(self) -> bool:
        """Concatenate all added videos into a single output file.

        Uses ffmpeg concat demuxer for lossless concatenation when videos
        have compatible formats, or re-encodes to a common format when needed.

        Returns:
            True if join succeeded, False otherwise

        Raises:
            VideoJoinError: If joining fails
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise VideoJoinError("ffmpeg no está disponible")

        if len(self._input_videos) < 2:
            logger.error("At least 2 videos are required for joining")
            raise VideoJoinError("Se necesitan al menos 2 videos para unir")

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if normalization is needed
        needs_normalization = self._need_normalization()

        # Create temporary directory for intermediate files
        temp_dir = self.output_path.parent / "join_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            if needs_normalization:
                logger.info("Videos have incompatible formats, normalizing first")
                videos_to_join = self._normalize_videos(str(temp_dir))
            else:
                logger.info("Videos have compatible formats, using direct concat")
                videos_to_join = self._input_videos.copy()

            # Create concat file list
            concat_file = temp_dir / "concat_list.txt"
            self._create_concat_file(videos_to_join, str(concat_file))

            # Build ffmpeg concat command
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output if exists
                "-f", "concat",  # Use concat demuxer
                "-safe", "0",  # Allow unsafe file paths
                "-i", str(concat_file),  # Input concat file
            ]

            if needs_normalization:
                # Already normalized, just copy
                cmd.extend(["-c", "copy"])
            else:
                # Direct concat with copy (lossless)
                cmd.extend(["-c", "copy"])

            cmd.extend([
                "-movflags", "+faststart",  # Web optimization
                str(self.output_path),
            ])

            logger.info(f"Joining {len(videos_to_join)} videos")
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"Videos joined successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise VideoJoinError("Error uniendo los videos") from e
        except Exception as e:
            logger.error(f"Unexpected error during video joining: {e}")
            raise VideoJoinError("Error inesperado al unir los videos") from e

    def get_input_count(self) -> int:
        """Get the number of videos currently in the join list.

        Returns:
            Number of videos added
        """
        return len(self._input_videos)

    def clear_videos(self) -> None:
        """Clear all videos from the join list."""
        self._input_videos.clear()
        logger.debug("Cleared all videos from join list")
