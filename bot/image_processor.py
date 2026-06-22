"""Image processing module for the Telegram bot.

Provides image compression, format conversion, and resizing using Pillow.
Follows the same patterns as audio/video processors in the codebase.
"""
import logging
import os
from io import BytesIO
from typing import Tuple, Optional, Dict, Any

from PIL import Image, ImageEnhance, ImageOps, ImageStat

logger = logging.getLogger(__name__)

# Supported formats for conversion
SUPPORTED_IMAGE_FORMATS = {
    "jpeg": {"ext": ".jpg", "mime": "image/jpeg", "description": "JPEG (alto compatibilidad)"},
    "png": {"ext": ".png", "mime": "image/png", "description": "PNG (sin pérdida)"},
    "webp": {"ext": ".webp", "mime": "image/webp", "description": "WebP (buena compresión)"},
}

# Default quality values per format
DEFAULT_QUALITY = {
    "jpeg": 85,
    "png": 85,  # PNG compression level (1-9 mapped to Pillow's 0-9)
    "webp": 80,
}

# Max dimensions for Telegram
MAX_DIMENSION = 2560  # Telegram squarifies photos > 2560px on one side

# Mean luminance above this (0-255) triggers reduced brightness/contrast scaling
BRIGHT_LUMINANCE_THRESHOLD = 200

# Enhancement profile definitions (Pillow ImageEnhance / ImageOps)
ENHANCEMENT_PROFILES = {
    "brillo": "Brillo",
    "colores": "Colores",
    "nitidez": "Nitidez",
    "equilibrado": "Equilibrado",
    "suave": "Suave",
}


class ImageProcessingError(Exception):
    """Base exception for image processing errors."""

    def __init__(self, message: str = "Error procesando la imagen"):
        self.message = message
        super().__init__(self.message)


class ImageCompressionError(ImageProcessingError):
    """Exception raised when image compression fails."""

    def __init__(self, message: str = "No pude comprimir la imagen"):
        self.message = message
        super().__init__(self.message)


class ImageConversionError(ImageProcessingError):
    """Exception raised when image format conversion fails."""

    def __init__(self, message: str = "No pude convertir el formato de la imagen"):
        self.message = message
        super().__init__(self.message)


class ImageResizeError(ImageProcessingError):
    """Exception raised when image resizing fails."""

    def __init__(self, message: str = "No pude redimensionar la imagen"):
        self.message = message
        super().__init__(self.message)


class ImageProcessor:
    """Processes images: compress, convert format, resize, and read info.

    All operations work with file paths and return (success, result_or_error).
    Follows the same patterns as AudioProcessor and VideoProcessor modules.
    """

    @staticmethod
    def _mean_luminance(img: Image.Image) -> float:
        """Return mean luminance (0-255) of an image."""
        return ImageStat.Stat(img.convert("L")).mean[0]

    @staticmethod
    def _bright_image_scale(mean_luminance: float) -> float:
        """Scale enhancement factors down for already-bright images."""
        if mean_luminance <= BRIGHT_LUMINANCE_THRESHOLD:
            return 1.0
        excess = (mean_luminance - BRIGHT_LUMINANCE_THRESHOLD) / (
            255 - BRIGHT_LUMINANCE_THRESHOLD
        )
        return max(0.35, 1.0 - excess * 0.65)

    @staticmethod
    def _scaled_enhance_factor(base_factor: float, scale: float) -> float:
        """Apply bright-image scale to an enhancement multiplier."""
        return 1.0 + (base_factor - 1.0) * scale

    @staticmethod
    def compress(
        input_path: str,
        output_path: str,
        quality: int = 85,
        max_dimension: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Compress an image by adjusting quality and optionally resizing.

        Args:
            input_path: Path to input image
            output_path: Path to save compressed image
            quality: JPEG/WebP quality (1-100, default 85)
            max_dimension: If set, resize image to fit within this dimension

        Returns:
            Tuple of (success, error_message)
        """
        logger.debug(f"Compressing image: {input_path} (quality={quality})")

        try:
            with Image.open(input_path) as img:
                # Convert to RGB if saving as JPEG (RGBA not supported)
                original_mode = img.mode
                img_format = img.format or "JPEG"

                # Determine output format from extension
                out_ext = os.path.splitext(output_path)[1].lower()
                if out_ext in (".jpg", ".jpeg"):
                    save_format = "JPEG"
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                elif out_ext == ".png":
                    save_format = "PNG"
                    # Map quality (1-100) to PNG compression (0-9)
                    png_compress = max(0, min(9, int((100 - quality) / 10)))
                elif out_ext == ".webp":
                    save_format = "WEBP"
                    if img.mode in ("P",):
                        img = img.convert("RGBA")
                else:
                    save_format = img_format

                # Resize if max_dimension is set and image exceeds it
                if max_dimension:
                    orig_w, orig_h = img.size
                    if max(orig_w, orig_h) > max_dimension:
                        ratio = max_dimension / max(orig_w, orig_h)
                        new_w = int(orig_w * ratio)
                        new_h = int(orig_h * ratio)
                        img = img.resize((new_w, new_h), Image.LANCZOS)
                        logger.debug(
                            f"Resized from {orig_w}x{orig_h} to {new_w}x{new_h}"
                        )

                # Save with compression
                save_kwargs: Dict[str, Any] = {"format": save_format}
                if save_format == "JPEG":
                    save_kwargs["quality"] = quality
                    save_kwargs["optimize"] = True
                elif save_format == "WEBP":
                    save_kwargs["quality"] = quality
                elif save_format == "PNG":
                    save_kwargs["compress_level"] = png_compress

                img.save(output_path, **save_kwargs)

            # Verify output was created
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"Compression produced empty file: {output_path}")
                return False, "La compresión produjo un archivo vacío"

            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
            logger.info(
                f"Image compressed: {input_size} -> {output_size} bytes "
                f"({ratio:.1f}% reduction)"
            )

            return True, None

        except Exception as e:
            logger.error(f"Image compression failed: {e}")
            return False, str(e)

    @staticmethod
    def convert_format(
        input_path: str, output_path: str, target_format: str
    ) -> Tuple[bool, Optional[str]]:
        """Convert image to a different format.

        Args:
            input_path: Path to input image
            output_path: Path to save converted image
            target_format: Target format (jpeg, png, webp)

        Returns:
            Tuple of (success, error_message)
        """
        logger.debug(
            f"Converting image: {input_path} to {target_format}"
        )

        # Validate target format
        target_format = target_format.lower()
        if target_format not in SUPPORTED_IMAGE_FORMATS:
            return (
                False,
                f"Formato '{target_format}' no soportado. "
                f"Usa: {', '.join(SUPPORTED_IMAGE_FORMATS.keys())}",
            )

        # Map format name to Pillow format
        format_map = {
            "jpeg": "JPEG",
            "png": "PNG",
            "webp": "WEBP",
        }
        pil_format = format_map[target_format]

        try:
            with Image.open(input_path) as img:
                # Handle mode conversions
                if pil_format == "JPEG" and img.mode in ("RGBA", "P"):
                    # Create white background for RGBA -> JPEG
                    if img.mode == "RGBA":
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3])
                        img = background
                    else:
                        img = img.convert("RGB")
                elif pil_format == "WEBP" and img.mode == "P":
                    img = img.convert("RGBA")

                # Save with format-appropriate quality
                save_kwargs: Dict[str, Any] = {"format": pil_format}
                quality = DEFAULT_QUALITY.get(target_format, 85)

                if pil_format in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = quality

                img.save(output_path, **save_kwargs)

            # Verify output
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"Conversion produced empty file: {output_path}")
                return False, "La conversión produjo un archivo vacío"

            logger.info(
                f"Image converted to {target_format}: {output_path} "
                f"({os.path.getsize(output_path)} bytes)"
            )
            return True, None

        except Exception as e:
            logger.error(f"Image format conversion failed: {e}")
            return False, str(e)

    @staticmethod
    def resize(
        input_path: str,
        output_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        percentage: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Resize an image to specific dimensions or by percentage.

        Args:
            input_path: Path to input image
            output_path: Path to save resized image
            width: Target width (if height not set, maintains aspect ratio)
            height: Target height (if width not set, maintains aspect ratio)
            percentage: Resize by percentage (e.g., 50 = half size)

        Returns:
            Tuple of (success, error_message)
        """
        logger.debug(
            f"Resizing image: {input_path} "
            f"(width={width}, height={height}, pct={percentage})"
        )

        try:
            with Image.open(input_path) as img:
                orig_w, orig_h = img.size

                if percentage:
                    # Resize by percentage
                    new_w = int(orig_w * percentage / 100)
                    new_h = int(orig_h * percentage / 100)
                elif width and height:
                    # Resize to exact dimensions
                    new_w, new_h = width, height
                elif width:
                    # Resize width, maintain aspect ratio
                    ratio = width / orig_w
                    new_w = width
                    new_h = int(orig_h * ratio)
                elif height:
                    # Resize height, maintain aspect ratio
                    ratio = height / orig_h
                    new_h = height
                    new_w = int(orig_w * ratio)
                else:
                    return False, "Especifica dimensiones o porcentaje"

                # Ensure minimum size
                new_w = max(1, new_w)
                new_h = max(1, new_h)

                resized = img.resize((new_w, new_h), Image.LANCZOS)

                # Determine output format from extension or keep original
                out_ext = os.path.splitext(output_path)[1].lower()
                save_format = img.format or "JPEG"

                if out_ext in (".jpg", ".jpeg"):
                    save_format = "JPEG"
                    if resized.mode in ("RGBA", "P"):
                        resized = resized.convert("RGB")
                elif out_ext == ".png":
                    save_format = "PNG"
                elif out_ext == ".webp":
                    save_format = "WEBP"

                save_kwargs: Dict[str, Any] = {"format": save_format}
                if save_format in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = 90

                resized.save(output_path, **save_kwargs)

            # Verify output
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"Resize produced empty file: {output_path}")
                return False, "El redimensionamiento produjo un archivo vacío"

            logger.info(
                f"Image resized: {orig_w}x{orig_h} -> {new_w}x{new_h} "
                f"({os.path.getsize(output_path)} bytes)"
            )
            return True, None

        except Exception as e:
            logger.error(f"Image resize failed: {e}")
            return False, str(e)

    @staticmethod
    def get_image_info(input_path: str) -> Dict[str, Any]:
        """Get image metadata (dimensions, format, file size).

        Args:
            input_path: Path to the image file

        Returns:
            Dict with keys: width, height, format, file_size, mode
        """
        info: Dict[str, Any] = {
            "width": 0,
            "height": 0,
            "format": "unknown",
            "file_size": 0,
            "mode": "unknown",
        }

        try:
            with Image.open(input_path) as img:
                info["width"] = img.width
                info["height"] = img.height
                info["format"] = img.format or "unknown"
                info["mode"] = img.mode

            info["file_size"] = os.path.getsize(input_path)
            logger.debug(f"Image info: {info}")

        except Exception as e:
            logger.error(f"Failed to get image info: {e}")

        return info

    @staticmethod
    def enhance(
        input_path: str,
        output_path: str,
        profile: str,
    ) -> Tuple[bool, Optional[str]]:
        """Enhance an image using a predefined profile.

        Profiles apply Pillow ImageEnhance and ImageOps adjustments:
        - brillo: autocontrast(cutoff=1%) + brightness 1.08 + contrast 1.05
        - colores: color 1.20 + contrast 1.10
        - nitidez: sharpness 1.35 + contrast 1.05
        - equilibrado: brightness 1.05, contrast 1.10, color 1.12, sharpness 1.15
        - suave: brightness 1.03, color 1.06, sharpness 1.08

        Args:
            input_path: Path to input image
            output_path: Path to save enhanced image
            profile: Enhancement profile key

        Returns:
            Tuple of (success, error_message)
        """
        profile = profile.lower()
        if profile not in ENHANCEMENT_PROFILES:
            return (
                False,
                f"Perfil '{profile}' no soportado. "
                f"Usa: {', '.join(ENHANCEMENT_PROFILES.keys())}",
            )

        logger.debug(f"Enhancing image: {input_path} (profile={profile})")

        try:
            with Image.open(input_path) as img:
                mean_lum = ImageProcessor._mean_luminance(img)
                bright_scale = ImageProcessor._bright_image_scale(mean_lum)
                if bright_scale < 1.0:
                    logger.debug(
                        f"Bright image detected (mean luminance={mean_lum:.1f}); "
                        f"scaling enhancements by {bright_scale:.2f}"
                    )

                if profile == "brillo":
                    img = ImageOps.autocontrast(img, cutoff=1)
                    img = ImageEnhance.Brightness(img).enhance(
                        ImageProcessor._scaled_enhance_factor(1.08, bright_scale)
                    )
                    img = ImageEnhance.Contrast(img).enhance(
                        ImageProcessor._scaled_enhance_factor(1.05, bright_scale)
                    )
                elif profile == "colores":
                    img = ImageEnhance.Color(img).enhance(1.20)
                    img = ImageEnhance.Contrast(img).enhance(1.10)
                elif profile == "nitidez":
                    img = ImageEnhance.Sharpness(img).enhance(1.35)
                    img = ImageEnhance.Contrast(img).enhance(1.05)
                elif profile == "equilibrado":
                    img = ImageEnhance.Brightness(img).enhance(
                        ImageProcessor._scaled_enhance_factor(1.05, bright_scale)
                    )
                    img = ImageEnhance.Contrast(img).enhance(
                        ImageProcessor._scaled_enhance_factor(1.10, bright_scale)
                    )
                    img = ImageEnhance.Color(img).enhance(1.12)
                    img = ImageEnhance.Sharpness(img).enhance(1.15)
                elif profile == "suave":
                    img = ImageEnhance.Brightness(img).enhance(1.03)
                    img = ImageEnhance.Color(img).enhance(1.06)
                    img = ImageEnhance.Sharpness(img).enhance(1.08)

                out_ext = os.path.splitext(output_path)[1].lower()
                save_format = img.format or "JPEG"

                if out_ext in (".jpg", ".jpeg"):
                    save_format = "JPEG"
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                elif out_ext == ".png":
                    save_format = "PNG"
                elif out_ext == ".webp":
                    save_format = "WEBP"
                    if img.mode == "P":
                        img = img.convert("RGBA")

                save_kwargs: Dict[str, Any] = {"format": save_format}
                if save_format in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = 90
                if save_format == "JPEG":
                    save_kwargs["optimize"] = True

                img.save(output_path, **save_kwargs)

            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"Enhancement produced empty file: {output_path}")
                return False, "La mejora produjo un archivo vacío"

            logger.info(
                f"Image enhanced with profile '{profile}': {output_path} "
                f"({os.path.getsize(output_path)} bytes)"
            )
            return True, None

        except Exception as e:
            logger.error(f"Image enhancement failed: {e}")
            return False, str(e)


__all__ = [
    "ImageProcessor",
    "ImageProcessingError",
    "ImageCompressionError",
    "ImageConversionError",
    "ImageResizeError",
    "SUPPORTED_IMAGE_FORMATS",
    "ENHANCEMENT_PROFILES",
]
