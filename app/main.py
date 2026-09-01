"""Web-Dashboard: Login, Live-Status der Bilder, Eingriffsmöglichkeiten,
Verwaltung der bekannten Gesichter. Läuft im selben Prozess wie der Watcher
(als Hintergrund-Thread), damit beide dieselbe SQLite-DB nutzen können."""
import os
import logging

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
import db
import auth
import watcher
import faces

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Foto-Workflow Dashboard")
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, same_site="lax")

BASE_DIR = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.on_event("startup")
def on_startup():
    db.init_db(db.conn())
    watcher.start_background_thread()


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if auth.check_credentials(username, password):
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Benutzername oder Passwort falsch"}
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
def _job_to_dict(job):
    return {
        "id": job["id"],
        "filename": job["filename"],
        "status": job["status"],
        "recognized_names": job["recognized_names"],
        "caption": job["caption"],
        "error": job["error"],
        "created_at": job["created_at"],
        "forward_at": job["forward_at"],
        "sent_at": job["sent_at"],
        "has_thumb": bool(job["thumb_path"] and os.path.exists(job["thumb_path"])),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    jobs = [_job_to_dict(j) for j in db.list_jobs()]
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "jobs": jobs,
            "automation_paused": db.is_automation_paused(),
        },
    )


@app.get("/api/jobs")
def api_jobs(request: Request):
    redirect = auth.require_login(request)
    if redirect:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    jobs = [_job_to_dict(j) for j in db.list_jobs()]
    return {"jobs": jobs, "automation_paused": db.is_automation_paused()}


@app.get("/thumb/{job_id}")
def thumb(request: Request, job_id: int):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    job = db.get_job(job_id)
    if not job or not job["thumb_path"] or not os.path.exists(job["thumb_path"]):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(job["thumb_path"])


@app.post("/automation/toggle")
def toggle_automation(request: Request):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    db.set_setting("automation_paused", "0" if db.is_automation_paused() else "1")
    return RedirectResponse(url="/", status_code=303)


@app.post("/jobs/{job_id}/stop")
def job_stop(request: Request, job_id: int):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    watcher.stop_job(job_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/jobs/{job_id}/send_now")
def job_send_now(request: Request, job_id: int):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    watcher.send_now(job_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/jobs/{job_id}/retry")
def job_retry(request: Request, job_id: int):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    watcher.retry_job(job_id)
    return RedirectResponse(url="/", status_code=303)


# --------------------------------------------------------------------------
# Bekannte Gesichter verwalten
# --------------------------------------------------------------------------
@app.get("/known-faces", response_class=HTMLResponse)
def known_faces_page(request: Request):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    people = []
    for name in faces.list_known_people():
        person_dir = os.path.join(config.KNOWN_FACES_DIR, name)
        photo_count = len([f for f in os.listdir(person_dir) if os.path.isfile(os.path.join(person_dir, f))])
        people.append({"name": name, "photo_count": photo_count})
    return templates.TemplateResponse("known_faces.html", {"request": request, "people": people})


@app.post("/known-faces/add")
async def known_faces_add(request: Request, person_name: str = Form(...), photo: UploadFile = File(...)):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    content = await photo.read()
    faces.add_known_face(person_name.strip(), content, photo.filename)
    return RedirectResponse(url="/known-faces", status_code=303)


@app.post("/known-faces/delete")
def known_faces_delete(request: Request, person_name: str = Form(...)):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    faces.delete_known_person(person_name)
    return RedirectResponse(url="/known-faces", status_code=303)
