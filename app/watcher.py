"""Hintergrundprozess: erkennt neue Bilder im FTP-Eingang und schickt sie durch
die gesamte Pipeline (Bildkorrektur -> Gesichtserkennung -> IPTC -> Weiterleitung).

Ablauf pro Bild:
  1. eingegangen        - Datei im incoming-Ordner entdeckt
  2. verarbeitung        - Auto-Tonwert/Schärfen + Gesichtserkennung + IPTC laufen
  3. wartet_auf_versand  - fertig bearbeitet, wartet die konfigurierte Verzögerung
                            (Eingriffsfenster über das Dashboard: stoppen/löschen möglich)
  4. gesendet            - erfolgreich an die Redaktion übertragen
  5. fehler              - Verarbeitung oder Versand ist fehlgeschlagen
  6. manuell_gestoppt    - im Dashboard gestoppt, wird NICHT an die Redaktion gesendet
"""
import os
import time
import shutil
import logging
import threading

import config
import db
import pipeline
import faces
import iptc
import forwarder

log = logging.getLogger("watcher")

# Bild-IDs, die im Dashboard gestoppt wurden, bevor sie versendet wurden
_stopped_job_ids = set()
_stop_lock = threading.Lock()


def stop_job(job_id: int):
    with _stop_lock:
        _stopped_job_ids.add(job_id)


def _is_stopped(job_id: int) -> bool:
    with _stop_lock:
        return job_id in _stopped_job_ids


def _ensure_dirs():
    for d in (
        config.INCOMING_DIR,
        config.PROCESSING_DIR,
        config.ARCHIVE_ORIGINALS_DIR,
        config.ARCHIVE_PROCESSED_DIR,
        config.REVIEW_DIR,
        config.FAILED_DIR,
        config.KNOWN_FACES_DIR,
    ):
        os.makedirs(d, exist_ok=True)


def _is_file_stable(path: str, wait: float = 1.0) -> bool:
    """Prüft, ob die Datei fertig hochgeladen ist (Größe ändert sich nicht mehr)."""
    try:
        size1 = os.path.getsize(path)
        time.sleep(wait)
        size2 = os.path.getsize(path)
        return size1 == size2 and size1 > 0
    except FileNotFoundError:
        return False


def _make_thumb(src_path: str, thumb_path: str, max_size=(480, 480)):
    from PIL import Image
    with Image.open(src_path) as img:
        img = img.convert("RGB")
        img.thumbnail(max_size)
        img.save(thumb_path, format="JPEG", quality=80)


def _handle_new_file(filename: str):
    src_path = os.path.join(config.INCOMING_DIR, filename)
    if not filename.lower().endswith((".jpg", ".jpeg")):
        return  # nur JPGs interessieren uns (Canon R1 liefert unbearbeitete JPGs)
    if not _is_file_stable(src_path):
        return  # Upload läuft noch, beim nächsten Durchlauf erneut prüfen

    job_id = db.create_job(filename)
    log.info("Neues Bild erkannt: %s (Job %s)", filename, job_id)

    processing_path = os.path.join(config.PROCESSING_DIR, f"{job_id}_{filename}")
    try:
        shutil.move(src_path, processing_path)
    except Exception as exc:
        db.update_job(job_id, status="fehler", error=f"Konnte Datei nicht verschieben: {exc}")
        return

    db.update_job(job_id, status="verarbeitung")

    # Original fürs Archiv sichern, bevor wir es verändern
    original_backup = os.path.join(config.ARCHIVE_ORIGINALS_DIR, f"{job_id}_{filename}")
    try:
        shutil.copy2(processing_path, original_backup)
    except Exception:
        pass

    processed_path = os.path.join(config.PROCESSING_DIR, f"{job_id}_bearbeitet_{filename}")
    try:
        pipeline.process_image(processing_path, processed_path)
        recognized = []
        try:
            recognized = faces.recognize_faces(processed_path)
        except Exception as exc:
            log.warning("Gesichtserkennung fehlgeschlagen für Job %s: %s", job_id, exc)
        caption = iptc.write_iptc(processed_path, recognized)

        thumb_path = os.path.join(config.PROCESSING_DIR, f"{job_id}_thumb.jpg")
        _make_thumb(processed_path, thumb_path)

        forward_at = time.time() + config.AUTO_FORWARD_DELAY_SECONDS
        db.update_job(
            job_id,
            status="wartet_auf_versand",
            processed_at=time.time(),
            forward_at=forward_at,
            recognized_names=", ".join(recognized),
            caption=caption,
            thumb_path=thumb_path,
        )
    except Exception as exc:
        log.exception("Verarbeitung fehlgeschlagen für Job %s", job_id)
        failed_path = os.path.join(config.FAILED_DIR, f"{job_id}_{filename}")
        try:
            shutil.move(processing_path, failed_path)
        except Exception:
            pass
        db.update_job(job_id, status="fehler", error=str(exc))


def _process_forward_queue():
    now = time.time()
    for job in db.list_pending_forward():
        job_id = job["id"]

        if _is_stopped(job_id):
            _move_to_review(job)
            db.update_job(job_id, status="manuell_gestoppt")
            continue

        if db.is_automation_paused():
            _move_to_review(job)
            continue  # bleibt in Review, bis Automatik fortgesetzt oder manuell gesendet wird

        if job["forward_at"] and now < job["forward_at"]:
            continue  # Eingriffsfenster läuft noch

        _do_forward(job)


def _find_processed_path(job) -> str | None:
    filename = job["filename"]
    job_id = job["id"]
    candidate = os.path.join(config.PROCESSING_DIR, f"{job_id}_bearbeitet_{filename}")
    if os.path.exists(candidate):
        return candidate
    candidate = os.path.join(config.REVIEW_DIR, f"{job_id}_bearbeitet_{filename}")
    if os.path.exists(candidate):
        return candidate
    return None


def _move_to_review(job):
    """Verschiebt ein fertiges Bild in den Review-Ordner, damit es bei einem
    Container-Neustart nicht verloren geht, während es auf Freigabe wartet."""
    processed_path = _find_processed_path(job)
    if not processed_path or not processed_path.startswith(config.PROCESSING_DIR):
        return
    target = os.path.join(config.REVIEW_DIR, os.path.basename(processed_path))
    try:
        shutil.move(processed_path, target)
    except Exception:
        pass


def _do_forward(job):
    job_id = job["id"]
    processed_path = _find_processed_path(job)
    if not processed_path:
        db.update_job(job_id, status="fehler", error="Bearbeitete Datei nicht gefunden")
        return
    try:
        forwarder.send_file(processed_path, job["filename"])
        archive_path = os.path.join(config.ARCHIVE_PROCESSED_DIR, os.path.basename(processed_path))
        shutil.move(processed_path, archive_path)
        db.update_job(job_id, status="gesendet", sent_at=time.time())
        log.info("Job %s an Redaktion gesendet: %s", job_id, job["filename"])
    except forwarder.ForwardError as exc:
        db.update_job(job_id, status="fehler", error=str(exc))
        log.error("Versand fehlgeschlagen für Job %s: %s", job_id, exc)


def retry_job(job_id: int):
    """Manuelles Erneut-Versuchen aus dem Dashboard (z.B. nach FTP-Problem)."""
    job = db.get_job(job_id)
    if not job:
        return
    db.update_job(job_id, status="wartet_auf_versand", forward_at=time.time(), error="")
    with _stop_lock:
        _stopped_job_ids.discard(job_id)


def send_now(job_id: int):
    """Sofort senden, ohne auf die Verzögerung zu warten."""
    db.update_job(job_id, forward_at=time.time() - 1)


def run_forever():
    _ensure_dirs()
    log.info("Watcher gestartet, beobachte %s", config.INCOMING_DIR)
    while True:
        try:
            if os.path.isdir(config.INCOMING_DIR):
                for filename in sorted(os.listdir(config.INCOMING_DIR)):
                    _handle_new_file(filename)
            _process_forward_queue()
        except Exception:
            log.exception("Fehler in der Watcher-Schleife")
        time.sleep(config.WATCH_POLL_INTERVAL_SECONDS)


def start_background_thread():
    thread = threading.Thread(target=run_forever, daemon=True)
    thread.start()
    return thread
