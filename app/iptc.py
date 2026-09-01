"""Schreibt IPTC-Metadaten in die JPGs, per exiftool (robust, Industriestandard)."""
import subprocess
import config


def write_iptc(image_path: str, recognized_names: list[str], extra_caption: str = "") -> str:
    """Schreibt Fotograf, Copyright, Keywords und Bildunterschrift.
    Gibt die verwendete Bildunterschrift zurück."""
    caption_parts = []
    if extra_caption:
        caption_parts.append(extra_caption)
    if recognized_names:
        caption_parts.append("Im Bild: " + ", ".join(recognized_names))
    caption = " – ".join(caption_parts)

    # -codedcharacterset=utf8 markiert das IPTC-Feld korrekt als UTF-8, damit Umlaute,
    # Sonderzeichen (©, –, …) nicht als Mojibake gespeichert/angezeigt werden.
    args = ["exiftool", "-overwrite_original", "-codedcharacterset=utf8"]

    if config.PHOTOGRAPHER_NAME:
        args += [f"-IPTC:By-line={config.PHOTOGRAPHER_NAME}", f"-XMP:Creator={config.PHOTOGRAPHER_NAME}"]
    if config.COPYRIGHT_NOTICE:
        args += [
            f"-IPTC:CopyrightNotice={config.COPYRIGHT_NOTICE}",
            f"-XMP:Rights={config.COPYRIGHT_NOTICE}",
        ]
    if config.DEFAULT_CREDIT:
        args += [f"-IPTC:Credit={config.DEFAULT_CREDIT}"]
    if caption:
        args += [f"-IPTC:Caption-Abstract={caption}", f"-XMP:Description={caption}"]
    for name in recognized_names:
        args += [f"-IPTC:Keywords+={name}", f"-XMP:Subject+={name}"]

    args.append(image_path)

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"exiftool fehlgeschlagen: {result.stderr.strip()}")

    return caption
