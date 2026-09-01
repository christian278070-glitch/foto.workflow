"""Zentrale Konfiguration, gelesen aus Umgebungsvariablen (.env)."""
import os


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# --- Pfade (entsprechen den Volumes in docker-compose.yml) ---
# Die Kamera loggt sich per FTP direkt im Home-Verzeichnis des FTP-Users ein
# und lädt dort hoch (kein Unterordner nötig) - dasselbe Volume wird hier
# schreibgeschützt für den Watcher eingehängt.
INCOMING_DIR = "/data/incoming"
PROCESSING_DIR = "/data/processing"
ARCHIVE_ORIGINALS_DIR = "/data/archive/originals"
ARCHIVE_PROCESSED_DIR = "/data/archive/processed"
REVIEW_DIR = "/data/review"
FAILED_DIR = "/data/failed"
KNOWN_FACES_DIR = "/data/known_faces"
DB_PATH = "/data/db/workflow.sqlite3"

# --- App / Login ---
APP_USERNAME = os.environ.get("APP_USERNAME", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "changeme")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "insecure-default-change-me")

# --- Redaktions-FTP (Ziel) ---
REDAKTION_FTP_HOST = os.environ.get("REDAKTION_FTP_HOST", "")
REDAKTION_FTP_PORT = int(os.environ.get("REDAKTION_FTP_PORT", "21"))
REDAKTION_FTP_USER = os.environ.get("REDAKTION_FTP_USER", "")
REDAKTION_FTP_PASS = os.environ.get("REDAKTION_FTP_PASS", "")
REDAKTION_FTP_USE_TLS = _bool("REDAKTION_FTP_USE_TLS", False)
REDAKTION_FTP_REMOTE_DIR = os.environ.get("REDAKTION_FTP_REMOTE_DIR", "")

# --- IPTC ---
PHOTOGRAPHER_NAME = os.environ.get("PHOTOGRAPHER_NAME", "")
COPYRIGHT_NOTICE = os.environ.get("COPYRIGHT_NOTICE", "")
DEFAULT_CREDIT = os.environ.get("DEFAULT_CREDIT", "")

# --- Workflow-Verhalten ---
AUTO_FORWARD_DELAY_SECONDS = int(os.environ.get("AUTO_FORWARD_DELAY_SECONDS", "8"))
FACE_RECOGNITION_ENABLED = _bool("FACE_RECOGNITION_ENABLED", True)
FACE_MATCH_TOLERANCE = float(os.environ.get("FACE_MATCH_TOLERANCE", "0.5"))

WATCH_POLL_INTERVAL_SECONDS = 2
