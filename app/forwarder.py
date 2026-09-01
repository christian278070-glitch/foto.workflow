"""Versand der fertig bearbeiteten Bilder an den FTP-Server der Redaktion."""
import os
import ftplib
import time
import config


class ForwardError(Exception):
    pass


def _connect():
    if config.REDAKTION_FTP_USE_TLS:
        ftp = ftplib.FTP_TLS()
        ftp.connect(config.REDAKTION_FTP_HOST, config.REDAKTION_FTP_PORT, timeout=30)
        ftp.login(config.REDAKTION_FTP_USER, config.REDAKTION_FTP_PASS)
        ftp.prot_p()
    else:
        ftp = ftplib.FTP()
        ftp.connect(config.REDAKTION_FTP_HOST, config.REDAKTION_FTP_PORT, timeout=30)
        ftp.login(config.REDAKTION_FTP_USER, config.REDAKTION_FTP_PASS)
    if config.REDAKTION_FTP_REMOTE_DIR:
        ftp.cwd(config.REDAKTION_FTP_REMOTE_DIR)
    return ftp


def send_file(local_path: str, remote_filename: str, max_retries: int = 3) -> None:
    """Lädt eine Datei per FTP(S) zur Redaktion hoch. Wirft ForwardError bei endgültigem Fehler."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            ftp = _connect()
            try:
                with open(local_path, "rb") as f:
                    ftp.storbinary(f"STOR {remote_filename}", f)
            finally:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 20))
    raise ForwardError(f"Versand an Redaktion fehlgeschlagen nach {max_retries} Versuchen: {last_error}")
