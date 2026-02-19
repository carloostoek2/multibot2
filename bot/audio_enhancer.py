"""Audio enhancement module for improving audio quality using ffmpeg filters.

Provides AudioEnhancer for applying audio enhancements including bass boost,
treble boost, and 3-band equalization to audio files.
"""
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional

from bot.error_handler import AudioEnhancementError

logger = logging.getLogger(__name__)


class AudioEnhancer:
    """Enhance audio files with bass boost, treble boost, and equalization.

    Uses ffmpeg audio filters to apply various enhancements:
    - Bass boost: Low-frequency enhancement using bass filter
    - Treble boost: High-frequency enhancement using treble filter
    - 3-band equalizer: Independent control of bass/mid/treble frequencies
    """

    # Intensity ranges
    MIN_INTENSITY = 1.0
    MAX_INTENSITY = 10.0

    # Equalizer band ranges
    MIN_EQ_GAIN = -10.0
    MAX_EQ_GAIN = 10.0

    def __init__(self, input_path: str, output_path: str):
        """Initialize audio enhancer.

        Args:
            input_path: Path to input audio file
            output_path: Path for enhanced output audio
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

    def _validate_input(self) -> None:
        """Validate input file exists and ffmpeg is available.

        Raises:
            AudioEnhancementError: If validation fails
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise AudioEnhancementError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise AudioEnhancementError("El archivo de entrada no existe")

    def _clamp_intensity(self, intensity: float) -> float:
        """Clamp intensity to valid range.

        Args:
            intensity: Input intensity value

        Returns:
            Clamped intensity between MIN_INTENSITY and MAX_INTENSITY
        """
        return max(self.MIN_INTENSITY, min(self.MAX_INTENSITY, intensity))

    def _clamp_eq_gain(self, gain: float) -> float:
        """Clamp equalizer gain to valid range.

        Args:
            gain: Input gain value

        Returns:
            Clamped gain between MIN_EQ_GAIN and MAX_EQ_GAIN
        """
        return max(self.MIN_EQ_GAIN, min(self.MAX_EQ_GAIN, gain))

    def bass_boost(self, intensity: float = 5.0) -> bool:
        """Apply bass boost enhancement to audio.

        Uses ffmpeg bass filter to enhance low frequencies around 100-200Hz.
        Intensity maps to gain: 1-10 -> 2-20dB boost

        Args:
            intensity: Boost intensity from 1.0 to 10.0 (default 5.0)

        Returns:
            True if enhancement succeeded

        Raises:
            AudioEnhancementError: If enhancement fails
        """
        self._validate_input()

        # Clamp intensity to valid range
        intensity = self._clamp_intensity(intensity)

        # Map intensity (1-10) to gain (2-20dB)
        gain = intensity * 2

        logger.info(f"Applying bass boost: intensity={intensity}, gain={gain}dB")

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command with bass filter
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-af", f"bass=gain={gain}",  # Bass boost filter
            "-c:a", "libmp3lame",  # Output codec (MP3 for compatibility)
            "-b:a", "192k",  # Bitrate
            "-q:a", "2",  # Quality
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
            logger.info(f"Bass boost applied successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise AudioEnhancementError(
                f"Error aplicando bass boost: {e.stderr[:100]}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during bass boost: {e}")
            raise AudioEnhancementError(f"Error inesperado: {str(e)}") from e

    def treble_boost(self, intensity: float = 5.0) -> bool:
        """Apply treble boost enhancement to audio.

        Uses ffmpeg treble filter to enhance high frequencies around 3000-10000Hz.
        Intensity maps to gain: 1-10 -> 1.5-15dB boost

        Args:
            intensity: Boost intensity from 1.0 to 10.0 (default 5.0)

        Returns:
            True if enhancement succeeded

        Raises:
            AudioEnhancementError: If enhancement fails
        """
        self._validate_input()

        # Clamp intensity to valid range
        intensity = self._clamp_intensity(intensity)

        # Map intensity (1-10) to gain (1.5-15dB)
        gain = intensity * 1.5

        logger.info(f"Applying treble boost: intensity={intensity}, gain={gain}dB")

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command with treble filter
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-af", f"treble=gain={gain}",  # Treble boost filter
            "-c:a", "libmp3lame",  # Output codec (MP3 for compatibility)
            "-b:a", "192k",  # Bitrate
            "-q:a", "2",  # Quality
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
            logger.info(f"Treble boost applied successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise AudioEnhancementError(
                f"Error aplicando treble boost: {e.stderr[:100]}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during treble boost: {e}")
            raise AudioEnhancementError(f"Error inesperado: {str(e)}") from e

    def equalize(self, bass: float = 0, mid: float = 0, treble: float = 0) -> bool:
        """Apply 3-band equalizer to audio.

        Uses ffmpeg equalizer filter with three frequency bands:
        - Bass: 125Hz (20-250Hz range)
        - Mid: 1000Hz (250Hz-4kHz range)
        - Treble: 8000Hz (4kHz-20kHz range)

        Gain values map: -10 to +10 -> -15dB to +15dB

        Args:
            bass: Bass gain from -10 to +10 (default 0, no change)
            mid: Mid gain from -10 to +10 (default 0, no change)
            treble: Treble gain from -10 to +10 (default 0, no change)

        Returns:
            True if enhancement succeeded

        Raises:
            AudioEnhancementError: If enhancement fails
        """
        self._validate_input()

        # Clamp gains to valid range
        bass_gain = self._clamp_eq_gain(bass)
        mid_gain = self._clamp_eq_gain(mid)
        treble_gain = self._clamp_eq_gain(treble)

        # Map input (-10 to +10) to actual dB gain (-15 to +15)
        bass_db = bass_gain * 1.5
        mid_db = mid_gain * 1.5
        treble_db = treble_gain * 1.5

        logger.info(
            f"Applying equalizer: bass={bass_gain}->{bass_db}dB, "
            f"mid={mid_gain}->{mid_db}dB, treble={treble_gain}->{treble_db}dB"
        )

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build equalizer filter chain
        # Band 1: Bass at 125Hz
        # Band 2: Mid at 1000Hz
        # Band 3: Treble at 8000Hz
        eq_filter = (
            f"equalizer=f=125:width_type=o:width=2:gain={bass_db},"
            f"equalizer=f=1000:width_type=o:width=2:gain={mid_db},"
            f"equalizer=f=8000:width_type=o:width=2:gain={treble_db}"
        )

        # Build ffmpeg command with equalizer filter
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(self.input_path),  # Input file
            "-af", eq_filter,  # Equalizer filter chain
            "-c:a", "libmp3lame",  # Output codec (MP3 for compatibility)
            "-b:a", "192k",  # Bitrate
            "-q:a", "2",  # Quality
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
            logger.info(f"Equalizer applied successfully: {self.output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise AudioEnhancementError(
                f"Error aplicando ecualizador: {e.stderr[:100]}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during equalization: {e}")
            raise AudioEnhancementError(f"Error inesperado: {str(e)}") from e


__all__ = [
    "AudioEnhancer",
]
