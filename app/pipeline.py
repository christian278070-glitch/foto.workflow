"""Automatische Bildkorrektur: Auto-Tonwert (Kontrast/Weißabgleich) + Schärfen.

Arbeitet bewusst mit robusten, schnellen Standardverfahren (kein RAW-Develop,
da die Kamera bereits JPGs liefert):
  1. Auto-Tonwert: Kontraststreckung pro Kanal (angelehnt an "Auto-Tonwert" in
     Lightroom/Photoshop), mit kleinem Cutoff gegen Ausreißer-Pixel.
  2. Leichte Sättigungsanhebung, da Kontraststreckung Bilder oft etwas matt macht.
  3. Unscharf-Maskieren (Unsharp Mask) zum Schärfen.
"""
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import piexif


def auto_tone(img: Image.Image, cutoff: float = 0.5) -> Image.Image:
    """Kontraststreckung pro Kanal (RGB), cutoff in Prozent pro Seite des Histogramms."""
    rgb = img.convert("RGB")
    return ImageOps.autocontrast(rgb, cutoff=cutoff)


def boost_saturation(img: Image.Image, factor: float = 1.08) -> Image.Image:
    return ImageEnhance.Color(img).enhance(factor)


def sharpen(img: Image.Image, radius: float = 1.4, percent: int = 130, threshold: int = 3) -> Image.Image:
    return img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))


def _prepare_exif_bytes(img: Image.Image) -> bytes | None:
    """Übernimmt die Original-EXIF-Daten (Aufnahmezeit, Kameramodell etc.),
    setzt aber den Orientation-Tag auf 1 zurück, da exif_transpose() die
    Drehung bereits fest in die Pixel eingebacken hat (sonst würde manche
    Software das Bild ein zweites Mal drehen)."""
    raw_exif = img.info.get("exif")
    if not raw_exif:
        return None
    try:
        exif_dict = piexif.load(raw_exif)
        exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
        return piexif.dump(exif_dict)
    except Exception:
        return None


def process_image(input_path: str, output_path: str) -> None:
    """Lädt ein JPG, wendet Auto-Tonwert + Schärfen an und speichert es (verlustarm),
    unter Beibehaltung der Original-EXIF-Daten (Aufnahmedatum, Kameramodell etc.)."""
    with Image.open(input_path) as original:
        exif_bytes = _prepare_exif_bytes(original)
        # EXIF-Ausrichtung korrekt anwenden, bevor weiterverarbeitet wird
        img = ImageOps.exif_transpose(original)
        img = auto_tone(img)
        img = boost_saturation(img)
        img = sharpen(img)
        save_kwargs = {"format": "JPEG", "quality": 92, "optimize": True}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        img.save(output_path, **save_kwargs)
