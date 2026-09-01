# Foto-Workflow-Server

Automatischer Zwischenserver für deinen Workflow:

**Canon R1 (mobiler Hotspot) → dieser Server → automatische Bildkorrektur + Beschriftung + Gesichtserkennung → Redaktions-FTP**

Dashboard zur Überwachung/Eingriff, mobil nutzbar (z.B. im iPhone-Browser).

---

## 1. Überblick über die Bausteine

| Baustein | Was er tut |
|---|---|
| `ftp`-Container | Nimmt die JPGs von der Canon R1 per FTP entgegen |
| `app`-Container | Erkennt neue Bilder, führt Auto-Tonwert + Schärfen aus, erkennt bekannte Gesichter, schreibt IPTC-Metadaten, sendet an die Redaktion, betreibt das Web-Dashboard |
| `caddy`-Container | Automatisches HTTPS-Zertifikat + Reverse Proxy fürs Dashboard |

Alle drei laufen über `docker compose` auf einem einzigen VPS.

---

## 2. Empfohlener Server (VPS)

Empfehlung: **Hetzner Cloud, Typ CPX32** (4 vCPU, 8 GB RAM, 160 GB NVMe-SSD, AMD EPYC, geteilte vCPUs),
Stand August 2026 ca. **35,49 €/Monat**, Rechenzentrum z.B. Nürnberg oder Falkenstein.
Das reicht für die Bildbearbeitung und die Gesichtserkennung bei normalem Aufkommen
(einzelne Fotos, keine Videoserie) gut aus.

Falls die Gesichtserkennung bei sehr vielen gleichzeitigen Bildern (z.B. Sport-Serienbilder)
spürbar hinterherhinkt, kannst du jederzeit ohne Neuinstallation auf **CPX42**
(8 vCPU, 16 GB RAM, ca. 69,49 €/Monat) hochskalieren ("Resize" in der Hetzner-Konsole).

Betriebssystem: Ubuntu 24.04 LTS.

Quellen zur Preisrecherche:
- [Hetzner Cloud – Regular Performance (CPX-Reihe)](https://www.hetzner.com/cloud/regular-performance/)
- [Hetzner Cloud Pricing Calculator (Aug 2026)](https://costgoat.com/pricing/hetzner)

*(Alternativ funktioniert jeder andere VPS-Anbieter mit Docker-Unterstützung, z.B. IONOS oder
Netcup – Hetzner ist wegen Preis-Leistung und deutschen Rechenzentren die naheliegendste Wahl.)*

---

## 3. Server einrichten

### 3.1 VPS anlegen
1. Bei Hetzner Cloud registrieren, neues Projekt anlegen.
2. Server erstellen: Ubuntu 24.04, Typ CPX32, SSH-Key hinterlegen.
3. **Cloud-Firewall** anlegen und dem Server zuweisen, folgende Ports öffnen:
   - `21/tcp` (FTP-Kontrollport, für die Kamera)
   - `30000-30009/tcp` (FTP Passive-Mode-Ports, für die Kamera)
   - `80/tcp` und `443/tcp` (Dashboard/HTTPS)
   - `22/tcp` nur von deiner eigenen IP aus (SSH-Zugriff für dich)

### 3.2 Domain
Lege eine Subdomain an (z.B. `foto.deine-domain.de`) und zeige per **A-Record** auf die
öffentliche IPv4-Adresse des VPS. Caddy holt sich darüber automatisch ein gültiges
HTTPS-Zertifikat (Let's Encrypt) – dadurch funktioniert das Dashboard sauber im iPhone-Browser.

### 3.3 Docker installieren
Auf dem Server per SSH:
```bash
curl -fsSL https://get.docker.com | sh
```

### 3.4 Projekt hochladen
Dieses Projektverzeichnis z.B. per `scp` auf den Server kopieren:
```bash
scp -r foto-workflow root@DEINE-SERVER-IP:/opt/foto-workflow
```

### 3.5 Konfiguration
```bash
cd /opt/foto-workflow
cp .env.example .env
nano .env
```
Trage ein:
- `VPS_PUBLIC_IP` – die öffentliche IP deines Servers (wichtig für FTP Passive Mode!)
- `DASHBOARD_DOMAIN` – deine Subdomain
- `CAMERA_FTP_USER` / `CAMERA_FTP_PASS` – frei wählbare Zugangsdaten für die Kamera
- `APP_USERNAME` / `APP_PASSWORD` – dein Login fürs Dashboard
- `SESSION_SECRET` – ein langer Zufallsstring, z.B. erzeugt mit `openssl rand -hex 32`
- `REDAKTION_FTP_*` – die Zugangsdaten, die ihr bisher direkt in der Kamera verwendet habt
- `PHOTOGRAPHER_NAME`, `COPYRIGHT_NOTICE`, `DEFAULT_CREDIT` – für die IPTC-Beschriftung

### 3.6 Starten
```bash
docker compose up -d --build
```
**Hinweis:** Der erste Build kompiliert `dlib` (Gesichtserkennung) und dauert ca. 10–20 Minuten.
Mit `docker compose logs -f app` kannst du den Fortschritt/Fehler verfolgen.

---

## 4. Canon R1 – FTP-Einstellungen an der Kamera

In den Netzwerkeinstellungen der Kamera (FTP-Übertragung):
- **Server:** deine `VPS_PUBLIC_IP` (oder die Domain)
- **Port:** 21
- **Modus:** Passiv (PASV)
- **Benutzername/Passwort:** wie in `.env` unter `CAMERA_FTP_USER`/`CAMERA_FTP_PASS`
- **Zielordner:** leer lassen / Hauptverzeichnis
- Dateityp: JPEG (wie bisher)

Damit landen die Bilder jetzt bei dir auf dem Zwischenserver statt direkt bei der Redaktion.

---

## 5. Bekannte Gesichter pflegen

Unter `https://DEINE-DOMAIN/known-faces` im Dashboard:
1. Name eingeben, ein gut erkennbares Referenzfoto der Person hochladen (Frontal, gute Beleuchtung).
   Mehrere Fotos pro Person (verschiedene Blickwinkel) verbessern die Trefferquote.
2. Wird die Person auf einem neuen Foto erkannt, wird ihr Name automatisch in die
   IPTC-Bildunterschrift und die Keywords eingetragen.

**Datenschutz-Hinweis:** Die automatische Zuordnung von Namen zu Gesichtern ist rechtlich die
Verarbeitung biometrischer Daten (Art. 9 DSGVO). Bei bekannten Personen des öffentlichen Lebens
im Rahmen der journalistischen Tätigkeit greift in der Regel das Medienprivileg, dennoch lohnt
sich eine kurze Abstimmung mit eurem Datenschutzbeauftragten – insbesondere falls auch nicht
öffentlich bekannte Personen erkannt werden sollen. Das ist keine Rechtsberatung, nur ein Hinweis,
das vorab zu klären.

---

## 6. Der Workflow im Detail

1. Kamera lädt JPG per FTP hoch.
2. Sobald die Datei vollständig ist, wird sie erkannt ("Eingegangen").
3. Automatische Bearbeitung: Auto-Tonwert (Kontraststreckung je Kanal), leichte
   Sättigungsanhebung, Schärfen (Unsharp Mask). Aufnahmedatum/Kameradaten (EXIF) bleiben erhalten.
4. Gesichtserkennung gegen deine Referenzdatenbank.
5. IPTC-Metadaten werden geschrieben (Fotograf, Copyright, Bildunterschrift, erkannte Personen).
6. Das Bild wartet die in `.env` eingestellte Zeit (`AUTO_FORWARD_DELAY_SECONDS`, Standard 8 Sekunden)
   – in dieser Zeit kannst du im Dashboard **"Stoppen"** drücken, falls z.B. ein Fehlschuss dabei ist.
7. Danach wird automatisch an den Redaktions-FTP gesendet ("Gesendet ✓").

Über den Button **"Automatik pausieren"** im Dashboard kannst du jederzeit auf manuelle Freigabe
umschalten: Bilder werden weiter bearbeitet, aber erst nach deinem Klick auf "Jetzt senden"
tatsächlich verschickt.

Originale und bearbeitete Bilder werden zusätzlich auf dem Server archiviert
(`/data/archive/originals` bzw. `/data/archive/processed` im `app`-Container) – nützlich als
Backup, falls bei der Redaktion mal etwas verloren geht.

---

## 7. Testen, bevor du live gehst

1. Ein Testfoto direkt per FTP-Programm (z.B. FileZilla) mit den Kamera-Zugangsdaten an den
   Server schicken und im Dashboard beobachten, ob es durch alle Status-Schritte läuft.
2. Ein Referenzgesicht hinterlegen und mit einem Foto dieser Person testen.
3. Die Redaktions-FTP-Zugangsdaten mit einem Testbild verifizieren (kommt es dort korrekt an?).
4. Erst danach die Kamera selbst auf den neuen Server umstellen.

---

## 8. Offene Punkte / sinnvolle nächste Schritte

- **Sicherheit der Kamera-Verbindung:** Plain-FTP überträgt Zugangsdaten und Bilder unverschlüsselt
  über das mobile Netz – das war beim bisherigen Direktversand an die Redaktion vermutlich genauso.
  Falls die Canon R1 FTPS (FTP über TLS) unterstützt, ist das ein sinnvolles Upgrade; sag Bescheid,
  dann bauen wir das nach.
- **Backups:** Die Docker-Volumes (v.a. `archive`, `known_faces`) sollten regelmäßig gesichert
  werden, z.B. über ein Hetzner-Snapshot oder ein Backup-Skript (`restic`/`rsync`) auf einen
  zweiten Speicherort.
- **Benachrichtigungen bei Fehlern:** aktuell siehst du Fehler nur im Dashboard. Auf Wunsch bauen
  wir eine Push-/E-Mail-Benachrichtigung bei fehlgeschlagenem Versand.
- **Praxistest ausstehend:** Dieses Setup ist fertig gebaut, aber noch nicht auf einem echten
  Server mit echten Redaktions-Zugangsdaten getestet. Nach dem ersten Testlauf schauen wir uns am
  besten gemeinsam die Logs an (`docker compose logs -f app`) und feilen an Details
  (z.B. Bearbeitungsstärke, Formulierung der Bildunterschrift, Timing der Verzögerung).
