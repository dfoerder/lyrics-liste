# CLAUDE.md

Hinweise für Claude Code (claude.ai/code) zur Arbeit in diesem Repository.

## Projekt

**Lyrics-Liste** — eine PWA zum Verwalten von Songtext-Listen für gemeinsames Singen
(z.B. Hauskreis, Jugendabend, Worship-Gruppen). Ersetzt die bisher ausgedruckte
Lyrics-Sammlung christlicher Worship-Lieder.

Kernidee: Für verschiedene Gruppen lassen sich eigene Listen führen. Songs (Titel,
Autor/Künstler, Text) werden einmal in der Sammlung angelegt und können in mehreren
Listen verwendet werden. Anzeige und Druck für den gemeinsamen Gebrauch.

## Architektur

**Eine einzige Datei:** `index.html` enthält die gesamte App (React via
Babel-Standalone über CDN, kein Build-Schritt, kein npm).

**Offline / PWA:**
- `sw.js` — Service Worker. Cacht App-Shell und die CDN-Bibliotheken beim Install.
  Eigene Dateien: Netz zuerst, offline aus dem Cache. CDN: Cache zuerst.
  **Wenn die CDN-Versionen in `index.html` geändert werden:** `CDN_ASSETS` in
  `sw.js` anpassen und `CACHE` hochzählen (`lyrics-liste-v2`, …).
- `manifest.webmanifest` + `icons/` — Installierbarkeit (Homescreen)

**Daten:**
- `localStorage` — Nutzerstand:
  - `lyrics-lists` — Array der Listen: `[{id, name, songIds:[...]}]`
  - `lyrics-songs` — Map der Songs: `{ [id]: {id, title, artist, lyrics} }`

**React-Komponenten (in index.html):**
- `App` — Haupt-Component, verwaltet `phase` (`home`, `list`, `newsong`, `song`,
  `editsong`, `print`), `lists`, `songs`
- `HomeView` — Übersicht aller Listen
- `ListView` — eine Liste mit ihren Songs (hinzufügen, sortieren, entfernen)
- `SongPicker` — vorhandenen Song suchen und in Liste aufnehmen
- `SongEditor` — Song anlegen/bearbeiten (Titel, Autor, Text; „Text bereinigen")
- `SongView` — Songtext-Ansicht
- `PrintView` — Druckansicht der ganzen Liste

## Copyright / CCLI

Songtexte christlicher Lieder sind urheberrechtlich geschützt. Die App liefert bewusst
**keine Texte mit** — Nutzer fügen nur Lieder ein, für die ihre Gemeinde/Gruppe die
Rechte bzw. eine CCLI-Sammellizenz hat. Bei Features, die Texte aus dem Netz beziehen,
diesen Aspekt beachten und nicht ungefragt geschützte Volltexte einbetten/veröffentlichen.

## Testen

Lokaler Server im Projektordner:

```
python3 -m http.server 8322
```

Dann `http://localhost:8322` aufrufen.

## Keine Browser-Dialoge

Nie `alert()`, `confirm()`, `prompt()` verwenden — immer Custom-Dialoge mit
Ja/Nein-Buttons (siehe `Confirm` und `PromptDialog` in `index.html`).
