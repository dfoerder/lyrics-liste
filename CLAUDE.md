# CLAUDE.md

Hinweise für Claude Code (claude.ai/code) zur Arbeit in diesem Repository.

## Projekt

**Lyrics-Liste** — eine PWA zum Anzeigen und Drucken von Liedtexten für die
Familienandachten einer Familie (privater Gebrauch).

Kernidee: Die App ist **ein reiner Viewer und beim Aufruf leer**. Lieder kommen
ausschließlich über eine Import-Datei, die der Besitzer auf seinem Mac mit einem
Claude-Prompt erstellt (Vorlage: `lieder-prompt.md`) und an die Familie schickt.
Ein Import **ersetzt** alle Lieder und mitgeschickten Listen. In der App gibt es
kein Anlegen, Bearbeiten, Online-Suchen oder Teilen/Exportieren von Liedern — bewusst
so, aus rechtlichen Gründen. Solche Funktionen nicht wieder einbauen.

Erlaubt sind **eigene Listen** der Familienmitglieder: Sie verweisen nur per Lied-id
auf vorhandene Lieder (keine Texte), liegen nur auf dem jeweiligen Gerät und bleiben
bei einem Import erhalten. Deshalb Lied-ids in der Sammlung nie ändern.

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
performer, year, lyrics, scores?, voices?}]}` — `lists` optional. `scores` = optionale Liste von
Notenbildern als data-URI (`data:image/gif|png|jpeg;base64,…`), unverändert eingebettet.
`voices` = optionale Übungsstimmen `[{name, midi}]`, `midi` als data-URI
(`data:audio/midi;base64,…`), Reihenfolge Sopran, Alt, Tenor, Bass. Ältere App-Stände
ignorieren das Feld, deshalb bleibt `version: 2`. Format-Spezifikation für Claude
steht in `lieder-prompt.md`; bei Formatänderungen beide Stellen anpassen.

**Lieder-Sammlung pflegen (auf dem Mac):**
- `tools/lieder.py` — CLI für `privat/familien-lieder.json`: Text aus der
  Zwischenablage formatieren und speichern, Noten anhängen (`--noten`, `noten`;
  GIF/PNG/JPEG unverändert, PDF seitenweise als PNG über `tools/pdf_seiten.swift`,
  dabei wird nur leerer weißer Rand abgeschnitten), Übungsstimmen als MIDI anhängen
  (`stimmen`; Stimme aus dem Dateiende `-s/-a/-t/-b`), Angaben/Listen ändern, Vorschau, Export nach `privat/versand/`. Gibt
  bewusst nie Songtexte oder Bildinhalte aus.
- Skills `/lied-hinzufuegen` und `/lieder-verschicken` (`.claude/skills/`) nutzen
  das Skript. Versand per WhatsApp wird nur vorbereitet, gesendet wird vom Nutzer.
- `lieder-prompt.md` — Alternative für ein Claude-Projekt in der Claude-App.

**Daten:**
- **IndexedDB** `lyrics-liste` / Store `daten` / Schlüssel `sammlung` — die zuletzt
  importierte Sammlung: `{created, importedAt, lists:[...], songs:{ [id]: {...} }}`.
  IndexedDB statt localStorage wegen der Notenbilder (localStorage auf iOS ~5 MB).
  Laden/Speichern asynchron (`loadCollection`/`saveCollection`); beim Import wird
  erst gespeichert, dann angezeigt. Ältere Stände unter `localStorage`
  `lyrics-sammlung` werden beim ersten Laden übernommen und danach dort gelöscht.
  `navigator.storage.persist()` wird angefragt.
- `localStorage` `lyrics-eigene-listen` — eigene Listen: `[{id, name, songIds}]`
  (ids beginnen mit `meine-`, eigene Reihenfolge). Werden weder vom Import noch vom
  Mülleimer gelöscht; ids fehlender Lieder bleiben stehen und erscheinen wieder,
  sobald das Lied zurückkommt.
- `localStorage` `lyrics-stimme` — zuletzt gewählte Übungsstimme (Name, z.B. „Bass“).
- `localStorage` `lyrics-schriftgroesse` — Index in `FONT_SCALES` für die Schrift der
  Liedtexte (Knöpfe A/A in Lied- und Druckansicht); der Ausdruck bleibt bei 13pt.
- Alte Schlüssel `lyrics-lists` / `lyrics-songs` (v1) werden beim Import bzw.
  beim Entfernen gelöscht.

**React-Komponenten (in index.html):**
- `App` — verwaltet `phase` (`home`, `list`, `song`, `print`), `collection`, Import
- `HomeView` — „Alle Lieder", mitgeschickte Listen, „Meine Listen" + „Neue Liste",
  Import-Button, alles entfernen, Stand-Datum
- `ListView` — Lieder einer Liste; mitgeschickte Listen alphabetisch und nur lesen,
  eigene Listen (`list.own`) in eigener Reihenfolge mit Hinzufügen/Verschieben/
  Entfernen/Umbenennen/Löschen
- `SongPicker` — Lieder aus der Sammlung zu einer eigenen Liste hinzufügen
- `PromptDialog` — Namenseingabe (neue Liste, umbenennen)
- `VoicePlayer` — Übungsplayer für `song.voices`: liest die MIDI-Dateien selbst
  (`parseMidi`, nur erstes Tempo) und erzeugt den Klang mit Web Audio (`playTone`,
  keine Bibliothek, keine Klangdateien). Stimme wählen (eigene laut, andere leise/aus),
  Tempo 50–130 %, Takt springen, Wiederholen. Geplant wird laufend 2 Schläge voraus.
  iPhone-Stummschalter: `navigator.audioSession.type='playback'` plus stummes
  `<audio>` im Hintergrund (`setSilentAudio`).
- `Scores` / `ScoreViewer` — Notenbilder über dem Text; Antippen öffnet Vollbild mit
  Zoomstufen
- `SongView` / `SongMeta` — Liedtext mit Titel, Interpret · Jahr und „Songwriter: …“;
  ohne Interpret (Choräle) stattdessen „Songwriter · Jahr“ in einer Zeile ohne Beschriftung;
  „Zu Liste hinzufügen" öffnet `ListChooser` (Lied in eigene Listen legen/
  herausnehmen, neue Liste mit dem Lied anlegen)
- `FontSizeButtons` — Schrift der Liedtexte kleiner/größer (CSS-Variable `--lyrics-scale`)
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
Ja/Nein-Buttons (siehe `Confirm` und `PromptDialog` in `index.html`).
