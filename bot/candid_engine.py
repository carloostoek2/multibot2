"""Motor fotográfico «candid» para el bot.

Portado de ``ai-candid/candid.py`` (commit 721e12f). Aplica la cadena de
defectos de una foto real: aberración cromática, caída de nitidez, viñeteo,
halación, curva de tono imperfecta, grano de sensor/película y compresión JPEG
real. Cada imagen muestrea parámetros distintos dentro del preset.

Requisitos de sistema:
  - ImageMagick 7 (binario ``magick``), obligatorio.
  - G'MIC 2.9.4 con ``fx_simulate_grain``, opcional. Si falta o falla, el grano
    se genera con ImageMagick.

Mantener este módulo en sincronía con ai-candid cuando cambie la cadena.
"""

from __future__ import annotations

import logging
import math
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAGICK = "magick"
GMIC = "gmic"

# Máximo de píxeles de entrada. Evita que una imagen descomprimida consuma
# memoria desproporcionada dentro de ImageMagick.
MAX_INPUT_PIXELS = 40_000_000

DEFAULT_PRESET = "medium"

PRESET_LABELS = {
    "subtle": "Sutil",
    "medium": "Media",
    "strong": "Fuerte",
}

# Tintes de balance de blancos imperfecto. Las fotos reales rara vez son neutras.
WARM_CASTS = ("#ffd9b0", "#ffe0c4", "#ffcf9e")
COOL_CASTS = ("#cfe2ff", "#d8e8ff", "#c4d8f0")


class CandidError(Exception):
    """Error base del efecto fotográfico."""

    def __init__(self, message: str = "No pude aplicar el efecto fotográfico"):
        self.message = message
        super().__init__(self.message)


class CandidUnavailableError(CandidError):
    """Falta una herramienta del sistema necesaria para el efecto."""


class CandidProcessingError(CandidError):
    """La cadena de ImageMagick/G'MIC falló."""


@dataclass(frozen=True)
class Preset:
    """Rangos de parámetros. Cada imagen muestrea un valor de cada rango."""

    downscale: tuple[float, float]  # factor final de resolución (1.0 = sin cambio)
    rotate: tuple[float, float]  # grados máximos de inclinación (se muestrea ±)
    ca: tuple[float, float]  # divergencia radial entre canal R y B
    blur: tuple[float, float]  # sigma del desenfoque óptico
    clip: tuple[float, float]  # % recortado en cada extremo del histograma
    contrast: tuple[float, float]  # intensidad de la curva S fílmica
    saturation: tuple[float, float]  # saturación final en %
    cast: tuple[float, float]  # % de tinte de balance de blancos
    halo_sigma: tuple[float, float]  # radio de la halación
    halo_level: tuple[float, float]  # umbral de altas luces para la halación
    vignette: tuple[float, float]  # profundidad del viñeteo (0-1)
    grain: tuple[float, float]  # amplitud del ruido (motor ImageMagick)
    grain_stock: tuple[int, int]  # película G'MIC: 0 Orwo, 1 TMAX400, 2 TMAX3200, 3 TRI-X
    grain_opacity: tuple[float, float]  # opacidad del grano G'MIC
    grain_scale: tuple[float, float]  # tamaño del grano G'MIC (menor = más grueso)
    quality: tuple[int, int]  # calidad JPEG
    double_pass: bool  # doble recompresión (historial de compresión real)


PRESETS: dict[str, Preset] = {
    # Móvil moderno bien expuesto: apenas se nota, pero deja de ser "perfecto".
    "subtle": Preset(
        downscale=(1.0, 1.0), rotate=(0.0, 0.15), ca=(0.0002, 0.0006),
        blur=(0.15, 0.40), clip=(0.3, 0.8), contrast=(0.0, 1.2),
        saturation=(97.0, 102.0), cast=(0.6, 1.8),
        halo_sigma=(6.0, 10.0), halo_level=(88.0, 94.0),
        vignette=(0.04, 0.08), grain=(0.015, 0.035),
        grain_stock=(1, 1), grain_opacity=(0.05, 0.09), grain_scale=(110.0, 150.0),
        quality=(84, 92), double_pass=False,
    ),
    # Snapshot casual de móvil: grano visible, encuadre imperfecto, color desviado.
    "medium": Preset(
        downscale=(0.85, 1.0), rotate=(0.0, 0.45), ca=(0.0006, 0.0015),
        blur=(0.25, 0.55), clip=(0.8, 1.8), contrast=(1.2, 3.0),
        saturation=(90.0, 98.0), cast=(1.5, 3.5),
        halo_sigma=(10.0, 16.0), halo_level=(82.0, 90.0),
        vignette=(0.10, 0.18), grain=(0.040, 0.075),
        grain_stock=(0, 1), grain_opacity=(0.10, 0.18), grain_scale=(90.0, 130.0),
        quality=(86, 92), double_pass=False,
    ),
    # Compacta analógica / móvil viejo: suave, granada, viñeteada, muy recomprimida.
    "strong": Preset(
        downscale=(0.70, 0.88), rotate=(0.0, 0.90), ca=(0.0012, 0.0025),
        blur=(0.40, 0.80), clip=(1.5, 3.5), contrast=(2.5, 5.0),
        saturation=(78.0, 90.0), cast=(3.0, 6.0),
        halo_sigma=(16.0, 26.0), halo_level=(74.0, 84.0),
        vignette=(0.18, 0.32), grain=(0.080, 0.150),
        grain_stock=(2, 3), grain_opacity=(0.20, 0.32), grain_scale=(70.0, 110.0),
        quality=(64, 74), double_pass=True,
    ),
}

PRESET_NAMES = tuple(PRESETS)


def is_available() -> bool:
    """Return True when the mandatory ImageMagick 7 binary is installed."""
    return shutil.which(MAGICK) is not None


def gmic_available() -> bool:
    """Return True when G'MIC is installed (film grain engine)."""
    return shutil.which(GMIC) is not None


def run(cmd: list[str]) -> None:
    """Ejecuta un comando y levanta un error legible si falla."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])}… falló:\n{result.stderr.strip()}")


def image_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        [MAGICK, "identify", "-format", "%w %h", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return int(out[0]), int(out[1])


def safe_crop_scale(width: int, height: int, theta: float) -> float:
    """Mayor rectángulo centrado, con la proporción original, que cabe tras rotar.

    Evita el borde negro que dejaría girar sin recortar.
    """
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    return min(
        width / (width * cos_t + height * sin_t),
        height / (width * sin_t + height * cos_t),
    )


def sample_scale(
    preset: Preset, rng: random.Random, upscale: float | None
) -> tuple[float, float]:
    """Devuelve (escala_efectiva, ratio frente al preset).

    ``upscale`` se mide respecto al tamaño original: 2.0 = el doble de píxeles.
    """
    base = rng.uniform(*preset.downscale)
    effective = upscale if upscale else base
    return effective, effective / base


def build_command(
    src: Path,
    dst: Path,
    preset: Preset,
    size: tuple[int, int],
    rng: random.Random,
    scale: float,
    ratio: float,
    include_grain: bool = True,
    quality: int | None = None,
) -> list[str]:
    """Construye el comando de ImageMagick que aplica la cadena completa."""
    width, height = size
    cmd = [MAGICK, str(src), "-auto-orient", "+repage", "-alpha", "off", "-strip"]

    # 1. Geometría: inclinación de mano + recorte compensado.
    angle = rng.uniform(-preset.rotate[1], preset.rotate[1])
    if abs(angle) > 0.05:
        factor = safe_crop_scale(width, height, math.radians(abs(angle)))
        cmd += [
            "-background", "black", "-rotate", f"{angle:.3f}",
            "-gravity", "center",
            "-crop", f"{int(width * factor)}x{int(height * factor)}+0+0", "+repage",
            "-resize", f"{width}x{height}!",
        ]

    # 2. Resolución final. ``scale`` ya incluye el posible upscale.
    out_w = max(1, round(width * scale))
    out_h = max(1, round(height * scale))
    if abs(scale - 1.0) > 0.001:
        cmd += ["-filter", "Lanczos", "-resize", f"{out_w}x{out_h}!"]

    # 3. Aberración cromática: R se agranda y B se encoge respecto al centro.
    divergence = rng.uniform(*preset.ca)
    # -distort SRT exige "escala,ángulo": con un solo valor lo interpreta como
    # ángulo y rota la imagen decenas de grados.
    red_scale = f"{1 + divergence / 2:.6f},0"
    blue_scale = f"{1 - divergence / 2:.6f},0"
    # Al escalar los canales por separado, el borde del encuadre queda con una
    # franja de color falsa. Se recorta y se devuelve al tamaño final.
    edge_px = max(2, math.ceil(divergence * max(out_w, out_h) / 2) + 1)
    cmd += [
        "(", "-clone", "0", "-channel", "R", "-separate",
        "-virtual-pixel", "edge", "-distort", "SRT", red_scale, ")",
        "(", "-clone", "0", "-channel", "G", "-separate", ")",
        "(", "-clone", "0", "-channel", "B", "-separate",
        "-virtual-pixel", "edge", "-distort", "SRT", blue_scale, ")",
        "-delete", "0", "-combine",
        "-shave", f"{edge_px}x{edge_px}", "-resize", f"{out_w}x{out_h}!",
    ]

    # 4. Óptica: caída de nitidez (escala con la resolución de salida).
    cmd += ["-gaussian-blur", f"0x{rng.uniform(*preset.blur) * ratio:.2f}"]

    # 5. Curva de tono: recorte de extremos, contraste fílmico, color.
    low, high = rng.uniform(*preset.clip), rng.uniform(*preset.clip)
    cmd += [
        "-level", f"{low:.2f}%,{100 - high:.2f}%",
        "-sigmoidal-contrast", f"{rng.uniform(*preset.contrast):.2f},48%",
        "-modulate", f"100,{rng.uniform(*preset.saturation):.1f},100",
    ]
    cast_color = rng.choice(WARM_CASTS if rng.random() < 0.65 else COOL_CASTS)
    cmd += ["-fill", cast_color, "-colorize", f"{rng.uniform(*preset.cast):.2f}%"]

    # 6. Halación: las altas luces sangran hacia las zonas vecinas.
    cmd += [
        "(", "+clone",
        "-blur", f"0x{rng.uniform(*preset.halo_sigma) * ratio:.1f}",
        "-level", f"{rng.uniform(*preset.halo_level):.1f}%,100%", ")",
        "-compose", "Screen", "-composite",
    ]

    # 7. Viñeteo: máscara radial con profundidad controlada.
    depth = rng.uniform(*preset.vignette)
    cmd += [
        "(", "-size", f"{out_w}x{out_h}", "radial-gradient:white-black",
        "-function", "polynomial", f"{depth:.3f},{1 - depth:.3f}", ")",
        "-compose", "Multiply", "-composite",
    ]

    # 8. Ruido de sensor (solo con el motor ImageMagick; G'MIC añade el suyo).
    if include_grain:
        cmd += [
            "(", "+clone", "-fill", "gray50", "-colorize", "100%",
            "-attenuate", f"{rng.uniform(*preset.grain):.4f}", "+noise", "Gaussian", ")",
            "-compose", "Mathematics", "-define", "compose:args=0,1,1,-0.5", "-composite",
        ]

    # 9. Compresión JPEG real: submuestreo de croma y calidad de cámara.
    if dst.suffix.lower() in {".jpg", ".jpeg"}:
        jpeg_quality = quality if quality is not None else rng.randint(*preset.quality)
        cmd += ["-quality", str(jpeg_quality), "-sampling-factor", "4:2:0"]
    cmd += ["-strip", str(dst)]
    return cmd


def build_gmic_command(
    src: Path,
    dst: Path,
    preset: Preset,
    rng: random.Random,
    ratio: float = 1.0,
    quality: int | None = None,
) -> list[str]:
    """Grano de película real (G'MIC) y codificación JPEG en un solo paso."""
    stock = rng.randint(*preset.grain_stock)
    opacity = rng.uniform(*preset.grain_opacity)
    # El grano es físico: a más resolución, más píxeles por grano.
    scale = rng.uniform(*preset.grain_scale) * ratio
    jpeg_quality = quality if quality is not None else rng.randint(*preset.quality)
    # Parámetros: stock, mezcla (1 = Grain Merge), opacidad, escala, nitidez,
    # grano coloreado y los cinco ajustes de tono. La calidad va en 0-100.
    params = f"{stock},1,{opacity:.3f},{scale:.0f},0,0,0,0,0,0,0"
    return [
        GMIC, str(src),
        "-fx_simulate_grain", params,
        "-o", f"{dst},{jpeg_quality}",
    ]


def process_one(
    src: Path,
    dst: Path,
    preset: Preset,
    rng: random.Random,
    keep_jpeg_history: bool,
    engine: str,
    upscale: float | None = None,
    quality: int | None = None,
) -> Path:
    """Procesa una imagen. Devuelve la ruta escrita."""
    width, height = image_size(src)
    final_is_jpeg = dst.suffix.lower() in {".jpg", ".jpeg"}
    scale, ratio = sample_scale(preset, rng, upscale)

    with tempfile.TemporaryDirectory(dir=dst.parent) as tmp_dir:
        tmp = Path(tmp_dir)
        current = tmp / "pass1.jpg"

        if engine == "gmic":
            # ImageMagick aplica óptica y tono; G'MIC añade el grano de película.
            staged = tmp / "stage.png"
            run(build_command(src, staged, preset, (width, height), rng, scale, ratio,
                              include_grain=False, quality=quality))
            run(build_gmic_command(staged, current, preset, rng, ratio, quality))
        else:
            run(build_command(src, current, preset, (width, height), rng, scale, ratio,
                              quality=quality))

        if keep_jpeg_history and preset.double_pass:
            second = tmp / "pass2.jpg"
            second_quality = quality if quality is not None else rng.randint(*preset.quality)
            run([MAGICK, str(current), "-quality", str(second_quality),
                 "-sampling-factor", "4:2:0", "-strip", str(second)])
            current = second

        if final_is_jpeg:
            shutil.move(str(current), dst)
        else:
            run([MAGICK, str(current), "-strip", str(dst)])

    return dst


def apply_effect(
    input_path: str | Path,
    output_path: str | Path,
    preset: str = DEFAULT_PRESET,
    seed: int | None = None,
    engine: str = "auto",
) -> Path:
    """Apply the candid effect to one image and return the written path.

    Args:
        input_path: Source image.
        output_path: Destination path. Use ``.png`` for lossless delivery (the
            JPEG look is already baked into the pixels) or ``.jpg`` for a normal
            Telegram photo.
        preset: One of ``subtle``, ``medium`` or ``strong``.
        seed: Optional seed for reproducible output.
        engine: ``auto``, ``gmic`` or ``imagemagick``.

    Raises:
        CandidUnavailableError: ImageMagick 7 is missing.
        CandidProcessingError: The processing chain failed.
        CandidError: Invalid input, preset, dimensions or engine.
    """
    if preset not in PRESETS:
        raise CandidError(f"Preset '{preset}' no soportado.")
    if engine not in {"auto", "gmic", "imagemagick"}:
        raise CandidError(f"Motor de grano '{engine}' no soportado.")
    if not is_available():
        raise CandidUnavailableError(
            "El efecto fotográfico no está disponible: falta ImageMagick 7 (magick)."
        )

    src = Path(input_path)
    dst = Path(output_path)
    if not src.is_file():
        raise CandidError("No encontré la imagen de entrada.")
    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        width, height = image_size(src)
    except (subprocess.SubprocessError, ValueError, IndexError) as exc:
        raise CandidProcessingError("No pude leer las dimensiones de la imagen.") from exc

    if width <= 0 or height <= 0:
        raise CandidError("La imagen no tiene dimensiones válidas.")
    if width * height > MAX_INPUT_PIXELS:
        raise CandidError(
            "La imagen es demasiado grande para el efecto fotográfico "
            f"({width}×{height}; máximo {MAX_INPUT_PIXELS // 1_000_000} MP)."
        )

    actual_seed = seed if seed is not None else random.randrange(2**32)
    selected_engine = engine
    if selected_engine == "auto":
        selected_engine = "gmic" if gmic_available() else "imagemagick"

    try:
        return process_one(
            src, dst, PRESETS[preset], random.Random(actual_seed),
            keep_jpeg_history=True, engine=selected_engine,
        )
    except RuntimeError as exc:
        if selected_engine != "gmic":
            raise CandidProcessingError(str(exc)) from exc
        # G'MIC puede estar instalado sin la stdlib de filtros. El grano de
        # ImageMagick es algo más simple, pero el efecto completo sigue siendo
        # válido y reproducible con la misma semilla.
        logger.warning("G'MIC falló; usando grano de ImageMagick: %s", exc)
        try:
            return process_one(
                src, dst, PRESETS[preset], random.Random(actual_seed),
                keep_jpeg_history=True, engine="imagemagick",
            )
        except RuntimeError as retry_exc:
            raise CandidProcessingError(str(retry_exc)) from retry_exc


__all__ = [
    "CandidError",
    "CandidProcessingError",
    "CandidUnavailableError",
    "DEFAULT_PRESET",
    "MAX_INPUT_PIXELS",
    "PRESET_LABELS",
    "PRESET_NAMES",
    "PRESETS",
    "apply_effect",
    "gmic_available",
    "is_available",
]
