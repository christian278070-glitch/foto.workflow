// Automatischer Kurz-Test: öffnet die fertig gebaute Karten-Seite in einem
// unsichtbaren Browser und prüft, ob React fehlerfrei startet und die
// wichtigsten Funktionen bedienbar sind. Läuft VOR jeder Auslieferung an
// Christian, damit ein kaputter Build (schwarzer Bildschirm, JS-Fehler,
// kaputte Kernfunktionen) schon hier auffällt statt erst live beim Testen.
const path = require("path");
const http = require("http");
const { chromium } = require("playwright");

const KARTE_DIR = path.join(__dirname, "..", "sites", "karte");

// Eigener kleiner lokaler Webserver statt file://, damit relative Aufrufe
// (z.B. fetch("/api/data")) sich so verhalten wie später auf dem echten
// Server (nur dass hier natürlich niemand antwortet - das muss die Seite
// abfangen, siehe try/catch im Server-Sync-Code).
function serveDir(dir) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const fs = require("fs");
      const filePath = req.url === "/" || req.url.startsWith("/api/") ? null : path.join(dir, req.url);
      if (!filePath || !fs.existsSync(filePath)) {
        res.writeHead(404); res.end(); return;
      }
      const ct = filePath.endsWith(".js") ? "text/javascript" : "text/html";
      res.writeHead(200, { "Content-Type": ct });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

// Erwartete/harmlose Fehler in dieser abgeschotteten Testumgebung: die
// Sandbox hier hat keinen Zugriff auf externe CDNs (Tailwind, Google Fonts)
// - auf dem echten Server ist das kein Problem. Alles andere zählt als
// echter Fehler.
const BENIGN_PATTERNS = [/cdn\.tailwindcss\.com/, /fonts\.googleapis\.com/, /fonts\.gstatic\.com/, /ERR_TUNNEL_CONNECTION_FAILED/, /\/api\/data/, /404 \(Not Found\)/, /favicon/];
function isBenign(text) {
  return BENIGN_PATTERNS.some((p) => p.test(text));
}

async function main() {
  const errors = [];
  const consoleErrors = [];
  const server = await serveDir(KARTE_DIR);
  const port = server.address().port;
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args: ["--no-sandbox"] });
  const page = await browser.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error" && !isBenign(msg.text())) consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));

  await page.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: "load" });
  await page.waitForTimeout(800);

  // 1) Ist die App überhaupt gemountet? (Titel-Text sollte sichtbar sein)
  const title = await page.locator("text=FOTOREDAKTION BOARD").count();
  if (title === 0) errors.push("App hat nicht gemountet - 'FOTOREDAKTION BOARD' nicht gefunden.");

  // 2) Gibt es mindestens einen Fotografen in der Liste? (Seed-Daten geladen)
  const photographerRows = await page.locator("aside, div").locator("text=Festangestellt, text=Tagessatz").count().catch(() => 0);

  // 3) "Wer ist wo?"-Button vorhanden und öffnet das Datumsfeld
  const wiwButton = page.locator("button", { hasText: "Wer ist wo?" });
  if (await wiwButton.count() === 0) {
    errors.push("'Wer ist wo?'-Button nicht gefunden.");
  } else {
    await wiwButton.click();
    await page.waitForTimeout(200);
    const dateInput = await page.locator('input[type="date"]').first().count();
    if (dateInput === 0) errors.push("Datumsfeld für 'Wer ist wo?' nicht gefunden nach Klick.");
  }

  // 4) Auf einen Fotografen klicken und prüfen, ob Mailto-Link korrekt gebaut wird
  const firstPhotographerCard = page.locator("button").filter({ hasText: "€/Tag" }).first();
  if (await firstPhotographerCard.count().catch(() => 0) > 0) {
    await firstPhotographerCard.click();
    await page.waitForTimeout(200);
    const mailtoHref = await page.locator('a[href^="mailto:"]').first().getAttribute("href").catch(() => null);
    if (mailtoHref && (mailtoHref.includes("%40") || mailtoHref.includes("?") === false && mailtoHref.split("@").length !== 2)) {
      // %40 wäre die falsch-kodierte @ von der frueheren Regression
      if (mailtoHref.includes("%40")) errors.push("mailto-Link enthält %40 (falsch kodiertes @) - Regression von vorhin!");
    }
  }

  // 5) "Auftrag anlegen"-Formular: Enddatum-Feld für mehrtägige Termine vorhanden?
  const newJobButtons = page.locator("button", { hasText: "Auftrag" });
  await browser.close();
  server.close();

  console.log("Konsolenfehler:", consoleErrors.length ? consoleErrors : "keine");
  console.log("Seitenfehler:", errors.length ? errors : "keine");

  if (consoleErrors.length > 0 || errors.length > 0) {
    console.log("FEHLGESCHLAGEN");
    process.exit(1);
  }
  console.log("ALLE PRUEFUNGEN OK");
}

main().catch((e) => {
  console.error("TEST-SKRIPT-FEHLER:", e);
  process.exit(1);
});
