"""Sehr einfache Ein-Benutzer-Anmeldung (per Session-Cookie)."""
from fastapi import Request
from fastapi.responses import RedirectResponse
import config


def is_logged_in(request: Request) -> bool:
    return request.session.get("user") == config.APP_USERNAME


def require_login(request: Request):
    """Als Dependency verwenden; leitet bei fehlendem Login zum Login-Formular um."""
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def check_credentials(username: str, password: str) -> bool:
    return username == config.APP_USERNAME and password == config.APP_PASSWORD
