# CLAUDE.md

Hinweise für Claude Code (claude.ai/code) zur Arbeit in diesem Repository.

## Projekt

**Lyrics-Liste** — eine PWA zum Anzeigen und Drucken von Liedtexten für die
Familienandachten einer Familie (privater Gebrauch).

Kernidee: Die App ist **ein reiner Viewer und beim Aufruf leer**. Lieder kommen
ausschließlich über eine Import-Datei, die der Besitzer auf seinem Mac mit einem
Claude-Prompt erstellt (Vorlage: `lieder-prompt.md`) und an die Familie schickt.
Ein Import **ersetzt** alle vorhandenen Daten. In der App gibt es kein Anlegen,
Bearbeiten, Online-Suchen oder Teilen/Exportieren von Liedern — bewusst so, aus
rechtlichen Gründen. Solche Funktionen nicht wieder einbauen.

## Architektur

**Eine einzige Datei:** `index.html` enthält die gesamte App (React via
Babel-Standalone über CDN, kein Build-Schritt, kein npm).

**Offline / PWA:**
- `sw.js` — Service Worker. Cacht App-Shell und die CDN-Bibliotheken beim Install.
  Eigene Dateien: Netz zuerst, offline aus dem Cache. CDN: Cache zuerst.
  **Wenn die CDN-Versionen in `index.html` geändert werden:** `CDN_ASSETS` in
  `sw.js` anpassen und `CACHE` hochzählen (`lyrics-liste-v2`, …).
- `manifest.webmanifest` + `icons/` — Installierbarkeit (Homescreen)

**Import-Datei** (`type: "lyrics-liste-sammlung"`, `version: 2`):
`{type, version, created, lists:[{id, name, songIds}], songs:[{id, title, writers,
performer, year, lyrics}]}` — `lists` optional. Format-Spezifikation für Claude
steht in `lieder-prompt.md`; bei Formatänderungen beide Stellen anpassen.

**Lieder-Sammlung pflegen (auf dem Mac):**
- `tools/lieder.py` — CLI für `privat/familien-lieder.json`: Text aus der
  Zwischenablage formatieren und speichern, Angaben/Listen ändern, Vorschau,
  Export nach `privat/versand/`. Gibt bewusst nie Songtexte aus.
- Skills `/lied-hinzufuegen` und `/lieder-verschicken` (`.claude/skills/`) nutzen
  das Skript. Versand per WhatsApp wird nur vorbereitet, gesendet wird vom Nutzer.
- `lieder-prompt.md` — Alternative für ein Claude-Projekt in der Claude-App.

**Daten:**
- `localStorage` `lyrics-sammlung` — die zuletzt importierte Sammlung:
  `{created, importedAt, lists:[...], songs:{ [id]: {...} }}`
- Alte Schlüssel `lyrics-lists` / `lyrics-songs` (v1) werden beim Import bzw.
  beim Entfernen gelöscht.

**React-Komponenten (in index.html):**
- `App` — verwaltet `phase` (`home`, `list`, `song`, `print`), `collection`, Import
- `HomeView` — „Alle Lieder" + Listen, Import-Button, alles entfernen, Stand-Datum
- `ListView` — Lieder einer Liste (alphabetisch), nur lesen
- `SongView` / `SongMeta` — Liedtext mit Titel, Interpret · Jahr, Songwriter
- `PrintView` — Druckansicht der ganzen Liste

## Copyright / CCLI

Songtexte christlicher Lieder sind urheberrechtlich geschützt. Die App liefert bewusst
**keine Texte mit** und ist öffentlich (GitHub Pages) nur als leere Hülle erreichbar.
Texte liegen nur im Browser-Speicher der Familiengeräte. Keine Songtexte ins Repo
committen (auch nicht als Beispiel- oder Testdaten). Lieder-Dateien gehören in den
Ordner `privat/`, der per `.gitignore` von Git ausgenommen ist. Keine Features bauen,
die Texte aus dem Netz beziehen, veröffentlichen oder aus der App heraus weitergeben.

## Testen

Lokaler Server im Projektordner:

```
python3 -m http.server 8322
```

Dann `http://localhost:8322` aufrufen.

## Keine Browser-Dialoge

Nie `alert()`, `confirm()`, `prompt()` verwenden — immer Custom-Dialoge mit
Ja/Nein-Buttons (siehe `Confirm` in `index.html`).
