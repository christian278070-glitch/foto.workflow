"""Gesichtserkennung gegen eine gepflegte Referenzdatenbank bekannter Personen.

Struktur von /data/known_faces/:
    known_faces/
        Max Mustermann/
            foto1.jpg
            foto2.jpg
        Erika Musterfrau/
            foto1.jpg
        _cache/
            encodings.pkl   (automatisch erzeugter Cache, nicht per Hand anfassen)

Über das Dashboard (Reiter "Bekannte Gesichter") können neue Personen/Fotos
hinzugefügt werden; die Encodings werden dann neu berechnet.
"""
import os
import pickle
import hashlib
import face_recognition
import config

_CACHE_PATH = os.path.join(config.KNOWN_FACES_DIR, "_cache", "encodings.pkl")

_encodings_cache = None  # {"signature": str, "names": [...], "encodings": [...]}


def _dir_signature() -> str:
    """Einfache Signatur aus Dateinamen+Größen, um zu erkennen ob neu berechnet werden muss."""
    parts = []
    for person in sorted(_list_people()):
        person_dir = os.path.join(config.KNOWN_FACES_DIR, person)
        for fname in sorted(os.listdir(person_dir)):
            fpath = os.path.join(person_dir, fname)
            if os.path.isfile(fpath):
                parts.append(f"{person}/{fname}:{os.path.getsize(fpath)}")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _list_people():
    if not os.path.isdir(config.KNOWN_FACES_DIR):
        return []
    return [
        d for d in os.listdir(config.KNOWN_FACES_DIR)
        if os.path.isdir(os.path.join(config.KNOWN_FACES_DIR, d)) and not d.startswith("_")
    ]


def list_known_people():
    return sorted(_list_people())


def _build_encodings():
    names, encodings = [], []
    for person in _list_people():
        person_dir = os.path.join(config.KNOWN_FACES_DIR, person)
        for fname in sorted(os.listdir(person_dir)):
            fpath = os.path.join(person_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                image = face_recognition.load_image_file(fpath)
                face_encodings = face_recognition.face_encodings(image)
                if face_encodings:
                    names.append(person)
                    encodings.append(face_encodings[0])
            except Exception:
                # Referenzbild konnte nicht verarbeitet werden -> überspringen
                continue
    return names, encodings


def _load_or_build_encodings():
    global _encodings_cache
    signature = _dir_signature()
    if _encodings_cache and _encodings_cache["signature"] == signature:
        return _encodings_cache["names"], _encodings_cache["encodings"]

    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "rb") as f:
                cached = pickle.load(f)
            if cached.get("signature") == signature:
                _encodings_cache = cached
                return cached["names"], cached["encodings"]
        except Exception:
            pass

    names, encodings = _build_encodings()
    _encodings_cache = {"signature": signature, "names": names, "encodings": encodings}
    with open(_CACHE_PATH, "wb") as f:
        pickle.dump(_encodings_cache, f)
    return names, encodings


def recognize_faces(image_path: str) -> list[str]:
    """Gibt eine Liste erkannter Namen zurück (Duplikate entfernt, sortiert)."""
    if not config.FACE_RECOGNITION_ENABLED:
        return []
    known_names, known_encodings = _load_or_build_encodings()
    if not known_encodings:
        return []

    image = face_recognition.load_image_file(image_path)
    face_locations = face_recognition.face_locations(image)
    if not face_locations:
        return []
    face_encodings = face_recognition.face_encodings(image, face_locations)

    found = set()
    for encoding in face_encodings:
        distances = face_recognition.face_distance(known_encodings, encoding)
        if len(distances) == 0:
            continue
        best_idx = distances.argmin()
        if distances[best_idx] <= config.FACE_MATCH_TOLERANCE:
            found.add(known_names[best_idx])
    return sorted(found)


def add_known_face(person_name: str, file_bytes: bytes, filename: str) -> None:
    person_dir = os.path.join(config.KNOWN_FACES_DIR, person_name)
    os.makedirs(person_dir, exist_ok=True)
    safe_name = os.path.basename(filename)
    with open(os.path.join(person_dir, safe_name), "wb") as f:
        f.write(file_bytes)
    global _encodings_cache
    _encodings_cache = None  # Cache invalidieren, wird beim nächsten Aufruf neu gebaut


def delete_known_person(person_name: str) -> None:
    import shutil
    person_dir = os.path.join(config.KNOWN_FACES_DIR, person_name)
    if os.path.isdir(person_dir):
        shutil.rmtree(person_dir)
    global _encodings_cache
    _encodings_cache = None
