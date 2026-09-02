// Baut die Fotoredaktion-Karte als EINE fertige, selbst-enthaltene HTML-Datei.
// Ersetzt die bisherige Live-Übersetzung im Browser (Babel) durch einen
// echten Build-Schritt: React/ReactDOM/lucide-react werden hier fest
// eingebunden, das Ergebnis ist normales, bereits übersetztes JavaScript.
// Vorteil: die Seite braucht dadurch KEIN 'unsafe-eval' mehr in der
// Content-Security-Policy - genau das hatte am 02.09.2026 den schwarzen
// Bildschirm verursacht, als die CSP verschärft wurde.
const esbuild = require("esbuild");
const fs = require("fs");
const path = require("path");

async function build() {
  const result = await esbuild.build({
    entryPoints: [path.join(__dirname, "app.jsx")],
    bundle: true,
    format: "iife",
    target: ["chrome100", "safari15", "firefox100"],
    minify: true,
    write: false,
    logLevel: "info",
    define: { "process.env.NODE_ENV": '"production"' },
  });

  const bundleJs = result.outputFiles[0].text;

  const html = `<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Fotoredaktion Board</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  html, body { margin: 0; padding: 0; background: #0d0e11; }
  #root { display: flex; justify-content: center; padding: 24px; min-height: 100vh; box-sizing: border-box; }
</style>
</head>
<body>
<div id="root"></div>
<script src="app.js"></script>
</body>
</html>
`;

  const outDir = path.join(__dirname, "..", "sites", "karte");
  fs.writeFileSync(path.join(outDir, "index.html"), html, "utf-8");
  fs.writeFileSync(path.join(outDir, "app.js"), bundleJs, "utf-8");
  console.log("Geschrieben:", outDir, "- index.html (", (html.length / 1024).toFixed(1), "KB ) + app.js (", (bundleJs.length / 1024).toFixed(1), "KB )");
}

build().catch((e) => {
  console.error(e);
  process.exit(1);
});
