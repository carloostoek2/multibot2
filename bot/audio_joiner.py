"""Audio joining module for concatenating multiple audio files.

Provides functionality to merge multiple audio files into a single continuous audio file.
"""
import shutil
import subprocess
import logging
import os
from pathlib import Path
from typing import List, Tuple

from bot.error_handler import AudioJoinError

logger = logging.getLogger(__name__)


class AudioJoiner:
    """Join multiple audio files into a single continuous audio file.

    Uses ffmpeg concat demuxer for quality preservation when possible,
    or re-encodes to a common format when audio files have incompatible codecs.
    """

    def __init__(self, output_path: str):
        """Initialize audio joiner.

        Args:
            output_path: Path for the joined output audio file
        """
        self.output_path = Path(output_path)
        self._input_audios: List[str] = []

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

    def add_audio(self, audio_path: str) -> None:
        """Add an audio file to the join list.

        Args:
            audio_path: Path to the audio file to add

        Raises:
            AudioJoinError: If the audio file doesn't exist
        """
        path = Path(audio_path)
        if not path.exists():
            logger.error(f"Input file not found: {audio_path}")
            raise AudioJoinError(f"Archivo no encontrado: {audio_path}")

        self._input_audios.append(str(path.absolute()))
        logger.debug(f"Added audio to join list: {audio_path}")

    def _get_audio_info(self, audio_path: str) -> Tuple[str, str]:
        """Get audio codec and container format using ffprobe.

        Args:
            audio_path: Path to the audio file

        Returns:
            Tuple of (audio_codec, container_format)

        Raises:
            AudioJoinError: If ffprobe fails
        """
        if not self._check_ffprobe():
            logger.error("ffprobe is not installed or not in PATH")
            raise AudioJoinError("ffprobe no está disponible")

        # Get audio codec
        codec_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            audio_path,
        ]

        # Get container format
        format_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=format_name",
            "-of", "csv=p=0",
            audio_path,
        ]

        try:
            codec_result = subprocess.run(
                codec_cmd, capture_output=True, text=True, check=False
            )
            audio_codec = codec_result.stdout.strip() or "unknown"

            format_result = subprocess.run(
                format_cmd, capture_output=True, text=True, check=True
            )
            container_format = format_result.stdout.strip() or "unknown"

            return audio_codec, container_format

        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed: {e.stderr}")
            raise AudioJoinError("No pude analizar el formato del audio") from e

    def _need_normalization(self) -> bool:
        """Check if audio files need format normalization before concatenation.

        Returns:
            True if audio files have incompatible formats and need re-encoding
        """
        if len(self._input_audios) < 2:
            return False

        # Get info for first audio as reference
        ref_audio_codec, ref_container = self._get_audio_info(self._input_audios[0])

        logger.debug(
            f"Reference audio - codec: {ref_audio_codec}, container: {ref_container}"
        )

        for audio_path in self._input_audios[1:]:
            audio_codec, container = self._get_audio_info(audio_path)
            logger.debug(
                f"Checking {audio_path} - codec: {audio_codec}, container: {container}"
            )

            # Check if codecs match
            if audio_codec != ref_audio_codec:
                logger.info(
                    f"Audio codec mismatch: {ref_audio_codec} vs {audio_codec}"
                )
                return True

        return False

    def _normalize_audios(self, temp_dir: str) -> List[str]:
        """Convert audio files to a common compatible format for concatenation.

        Re-encodes all audio files to MP3 format with libmp3lame encoder,
        which is widely compatible.

        Args:
            temp_dir: Directory for temporary normalized files

        Returns:
            List of paths to normalized audio files

        Raises:
            AudioJoinError: If normalization fails
        """
        normalized_paths = []
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)

        logger.info("Normalizing audio files to common format (MP3)")

        for i, audio_path in enumerate(self._input_audios):
            output_path = temp_path / f"normalized_{i:03d}.mp3"

            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output if exists
                "-i", audio_path,  # Input file
                "-c:a", "libmp3lame",  # MP3 audio codec
                "-b:a", "192k",  # Audio bitrate
                "-id3v2_version", "3",  # Metadata compatibility
                str(output_path),
            ]

            try:
                logger.debug(f"Normalizing audio {i+1}/{len(self._input_audios)}: {audio_path}")
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
                raise AudioJoinError(f"Error normalizando audio {i+1}") from e

        logger.info(f"All {len(normalized_paths)} audio files normalized successfully")
        return normalized_paths

    def _create_concat_file(self, audio_paths: List[str], concat_file_path: str) -> str:
        """Create ffmpeg concat demuxer file list.

        The concat demuxer format is:
            file '/path/to/audio1.mp3'
            file '/path/to/audio2.mp3'

        Args:
            audio_paths: List of audio file paths to concatenate
            concat_file_path: Path for the concat list file

        Returns:
            Path to the created concat file
        """
        with open(concat_file_path, "w", encoding="utf-8") as f:
            for audio_path in audio_paths:
                # Escape single quotes in path by replacing ' with '\''
                escaped_path = audio_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        logger.debug(f"Created concat file: {concat_file_path}")
        return concat_file_path

    def join_audios(self) -> bool:
        """Concatenate all added audio files into a single output file.

        Uses ffmpeg concat demuxer for lossless concatenation when audio files
        have compatible formats, or re-encodes to a common format when needed.

        Returns:
            True if join succeeded, False otherwise

        Raises:
            AudioJoinError: If joining fails
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise AudioJoinError("ffmpeg no está disponible")

        if len(self._input_audios) < 2:
            logger.error("At least 2 audio files are required for joining")
            raise AudioJoinError("Se necesitan al menos 2 archivos de audio para unir")

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if normalization is needed
        needs_normalization = self._need_normalization()

        # Create temporary directory for intermediate files
        temp_dir = self.output_path.parent / "join_audio_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            if needs_normalization:
                logger.info("Audio files have incompatible formats, normalizing first")
                audios_to_join = self._normalize_audios(str(temp_dir))
            else:
                logger.info("Audio files have compatible formats, using direct concat")
                audios_to_join = self._input_audios.copy()

            # Create concat file list
            concat_file = temp_dir / "concat_list.txt"
            self._create_concat_file(audios_to_join, str(concat_file))

            # Build ffmpeg concat command
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output if exists
                "-f", "concat",  # Use concat demuxer
                "-safe", "0",  # Allow unsafe file paths
                "-i", str(concat_file),  # Input concat file
            ]

            if needs_normalization:
                # Already normalized to MP3, just copy
                cmd.extend(["-c", "copy"])
            else:
                # Direct concat with copy (lossless)
                cmd.extend(["-c", "copy"])

            cmd.extend([
                "-id3v2_version", "3",  # Metadata compatibility
                str(self.output_path),
            ])

            logger.info(f"Joining {len(audios_to_join)} audio files")
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"Audio files joined successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise AudioJoinError("Error uniendo los archivos de audio") from e
        except Exception as e:
            logger.error(f"Unexpected error during audio joining: {e}")
            raise AudioJoinError("Error inesperado al unir los archivos de audio") from e

    def get_input_count(self) -> int:
        """Get the number of audio files currently in the join list.

        Returns:
            Number of audio files added
        """
        return len(self._input_audios)

    def clear_audios(self) -> None:
        """Clear all audio files from the join list."""
        self._input_audios.clear()
        logger.debug("Cleared all audio files from join list")
