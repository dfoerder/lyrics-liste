# CLAUDE.md

Hinweise für Claude Code (claude.ai/code) zur Arbeit in diesem Repository.

## Projekt

**Lyrics-Liste** — eine PWA zum Anzeigen und Drucken von Liedtexten für die
Familienandachten einer Familie (privater Gebrauch).

Kernidee: Die App ist **beim Aufruf leer** (öffentlich nur eine leere Hülle). Lieder
kommen über Lieder-Dateien: vom Besitzer auf seinem Mac erstellt (`tools/lieder.py`,
Vorlage `lieder-prompt.md`) oder von Familienmitgliedern aus der App weitergegeben.

Entscheid des Besitzers (13.10.2026, Familiengebrauch nach Art. 19 URG):
- **Bearbeiten und neu anlegen** in der App ist erlaubt, für alle in der Familie. Die
  Änderung bleibt auf dem Gerät (`edited: true`, neue Lieder mit id `app-…`).
- **Weitergeben** aus der App ist erlaubt, aber nur als Datei über das Teilen-Fenster an
  selbst gewählte Empfänger (WhatsApp-Familiengruppe). Kein Upload, kein öffentlicher Link,
  kein Server, keine Suche im Netz oder KI-Dienst – Texte gehen nur von Gerät zu Gerät.
- Ein **Import führt zusammen**: neue Lieder kommen dazu, gleiche ids werden durch die
  Fassung aus der Datei ersetzt, alles andere bleibt. Jede Textfassung hat einen Zeitstempel
  `updated` (UTC `JJJJ-MM-TTThh:mm:ssZ`, unter dem Text als „Textstand …“). Ist die Fassung
  auf dem Gerät neuer (oder selbst bearbeitet ohne Zeitstempel), fragt `ImportDialog` je Lied,
  welche bleibt (`analyzeImport`, `mergeCollection(…, keepDeviceIds)`). `lieder.py` setzt
  `updated` beim Aufnehmen und bei geändertem Text/Angaben; `uebernehmen` übergeht bei
  `--alle` Lieder, deren Mac-Fassung neuer ist. Der Export-Vergleich ignoriert `updated`. Gelöschtes verschwindet deshalb
  nicht durch einen Import, nur über ⋯ → „Alle Lieder entfernen“ oder „Lied löschen“.
- **Papierkorb:** Löschen (Lied, Liste mit Liedern, Alle Lieder entfernen) verschiebt Lieder nach
  `collection.trash` (`trashSongs`, merkt Listen-Zugehörigkeit). Startseite ⋯: „Gelöschte
  wiederherstellen“ (`RestoreDialog`/`restoreSongs`, setzt Lieder an ihre Stelle zurück, legt
  mitgelöschte mitgeschickte Listen neu an) und „Gelöschte endgültig entfernen“. Kommt ein
  gelöschtes Lied mit einer Lieder-Datei, verlässt es den Papierkorb.

Erlaubt sind **eigene Listen** der Familienmitglieder: Sie verweisen nur per Lied-id
auf vorhandene Lieder (keine Texte), liegen nur auf dem jeweiligen Gerät und bleiben
bei einem Import erhalten. Deshalb Lied-ids in der Sammlung nie ändern.

## Architektur

**Eine einzige Datei:** `index.html` enthält die gesamte App (React via
Babel-Standalone über CDN, kein Build-Schritt, kein npm).

**App-Version:** `APP_VERSION` in `index.html` (Datum `JJJJ-MM-TT`) steht unten auf der
Startseite. Bei jeder Änderung an der App auf das aktuelle Datum setzen, damit man auf den
Geräten sieht, ob die neue Version geladen ist. Mehrere Änderungen am selben Tag: `-2`,
`-3`, … anhängen (Anzeige „5.10.2026 (2)“).

**Offline / PWA:**
- `sw.js` — Service Worker. Cacht App-Shell und die CDN-Bibliotheken beim Install.
  Eigene Dateien: Netz zuerst, offline aus dem Cache. CDN: Cache zuerst.
  **Wenn die CDN-Versionen in `index.html` geändert werden:** `CDN_ASSETS` (beim Install
  geladen) bzw. `LAZY_ASSETS` (erst bei Bedarf, z.B. Notenanzeige, PDF-Leser) in `sw.js`
  anpassen und `CACHE` hochzählen (zurzeit `lyrics-liste-v2`).
- `manifest.webmanifest` + `icons/` — Installierbarkeit (Homescreen)

**Import-Datei** (`type: "lyrics-liste-sammlung"`, `version: 2`):
`{type, version, created, lists:[{id, name, songIds}], songs:[{id, title, writers,
performer, year, lyrics, updated?, scores?, voices?, link?, chords?, capo?, musicxml?}]}` — `lists` optional. `scores` = optionale Liste von
Notenbildern als data-URI (`data:image/gif|png|jpeg;base64,…`), unverändert eingebettet.
`voices` = optionale Übungsstimmen `[{name, midi}]`, `midi` als data-URI
(`data:audio/midi;base64,…`), Reihenfolge Sopran, Alt, Tenor, Bass. Ältere App-Stände
ignorieren das Feld, deshalb bleibt `version: 2`. `link` = optionaler https-Link zum
Anhören (Spotify, YouTube, …), in der Liedansicht als Knopf „▶ Song spielen“; `chords` =
optionale Gitarrenakkorde: derselbe Text wie `lyrics` mit ChordPro-Akkorden („Her[E]bei“),
ohne die `[..]` genau gleich `lyrics` (sonst verworfen); deutsche (H, Fis, fis = Moll) oder
englische Schreibweise; `capo` = Kapodaster-Bund; `musicxml` = optionale Partitur als
MusicXML-Text (Probelauf: die App zeichnet sie statt des Notenbilds, `MusicXmlScore`). Den Link setzt
`lieder.py bearbeiten <id> --link URL` (oder `hinzufuegen --link`), `--link ""` entfernt ihn. Format-Spezifikation für Claude
steht in `lieder-prompt.md`; bei Formatänderungen beide Stellen anpassen.

**Lieder-Sammlung pflegen (auf dem Mac):**
- `tools/lieder.py` — CLI für `privat/familien-lieder.json`: Text aus der
  Zwischenablage formatieren und speichern, Noten anhängen (`--noten`, `noten`;
  GIF/PNG/JPEG unverändert, PDF seitenweise als PNG über `tools/pdf_seiten.swift`,
  dabei wird nur leerer weißer Rand abgeschnitten), Übungsstimmen als MIDI anhängen
  (`stimmen`; Stimme aus dem Dateiende `-s/-a/-t/-b`), Angaben/Listen ändern, Vorschau, Export nach `privat/versand/`. Gibt
  bewusst nie Songtexte oder Bildinhalte aus.
- **Ordner `privat/data`** (mit Unterordnern): je Lied `name.txt` (1. Zeile „Titel,
  Person, Jahr“, Leerzeile, Text; eine Zeile nur mit Link wird zu `link`), `name.pdf` (Noten), `name.mid` (Stimmen, eine Spur je
  Stimme). `lieder.py scan` findet neue/geänderte Lieder, `aus-ordner "<gruppe>"` liest
  eins ein. Was schon eingelesen ist, steht in `privat/data-import.json` (Gruppe → id +
  Prüfsummen); `verknuepfen`/`ignorieren` pflegen das. Unterordner `alt`/`mp3` werden
  übergangen.
- Fehlt die `.mid`: PDF mit Audiveris (installiert, `-batch -export`) erkennen,
  `tools/mxl_zu_stimmen.py` repariert typische Erkennungsfehler und meldet unklare Takte
  als PRÜFEN → `privat/data/<name>.stimmen`; unklare Stellen mit
  `tools/noten_raster.swift` (Lesehilfe mit Tonhöhen-Raster) nachsehen; MIDI mit
  `tools/midi_schreiben.py`; als Partitur für MuseScore & Co. `tools/stimmen_zu_musicxml.py`
  (`.stimmen` → `.musicxml`, je Stimme eine Partie, ohne Liedtext) bzw. `tools/midi_zu_musicxml.py`
  (eine oder mehrere `.mid` → `.musicxml`; rückt eingespielte Töne aufs Raster 1/12 Viertel,
  schließt Artikulationslücken, Triolen/Taktwechsel/Akkorde; `write_score` gemeinsam). `pdf_seiten.swift` beachtet Seitendrehung und CropBox und
  rendert kleine Seiten mit mindestens 1100 px Breite.
- **MusicXML in der App (Probelauf):** `stimmen_zu_musicxml.py <name>.stimmen --chorsatz` schreibt
  `<name>.chorsatz.musicxml` (2 Systeme: Sopran/Alt, Tenor/Bass, wie im Gesangbuch);
  `lieder.py musicxml <id> <datei>` / `--entfernen` hängt sie an (bleibt beim Neu-Einlesen
  erhalten). Bisher nur „Herbei, o ihr Gläubgen“.
- **Gitarrenakkorde:** `name.akkorde` neben der `.txt` (Muster vom Akkordblatt: je Strophe
  `Suchtext=Akkord` der Reihe nach, `kapo: N`; Liedtext wird nie abgetippt) → `aus-ordner` setzt
  `chords`; für vorhandene Lieder `lieder.py akkorde <id> <datei>` / `--entfernen`. Ändert sich der
  Text, fallen die Akkorde weg (Hinweis).
- `lieder.py uebernehmen <datei> [--alle | --id …] [--liste …]` — Datei aus der App (von der
  Familie weitergegeben) mit der Sammlung vergleichen: NEU/GEÄNDERT anzeigen (ohne Texte) und
  auf Wunsch übernehmen.
- Skills `/lied-hinzufuegen` und `/lieder-verschicken` (`.claude/skills/`) nutzen
  das Skript. Versand per WhatsApp wird nur vorbereitet, gesendet wird vom Nutzer.
- `lieder-prompt.md` — Alternative für ein Claude-Projekt in der Claude-App.

**Daten:**
- **IndexedDB** `lyrics-liste` / Store `daten` / Schlüssel `sammlung` — die zuletzt
  importierte Sammlung: `{created, importedAt, lists:[...], songs:{ [id]: {...} }, trash?:{ [id]: {song, deletedAt, lists} }}`.
  IndexedDB statt localStorage wegen der Notenbilder (localStorage auf iOS ~5 MB).
  Laden/Speichern asynchron (`loadCollection`/`saveCollection`); beim Import wird
  erst gespeichert, dann angezeigt. Ältere Stände unter `localStorage`
  `lyrics-sammlung` werden beim ersten Laden übernommen und danach dort gelöscht.
  `navigator.storage.persist()` wird angefragt.
- `localStorage` `lyrics-eigene-listen` — eigene Listen: `[{id, name, songIds}]`
  (ids beginnen mit `meine-`, eigene Reihenfolge). Werden weder vom Import noch vom
  Mülleimer gelöscht; ids fehlender Lieder bleiben stehen und erscheinen wieder,
  sobald das Lied zurückkommt.
- `localStorage` `lyrics-favoriten` — Favoriten: Lied-ids in eigener Reihenfolge. Auf der
  Startseite ganz oben, im Lied Knopf „☆ Zu Favoriten“ / „★ Favorit“. In `ListView` wie eine
  eigene Liste (`FAV_ID`, `own` + `fixed`: verschieben/entfernen ja, umbenennen/löschen nein).
  Bleibt bei Import und Mülleimer erhalten.
- `localStorage` `lyrics-noten-zeigen` — Noten in der Liedansicht ein-/ausgeblendet (Menü ⋯,
  gilt für alle Lieder auf dem Gerät; Druck zeigt Noten immer).
- `localStorage` `lyrics-darstellung` — `auto` (folgt Hell/Dunkel des iPhones,
  `prefers-color-scheme`), `hell` oder `dunkel` (Menü ⋯ auf der Startseite). Ein kleines Skript
  im `<head>` setzt `data-theme` vor dem ersten Zeichnen. Farben nur über die CSS-Variablen in
  `:root` (dunkle Werte in `@media screen`), der Druck bleibt immer hell; Noten bleiben weiß.
- `localStorage` `lyrics-akkorde-zeigen` (Akkord-Ansicht an/aus, für alle Lieder) und
  `lyrics-tonart` (`{id: Grundton 0–11}`, gewählte Zieltonart je Lied; fehlt = Original).
- `localStorage` `lyrics-stimme` — zuletzt gewählte Übungsstimme (Name, z.B. „Bass“).
- `localStorage` `lyrics-schriftgroesse` — Index in `FONT_SCALES` für die Schrift der
  Liedtexte (Knöpfe A/A in Lied- und Druckansicht); der Ausdruck bleibt bei 13pt.
- Alte Schlüssel `lyrics-lists` / `lyrics-songs` (v1) werden beim Import bzw.
  beim Entfernen gelöscht.

**React-Komponenten (in index.html):**
- `App` — verwaltet `phase` (`home`, `list`, `song`, `print`), `collection`, Import
- `HomeView` — Suchfeld (Volltextsuche nur auf dem Gerät: `buildSearchIndex`/`searchSongs`,
  fehlertolerant, ohne Netz und ohne KI-Dienst – Texte dürfen das Gerät nicht verlassen; Treffer
  mit Fundstelle, Suchbegriff bleibt in `App` erhalten), „Favoriten", „Alle Lieder", unter „Listen" alle Listen (mitgeschickte und eigene) + „Neue Liste",
  Menü ⋯ (importieren, weitergeben, alles entfernen), Stand-Datum
- `ListView` — oben ein Suchfeld, das nur in den Liedern dieser Liste sucht (`SearchField`/
  `SearchResults`, gleiche Suche wie auf der Startseite; Begriff in `App` `listQuery`, beim
  Öffnen einer Liste geleert); Lieder einer Liste; mitgeschickte Listen alphabetisch und nur lesen,
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
- `MusicXmlScore` — zeichnet `song.musicxml` mit OpenSheetMusicDisplay 1.8.9 (jsDelivr, erst bei
  Bedarf geladen, `sw.js` `LAZY_ASSETS` speichert sie dann für offline; ebenso pdf.js); weißer
  Hintergrund auch im Dunkelmodus; Umschalter „Original-Notenblatt zeigen“, wenn es auch `scores`
  gibt; bei Fehler Rückfall aufs Notenbild
- `SongEditor` — „✎ Bearbeiten“ im Lied und „+ Neues Lied“ (Alle Lieder, leere Startseite;
  `phase` `new`): Titel, Interpret, Jahr, Songwriter, Text, Link (https), Noten hochladen (PDF
  über pdf.js 3.11.174 von cdnjs, nur bei Bedarf geladen – braucht dann Internet; Seiten als
  JPEG mit abgeschnittenem Rand, `pdfToScores`/`trimCanvas`; oder PNG/JPEG unverändert),
  Übungsstimmen hochladen (MIDI, `filesToVoices`: mehrstimmige Datei wird je Spur aufgeteilt,
  sonst Name aus `-s/-a/-t/-b`); speichert über `saveSong` in IndexedDB, Verwerfen mit
  Rückfrage, „Lied löschen“ (`deleteSong`)
- `saveSongFiles` — Liedansicht ⋯ → „Als Dateien sichern“: `name.txt` (Kopf „Titel, Person,
  Jahr“, Link-Zeile, Text – wie in `privat/data`), `name.pdf` (Notenbilder, eigener kleiner
  PDF-Schreiber `scoresToPdf`), `name.mid` (alle Stimmen in einer Format-1-Datei,
  `voicesToMidi`) über das Teilen-Fenster (AirDrop an den Mac, „In Dateien sichern“)
- `ShareChooser` / `shareSongs` — ⋯ → „Lieder weitergeben“ auf der Startseite (Alle Lieder, Favoriten, eine Liste)
  und „📤 Weitergeben“ im Lied: baut eine Import-Datei (ohne `edited`) und öffnet
  `navigator.share`; ohne Teilen-Funktion Download. `mergeCollection` beim Import
- `ActionMenu` — Menü „⋯“ oben rechts. Startseite: Neues Lied, Lieder importieren, weitergeben, alle
  entfernen, Darstellung. Listenansicht: Neues Lied und Alle Lieder entfernen (Alle Lieder), Lieder hinzufügen (eigene
  Listen, Favoriten), Drucken / Anzeigen, Liste weitergeben (alle Listen), Liste umbenennen
  (eigene), Liste löschen (alle außer „Alle Lieder“ und Favoriten; `deleteList(withSongs)`:
  nur die Liste oder auch ihre Lieder, die dann aus allen Listen verschwinden; eine
  mitgeschickte Liste kommt mit dem nächsten Import zurück). Ohne
  Einträge wird kein Menü gezeigt. Liedansicht: Favoriten, Zu Liste hinzufügen, Noten ein-/ausblenden,
  Stimmen üben
  (blendet `VoicePlayer` ein, nur bei `voices`), Bearbeiten, Weitergeben. Darunter nur noch
  „▶ Song spielen“, eine Statuszeile (★ Favorit · In: … · bearbeitet) und die Noten-Knöpfe
  (`note-tools`): ♪ blendet ausgeblendete Noten ein, ♫ öffnet „Stimmen üben“; über sichtbaren
  Noten oben rechts ✕ zum Ausblenden
- `SongView` / `SongMeta` — Liedtext mit Titel, Interpret · Jahr und „Songwriter: …“;
  ohne Interpret (Choräle) stattdessen „Songwriter · Jahr“ in einer Zeile ohne Beschriftung;
  „▶ Song spielen“ öffnet `song.link` (falls vorhanden); „Zu Liste hinzufügen" öffnet `ListChooser` (Lied in eigene Listen legen/
  herausnehmen, neue Liste mit dem Lied anlegen)
- `ChordSheet` — Akkord-Ansicht (🎸 in den Noten-Knöpfen und im Menü ⋯, nur bei `chords`):
  Akkorde über der Silbe, Wörter brechen nie mittendrin. `transposeChord` kennt deutsche und
  englische Namen und wählt ♭/♯ nach der Ziel-Tonart.
- `KeyBar` — gemeinsame Tonart-Leiste (sichtbar, sobald Akkorde, Übungsstimmen oder gezeichnete
  Noten offen sind): −/+ Halbton, „Original“, „wie Akkorde“/„wie Noten“, wenn sich deren Tonarten
  unterscheiden. Eine Zieltonart je Lied; jede Quelle rechnet ihre Verschiebung aus der eigenen
  Tonart (`shiftTo`, −6…+5): Noten aus `<fifths>` (`xmlKey`, `transposeXml` setzt Vorzeichen und
  Schreibweise neu), Stimmen aus dem MIDI-Tonart-Ereignis (`voicesKey`, `VoicePlayer transpose`),
  Akkorde aus dem ersten Akkord (`chordsKey`). Das gescannte Notenbild bleibt im Original. Druck und Suche nutzen weiter `lyrics`. Der Editor verwirft
  `chords`, wenn der Text geändert wird (mit Warnung).
- `FontSizeButtons` — Schrift der Liedtexte kleiner/größer (CSS-Variable `--lyrics-scale`)
- `PrintView` — Druckansicht der ganzen Liste

## Bug-Melder (Testen, wie in der Bibel-App)

- **Einschalten:** unten auf der Startseite fünfmal auf die Versionszeile tippen (`VersionTap`),
  dieselben fünf Tipps schalten ihn aus; alternativ `?bugs=1` / `?bugs=0` an der URL
  (`localStorage` `lyrics-bugmode`). Dann schwebt unten rechts ein 🐞-Knopf (`BugReporter`).
- **Art:** 🐞 Fehler (mit Schwere) oder 💡 Neues Feature (`kind`).
- **Erfasst:** Text, Schwere, Ansicht (`window.__bugCtx`: phase, Liste, Liedtitel – nie
  Liedtext), App-Version, Gerät, letzte JS-Fehler (`window.__bugLog`, früher Script im `<head>`).
- **Versand per Mail:** „Per Mail senden“ öffnet `mailto:` mit Betreff und Text. Die
  Empfängeradresse steht bewusst **nicht** im Code (App ist öffentlich), sondern wird im Melder
  pro Gerät eingetragen (`lyrics-bug-mail`). Bugs liegen in `lyrics-bugs`, „gemailt“ markiert.

## Copyright / CCLI

Songtexte christlicher Lieder sind urheberrechtlich geschützt. Die App liefert bewusst
**keine Texte mit** und ist öffentlich (GitHub Pages) nur als leere Hülle erreichbar.
Texte liegen nur im Browser-Speicher der Familiengeräte. Keine Songtexte ins Repo
committen (auch nicht als Beispiel- oder Testdaten). Lieder-Dateien gehören in den
Ordner `privat/`, der per `.gitignore` von Git ausgenommen ist. Keine Features bauen,
die Texte aus dem Netz beziehen oder veröffentlichen; Weitergeben nur wie oben beschrieben
(Datei über das Teilen-Fenster an die Familie).

## Testen

Lokaler Server im Projektordner:

```
python3 -m http.server 8322
```

Dann `http://localhost:8322` aufrufen.

## Keine Browser-Dialoge

Nie `alert()`, `confirm()`, `prompt()` verwenden — immer Custom-Dialoge mit
Ja/Nein-Buttons (siehe `Confirm` und `PromptDialog` in `index.html`).

## Beim Zusammenfassen (compact)

Die zuletzt bearbeitete Aufgabe ausführlich behalten: genaue Befehle, Dateipfade,
Fehlermeldungen, offene Rückfragen und den letzten Stand von Dateien, die gerade
geändert werden.
