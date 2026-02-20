"""Audio effects module for professional audio processing using ffmpeg filters.

Provides AudioEffects for applying professional audio effects including:
- Noise reduction (denoise) using afftdn filter
- Dynamic range compression (compress) using acompressor filter
- Loudness normalization (normalize) using loudnorm filter

Effects can be chained for pipeline processing: effects.denoise().compress().normalize()
"""
import shutil
import subprocess
import logging
import tempfile
from pathlib import Path
from typing import Optional

from bot.error_handler import AudioEffectsError

logger = logging.getLogger(__name__)


class AudioEffects:
    """Apply professional audio effects using ffmpeg filters.

    Supports method chaining for effect pipelines:
        effects.denoise().compress().normalize()

    Effects:
        - denoise: FFT-based noise reduction (afftdn filter)
        - compress: Dynamic range compression (acompressor filter)
        - normalize: EBU R128 loudness normalization (loudnorm filter)
    """

    # Denoise parameter ranges
    MIN_DENOISE_STRENGTH = 1.0
    MAX_DENOISE_STRENGTH = 10.0
    DENOISE_NR_MIN = 0.01  # Minimum noise reduction factor
    DENOISE_NR_MAX = 0.5   # Maximum noise reduction factor

    # Compressor parameter ranges
    MIN_COMPRESS_RATIO = 1.0
    MAX_COMPRESS_RATIO = 20.0
    MIN_COMPRESS_THRESHOLD = -60.0  # dB
    MAX_COMPRESS_THRESHOLD = 0.0    # dB

    # Normalization parameter ranges
    MIN_TARGET_LUFS = -23.0
    MAX_TARGET_LUFS = -5.0

    def __init__(self, input_path: str, output_path: str):
        """Initialize audio effects processor.

        Args:
            input_path: Path to input audio file
            output_path: Path for processed output audio
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self._temp_files: list[Path] = []
        self._in_chain = False

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
            AudioEffectsError: If validation fails
        """
        if not self._check_ffmpeg():
            logger.error("ffmpeg is not installed or not in PATH")
            raise AudioEffectsError("ffmpeg no está disponible")

        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            raise AudioEffectsError("El archivo de entrada no existe")

    def _get_input_for_effect(self) -> Path:
        """Get the appropriate input path for the current effect.

        Returns:
            Path to use as input (original or from previous effect in chain)
        """
        if self._in_chain and self._temp_files:
            return self._temp_files[-1]
        return self.input_path

    def _create_temp_output(self) -> Path:
        """Create a temporary file for intermediate output in effect chain.

        Returns:
            Path to temporary file
        """
        temp_dir = tempfile.gettempdir()
        temp_file = Path(temp_dir) / f"audio_effect_{id(self)}_{len(self._temp_files)}.mp3"
        self._temp_files.append(temp_file)
        return temp_file

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary intermediate files."""
        for temp_file in self._temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
        self._temp_files.clear()

    def _clamp_value(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value to valid range.

        Args:
            value: Input value
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Clamped value between min_val and max_val
        """
        return max(min_val, min(max_val, value))

    def _map_strength_to_nr(self, strength: float) -> float:
        """Map denoise strength (1-10) to noise reduction factor (0.01-0.5).

        Args:
            strength: Input strength from 1.0 to 10.0

        Returns:
            Noise reduction factor for afftdn nr parameter
        """
        # Linear mapping: 1->0.01, 10->0.5
        normalized = (strength - self.MIN_DENOISE_STRENGTH) / (
            self.MAX_DENOISE_STRENGTH - self.MIN_DENOISE_STRENGTH
        )
        return self.DENOISE_NR_MIN + normalized * (
            self.DENOISE_NR_MAX - self.DENOISE_NR_MIN
        )

    def denoise(self, strength: float = 5.0) -> "AudioEffects":
        """Apply noise reduction to audio using FFT denoiser.

        Uses ffmpeg afftdn (FFT Denoiser) filter for noise reduction.
        Higher strength values apply more aggressive noise reduction.

        Args:
            strength: Noise reduction strength from 1.0 to 10.0 (default 5.0)
                     1.0 = subtle noise reduction
                     10.0 = aggressive noise reduction

        Returns:
            Self to enable method chaining

        Raises:
            AudioEffectsError: If denoise processing fails
        """
        self._validate_input()

        # Clamp strength to valid range
        strength = self._clamp_value(
            strength, self.MIN_DENOISE_STRENGTH, self.MAX_DENOISE_STRENGTH
        )

        # Map strength to noise reduction factor
        nr_value = self._map_strength_to_nr(strength)

        logger.info(f"Applying denoise: strength={strength}, nr={nr_value:.3f}")

        # Determine input and output paths
        input_path = self._get_input_for_effect()

        if self._in_chain:
            output_path = self._create_temp_output()
        else:
            output_path = self.output_path
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command with afftdn filter
        # nf=-70: noise floor in dB
        # nr: noise reduction factor (0.01 to 0.5)
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(input_path),  # Input file
            "-af", f"afftdn=nf=-70:nr={nr_value:.3f}",  # FFT denoiser filter
            "-c:a", "libmp3lame",  # Output codec (MP3 for compatibility)
            "-b:a", "192k",  # Bitrate
            "-q:a", "2",  # Quality
            str(output_path),  # Output file
        ]

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Denoise applied successfully: {output_path}")

            # Mark that we're now in a chain
            self._in_chain = True

            return self

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            self._cleanup_temp_files()
            raise AudioEffectsError(
                f"Error aplicando reducción de ruido: {e.stderr[:100]}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during denoise: {e}")
            self._cleanup_temp_files()
            raise AudioEffectsError(f"Error inesperado: {str(e)}") from e

    def compress(self, ratio: float = 4.0, threshold: float = -20.0) -> "AudioEffects":
        """Apply dynamic range compression to audio.

        Uses ffmpeg acompressor filter to reduce dynamic range.
        Useful for making quiet parts louder and loud parts quieter.

        Args:
            ratio: Compression ratio from 1.0 to 20.0 (default 4.0)
                   Higher ratio = more compression
            threshold: Threshold in dB from -60.0 to 0.0 (default -20.0)
                      Signals above this level are compressed

        Returns:
            Self to enable method chaining

        Raises:
            AudioEffectsError: If compression processing fails
        """
        self._validate_input()

        # Clamp parameters to valid ranges
        ratio = self._clamp_value(
            ratio, self.MIN_COMPRESS_RATIO, self.MAX_COMPRESS_RATIO
        )
        threshold = self._clamp_value(
            threshold, self.MIN_COMPRESS_THRESHOLD, self.MAX_COMPRESS_THRESHOLD
        )

        logger.info(f"Applying compression: ratio={ratio}, threshold={threshold}dB")

        # Determine input and output paths
        input_path = self._get_input_for_effect()

        if self._in_chain:
            output_path = self._create_temp_output()
        else:
            output_path = self.output_path
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command with acompressor filter
        # attack=5ms: quick response to signal above threshold
        # release=100ms: smooth return to normal after signal drops
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(input_path),  # Input file
            "-af", f"acompressor=threshold={threshold}dB:ratio={ratio}:attack=5:release=100",
            "-c:a", "libmp3lame",  # Output codec (MP3 for compatibility)
            "-b:a", "192k",  # Bitrate
            "-q:a", "2",  # Quality
            str(output_path),  # Output file
        ]

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Compression applied successfully: {output_path}")

            # Mark that we're now in a chain
            self._in_chain = True

            return self

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            self._cleanup_temp_files()
            raise AudioEffectsError(
                f"Error aplicando compresión: {e.stderr[:100]}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during compression: {e}")
            self._cleanup_temp_files()
            raise AudioEffectsError(f"Error inesperado: {str(e)}") from e

    def normalize(self, target_lufs: float = -14.0) -> "AudioEffects":
        """Apply EBU R128 loudness normalization to audio.

        Uses ffmpeg loudnorm filter to normalize audio to a standard loudness level.
        Useful for achieving consistent loudness across different audio files.

        Args:
            target_lufs: Target loudness in LUFS from -23.0 to -5.0 (default -14.0)
                        -23.0 = broadcast standard (EBU R128)
                        -14.0 = streaming standard (Spotify, YouTube)
                        -5.0  = loud, for podcasts/speech

        Returns:
            Self to enable method chaining

        Raises:
            AudioEffectsError: If normalization processing fails
        """
        self._validate_input()

        # Clamp target to valid range
        target_lufs = self._clamp_value(
            target_lufs, self.MIN_TARGET_LUFS, self.MAX_TARGET_LUFS
        )

        logger.info(f"Applying normalization: target={target_lufs} LUFS")

        # Determine input and output paths
        input_path = self._get_input_for_effect()

        if self._in_chain:
            output_path = self._create_temp_output()
        else:
            output_path = self.output_path
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command with loudnorm filter
        # I = integrated loudness (target LUFS)
        # TP = true peak limit (-1dB to prevent clipping)
        # LRA = loudness range (11 for general audio, 1 for speech)
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output if exists
            "-i", str(input_path),  # Input file
            "-af", f"loudnorm=I={target_lufs}:TP=-1:LRA=11",
            "-c:a", "libmp3lame",  # Output codec (MP3 for compatibility)
            "-b:a", "192k",  # Bitrate
            "-q:a", "2",  # Quality
            str(output_path),  # Output file
        ]

        try:
            logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Normalization applied successfully: {output_path}")

            # Mark that we're now in a chain
            self._in_chain = True

            return self

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            self._cleanup_temp_files()
            raise AudioEffectsError(
                f"Error aplicando normalización: {e.stderr[:100]}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during normalization: {e}")
            self._cleanup_temp_files()
            raise AudioEffectsError(f"Error inesperado: {str(e)}") from e

    def finalize(self) -> Path:
        """Finalize effect chain and return output path.

        Moves the final result to the specified output path if in a chain,
        cleans up temporary files, and returns the output path.

        Returns:
            Path to the final output file

        Raises:
            AudioEffectsError: If finalization fails
        """
        try:
            if self._in_chain and self._temp_files:
                # Get the last temp file (final result)
                final_temp = self._temp_files[-1]

                # Ensure output directory exists
                self.output_path.parent.mkdir(parents=True, exist_ok=True)

                # Move to final destination if different
                if final_temp != self.output_path:
                    import shutil
                    shutil.move(str(final_temp), str(self.output_path))
                    logger.info(f"Moved final output to: {self.output_path}")

                # Clean up remaining temp files
                self._cleanup_temp_files()

            if not self.output_path.exists():
                raise AudioEffectsError("El archivo de salida no fue creado")

            return self.output_path

        except Exception as e:
            self._cleanup_temp_files()
            if isinstance(e, AudioEffectsError):
                raise
            logger.error(f"Error finalizing effect chain: {e}")
            raise AudioEffectsError(f"Error finalizando cadena de efectos: {str(e)}") from e

    def __enter__(self) -> "AudioEffects":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - clean up temp files."""
        self._cleanup_temp_files()


__all__ = [
    "AudioEffects",
]
