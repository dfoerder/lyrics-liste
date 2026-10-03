---
name: lied-hinzufuegen
description: Nimmt neue Lieder in die private Lieder-Sammlung der Lyrics-Liste auf. Durchsucht den Ordner privat/data (mit Unterordnern) nach neuen oder geänderten Liedern – je Lied name.txt (Kopf „Titel, Person, Jahr“ + Text), name.pdf (Noten) und name.mid (Übungsstimmen) –, fragt pro neuem Lied nach den Listen und speichert alles in privat/familien-lieder.json. Kann auch Text aus der Zwischenablage formatieren, Liedangaben ändern, Lieder löschen und Listen pflegen. Verwende diesen Skill immer, wenn der Nutzer Lieder hinzufügen, aufnehmen, aktualisieren oder entfernen will, neue Dateien in privat/data abgelegt hat, Liedangaben korrigieren möchte oder Lieder in Listen wie „Morgenandacht“ oder „Abendandacht“ einsortieren will – auch bei „neue Lieder im Ordner“, „schau mal ob was Neues da ist“ oder einfach „/lied-hinzufuegen“ ohne weitere Angaben.
---

# Lied hinzufügen

Die Lyrics-Liste ist eine App für die Familienandachten des Nutzers. Die App selbst
ist leer. Lieder kommen nur über eine Import-Datei, die hier auf dem Mac gepflegt wird:
`privat/familien-lieder.json`. Der Ordner `privat/` ist von Git ausgenommen, damit
Songtexte nie auf GitHub landen.

Alle Arbeit erledigt das Skript `tools/lieder.py` (vom Projektordner aus aufrufen).

## Der Songtext wird nie abgetippt

Den Text bereitet der Nutzer selbst vor, aus einer Quelle, für die die Familie die
Rechte hat, zum Beispiel ein gekauftes Gesangbuch, SongSelect oder gekaufte Noten. Das
Skript liest ihn direkt aus seiner `.txt` in `privat/data` oder aus der Zwischenablage.
Dafür gibt es zwei Gründe:

- **Urheberrecht:** Songtexte sind geschützt. Du schreibst keine Liedtexte aus dem
  Gedächtnis, ergänzt keine fehlenden Zeilen und gibst den Text auch nicht im Chat
  wieder. Das Skript gibt deshalb absichtlich nur Zusammenfassungen aus, also Abschnitte
  und Zeilenzahlen. Lies die Texte nicht mit `cat` oder Ähnlichem, weder aus der
  JSON-Datei noch aus den `.txt`-Dateien.
- **Keine Abschreibfehler:** Was aus der Datei oder der Zwischenablage kommt, stimmt
  Buchstabe für Buchstabe.

Möchte der Nutzer den formatierten Text sehen, öffne die Vorschau im Browser:
`python3 tools/lieder.py vorschau <id>`.

Fügt der Nutzer den Text stattdessen in den Chat ein, bitte ihn freundlich, den Text zu
kopieren und nur „kopiert“ zu schreiben. Dann läuft alles über das Skript.

## Hauptweg: Lieder aus dem Ordner `privat/data`

Der Nutzer legt neue Lieder als Dateien in `privat/data` oder einen Unterordner, zum
Beispiel `privat/data/taize/`. Zu jedem Lied gehören drei Dateien mit gleichem Namen:

| Datei | Inhalt |
|---|---|
| `name.txt` | Kopf, dann eine Leerzeile und der Liedtext, Strophen durch Leerzeilen getrennt. Der Kopf ist entweder eine Zeile **Titel, Person, Jahr**, z.B. `Grosser Gott wir loben dich, Ignaz Franz, 1768`, oder zwei Zeilen: Titel, darunter **Person, Jahr**, z.B. `Matthias Claudius, 1779`. |
| `name.pdf` | Noten. Das Skript rendert sie als Bild, mit abgeschnittenem weißem Rand. Ein Bild (`name.png`, `name-noten.png`) geht auch. |
| `name.mid` | Übungsstimmen, eine Spur je Stimme. Das Skript teilt sie automatisch auf. Einzelne Dateien `name-s/-a/-t/-b.mid` gehen auch. |

„Person“ ist der Autor (Text oder Musik). Sie wird als Songwriter gespeichert, ohne
Interpret. Die App zeigt dann „Ignaz Franz · 1768“. Mehrere Personen mit „/“ oder „und“
trennen, nicht mit Komma, denn das Komma trennt Titel, Person und Jahr. Ein Komma im
Titel ist erlaubt.

Die Unterordner `alt` und `mp3` werden übergangen. Welche Dateien schon eingelesen sind,
merkt sich `privat/data-import.json`, mit Prüfsumme je Datei.

### MIDI fehlt? Aus den Noten ablesen

Bittet der Nutzer darum, die `.mid` aus den Noten zu erzeugen, und steht kein
Notenerkennungs-Programm bereit, liest du die Stimmen selbst ab. Bei „Der Mond ist
aufgegangen“ hat das zuverlässig geklappt:

1. **Bild holen:** Hat die PDF einen eingebetteten Scan, nimm diesen, denn er ist höher
   aufgelöst. Achte auf die Drehung der Seite und richte ihn mit `sips -r 270` o.ä.
   aufrecht aus. Sonst `swift tools/pdf_seiten.swift <pdf> <ordner> 5`.
2. **Raster:** `swift tools/noten_raster.swift <bild> <ordner>` richtet den Scan gerade
   aus und zeichnet ein beschriftetes Tonhöhen-Raster ein: rot für Linien, blau für
   Zwischenräume, „B“ steht für das Vorzeichen der Tonart. Es schreibt je Notenzeile drei
   Ausschnitte `zeile<N>_<teil>.png`. Lies sie mit dem Read-Tool Takt für Takt ab.
3. **Prüfen:** Steht ein Notenkopf zwischen zwei Rasterlinien, halte dich an die echten
   Notenlinien im Scan. Plausibilität: Wiederholte Melodieteile sollten gleich gelesen
   sein, und jeder Akkord sollte in der Tonart Sinn ergeben. Vorzeichen im Takt
   (♮, ♯, ♭) gesondert beachten.
4. **Notation schreiben:** `privat/data/<name>.stimmen`. Das Format steht oben in
   `tools/midi_schreiben.py`, zum Beispiel `Sopran: F4 | G4 F4 Bb4 A4 | G4:2 F4 A4 | …`.
   Vorzeichen immer ausschreiben (Bb, F#). Dann
   `python3 tools/midi_schreiben.py privat/data/<name>.stimmen`. Das Skript prüft, dass
   alle Stimmen pro Takt gleich lang sind, und schreibt `<name>.mid` daneben.
5. **Sagen,** dass die Stimmen abgelesen sind und durch Anhören geprüft werden sollten.
   Falsche Töne korrigiert man in der `.stimmen`-Datei und erzeugt die MIDI neu. Der Scan
   meldet das Lied dann als GEÄNDERT.

### Ablauf

1. **Scannen:** `python3 tools/lieder.py scan`. Die Ausgabe hat drei Arten von Zeilen:
   - `NEU: <gruppe> → „Titel“ · Person · Jahr`: Hier fehlt eventuell eine Datei
     („fehlt: .pdf, .mid“), oder es gibt die id schon („ACHTUNG“).
   - `GEÄNDERT: <gruppe> → <id>: …`: Dateien haben sich seit dem Einlesen geändert.
   - `UNVOLLSTÄNDIG: <gruppe>: …`: .txt fehlt, oder die Kopfzeile wurde nicht erkannt.
   Meldet der Scan „Nichts Neues“, sag das dem Nutzer und frag, ob er stattdessen einen
   Text aus der Zwischenablage aufnehmen möchte (siehe unten).
2. **Unvollständiges melden:** Fehlt PDF oder MIDI, frag, ob das Lied trotzdem schon
   aufgenommen werden soll. Fehlende Dateien können später ergänzt werden. Der Scan
   meldet das Lied dann als GEÄNDERT. Bei kaputter Kopfzeile beschreib dem Nutzer, was
   in Zeile 1 erwartet wird. Ist eine Datei gar kein Lied, zum Beispiel eine Sammeldatei:
   `python3 tools/lieder.py ignorieren "<gruppe>"`.
3. **Für jedes neue Lied nach den Listen fragen.** Das ist Pflicht, der Nutzer entscheidet
   das pro Lied. Die vorhandenen Listen zeigt `python3 tools/lieder.py uebersicht`.
   Frag mit AskUserQuestion: eine Frage je Lied (bis zu 4 Lieder pro Aufruf),
   `multiSelect: true`, die Listen als Optionen. Gibt es mehr als 4 Listen, frag
   stattdessen im Text. Eine neue Liste nennt der Nutzer über „Other“.
4. **Probelauf, dann speichern**, je Lied:
   ```bash
   python3 tools/lieder.py aus-ordner "<gruppe>" --liste "Morgenandacht" --liste "Abendandacht" --probelauf
   python3 tools/lieder.py aus-ordner "<gruppe>" --liste "Morgenandacht" --liste "Abendandacht"
   ```
   Der Kopf wird vom Text getrennt. Die erste Liedzeile bleibt also immer erhalten, auch
   wenn sie gleich dem Titel ist. Achte im Probelauf auf „HINWEIS: … mehr als 12 Zeilen“
   (Leerzeilen fehlen) und „ANDERE VERSION“.
5. **Geänderte Lieder:** Frag, ob sie neu eingelesen werden sollen. Dann
   `aus-ordner "<gruppe>" --ersetzen`. Die id und die Listen bleiben gleich, Text, Noten
   und Stimmen kommen neu aus den Dateien.
6. **Kurz berichten**, als Tabelle: Titel, Person · Jahr, Strophen, Noten, Stimmen,
   Listen. Biete die Vorschau an (`vorschau <id> …`) und erwähne am Ende
   `/lieder-verschicken`.

Ein Lied, das schon in der Sammlung ist, aber aus einer anderen Quelle stammt, verbindest
du mit seinen Dateien über `python3 tools/lieder.py verknuepfen "<gruppe>" <id>`. Danach
gilt es als eingelesen.

## Alternative: Text aus der Zwischenablage

Nur, wenn der Nutzer ausdrücklich einen kopierten Text aufnehmen will, ohne Dateien in
`privat/data`.

1. **Klären, welche Version gemeint ist.** Du brauchst Titel, Interpret und Jahr.
   Verschiedene Interpreten singen ein Lied oft leicht anders, und der Nutzer passt den
   Text an die Version an, die er singen will. Deshalb sind Interpret und Jahr Pflicht.
   Das Skript verweigert das Speichern ohne sie.
   - **Interpret fehlt:** Frag nach, welche Aufnahme gemeint ist. Rate nicht, auch
     nicht, wenn eine Version am bekanntesten ist. Du kannst bekannte Versionen als
     Auswahl anbieten.
   - **Nur das Jahr fehlt:** Schlag das Erscheinungsjahr dieser Aufnahme vor, wenn du
     es sicher weißt, und lass es den Nutzer bestätigen. Sonst frag nach.
   - **Ohne bestimmte Aufnahme:** Stammt der Text aus einem Liederbuch, zum Beispiel
     bei einem Choral, sagt der Nutzer das. Dann speicherst du mit `--ohne-version`,
     und Interpret und Jahr bleiben leer.

2. **Probelauf:**
   ```bash
   python3 tools/lieder.py hinzufuegen --titel "Oceans (Where Feet May Fail)" --probelauf
   ```
   Die Ausgabe zeigt die Strophen, entfernte Zeilen und Hinweise aus der
   Fußzeile (Songwriter, ©-Jahr, CCLI-Nummer). Achte auf Warnungen:
   - **Leere Zwischenablage, sehr kurzer Text oder „identischer Text wie bei …“:** Der
     Nutzer hat vermutlich etwas anderes kopiert. Sag es ihm und warte, bis er neu
     kopiert hat.
   - **Fußzeilen, die eigentlich Liedzeilen sind:** Das ist selten, aber möglich. Dann
     nachfragen.
   - **„ANDERE VERSION in der Sammlung: …“:** Vom selben Lied gibt es schon eine
     Version mit anderem Interpreten. Sag das dem Nutzer und frag, ob er beide Versionen
     behalten will oder die alte ersetzt werden soll. Zum Ersetzen speicherst du die
     neue Version und entfernst danach die alte mit `entfernen <id>`. Listen-Einträge
     der alten Version musst du dabei auf die neue übertragen. Weise den Nutzer darauf
     hin: Die Familie kann in der App eigene Listen anlegen, die Lieder über ihre id
     merken. Eine neue Version hat eine neue id und fällt dort heraus. Soll nur der
     Text korrigiert werden, ist `--ersetzen` besser, weil die id dann bleibt.
   - **„WARNUNG: Jahr … ist keine vierstellige Jahreszahl“:** Korrigieren.
   - **„HINWEIS: Ein Block hat mehr als 12 Zeilen …“:** Dem Text fehlen vermutlich die
     Leerzeilen zwischen den Strophen. Sag es dem Nutzer. Er kann den Text im Editor
     mit Leerzeilen versehen, neu kopieren, und dann ersetzt du den Text.

   Der Nutzer gliedert seine Texte bewusst nur mit Leerzeilen zwischen den Strophen,
   ohne Abschnittsnamen wie „Strophe“ oder „Refrain“. Das ist vollständig. Empfiehl
   keine Abschnittsnamen. Bringt ein kopierter Text sie mit, zum Beispiel aus
   SongSelect, formatiert das Skript sie einheitlich.

3. **Angaben bestimmen:**
   - **Titel:** offizieller Titel, wie er im Probelauf passt.
   - **Interpret:** die Band oder der Künstler der Version, die der Nutzer meint.
   - **Jahr:** Erscheinungsjahr *dieser Aufnahme*, bei einem Live-Album also das Jahr
     des Live-Albums. Das ©-Jahr aus der Fußzeile ist das Entstehungsjahr des Liedes und
     ist dafür nicht geeignet.
   - **Songwriter:** nebensächlich. Übernimm ihn nur aus der Fußzeile, dort steht er
     verlässlich aus der Lizenzdatenbank, oder wenn der Nutzer ihn angibt. Recherchiere
     ihn nicht. Fehlt er, bleibt er leer, und das ist in Ordnung.

   Eine falsche Angabe landet bei der ganzen Familie. Rate deshalb nicht, sondern frag
   lieber nach.

4. **Speichern** mit denselben Angaben ohne `--probelauf`. Mit `--liste` nimmst du das
   Lied gleich in Listen auf. Die Option geht mehrfach, und eine fehlende Liste wird
   angelegt:
   ```bash
   python3 tools/lieder.py hinzufuegen --titel "…" --songwriter "A, B" --interpret "…" --jahr 2013 --liste "Advent"
   ```

5. **Kurz berichten:** Titel, Interpret, Jahr, Songwriter (falls vorhanden), Strophen
   und Zeilenzahl, was entfernt wurde und ob es andere Versionen in der Sammlung gibt. Biete die Vorschau an.
   Erwähne am Ende, dass `/lieder-verschicken` die neue Datei an die Familie bringt,
   wenn er fertig ist.

## Noten (z.B. Taizé-Gesänge)

Für mehrstimmige Lieder kann ein Lied zusätzlich Noten haben: GIF, PNG, JPEG oder
PDF. Die gekauften Taizé-Noten von eXultet sind PDFs, zum Beispiel
`Choeur-<Titel>.pdf`. Die App zeigt sie über dem Text an, in Vollbild mit Zoom und im Druck. Der
Text bleibt trotzdem wichtig: Der Nutzer will bei Liedern mit Noten **Noten und Text**.
Wer keine Noten liest, kann so die Schriftgröße einstellen.

1. **Bild finden:** Der Nutzer lädt die Noten selbst herunter, zum Beispiel aus dem
   offiziellen Download von Taizé. Sagt er nicht genau, wo die Datei liegt, schau
   nach den neuesten Bildern im Download-Ordner:
   ```bash
   ls -lt ~/Downloads/*.pdf ~/Downloads/*.gif ~/Downloads/*.png ~/Downloads/*.jpg 2>/dev/null | head -5
   ```
   Nenn ihm Dateiname und Zeitpunkt und lass dir bestätigen, dass es die richtige
   Datei ist. Bei mehreren Seiten auch die Reihenfolge. Auf Wunsch zeigt
   `open -a Preview <datei>` das Bild.
2. **Unverändert übernehmen:** Das Skript bettet Bilder Byte für Byte ein. PDFs rendert
   es Seite für Seite als PNG mit 144 dpi (`tools/pdf_seiten.swift`, macOS-Bordmittel)
   und schneidet dabei nur den leeren weißen Rand ab, bis auf etwa 4 mm. So stehen die
   Noten auf dem iPhone nicht klein in einer großen weißen Seite. Die erste Umwandlung
   dauert ein paar Sekunden. Darüber hinaus schneidest, skalierst oder bearbeitest du
   die Noten nicht. Taizé erlaubt nur die Wiedergabe in der
   Originalfassung, und das gilt auch sonst für fremde Noten.
3. **Neues Lied mit Noten:** wie gewohnt mit Text aus der Zwischenablage, plus
   `--noten <datei>` (mehrfach für mehrere Seiten):
   ```bash
   python3 tools/lieder.py hinzufuegen --titel "…" --interpret "Taizé Community" --jahr 1986 --noten ~/Downloads/xyz.gif --liste "Morgenandacht"
   ```
   Bei Taizé-Gesängen beginnt der Text oft mit dem Titel, dann mit
   `--titelzeile-behalten` (siehe unten).
4. **Vorhandenes Lied ergänzen:** `python3 tools/lieder.py noten <id> ~/Downloads/xyz.gif`.
   Der Text bleibt dabei unverändert.

## Übungsstimmen (MIDI)

Ein Lied kann pro Stimme eine MIDI-Datei haben. Die App zeigt dann einen Übungsplayer:
eigene Stimme laut, die anderen leise oder aus, Tempo einstellbar. Die MIDI-Dateien
liegen meist neben dem Notenscan in `privat/scans/` und enden auf `-s`, `-a`, `-t`, `-b`
(Sopran, Alt, Tenor, Bass):

```bash
python3 tools/lieder.py stimmen <id> privat/scans/<name>-s.mid privat/scans/<name>-a.mid privat/scans/<name>-t.mid privat/scans/<name>-b.mid
```

Andere Namen (z.B. „Bariton“) ergeben sich aus dem Teil nach dem letzten Bindestrich
oder werden mit `--name` je Datei gesetzt.

**Mehrstimmige MIDI-Datei** (alle Stimmen in einer Datei, eine Spur je Stimme, z.B. die
Taizé-MIDIs in `privat/data/taize/`): mit `--aufteilen` zerlegt das Skript sie in einzelne
Stimmen. Jede Stimme bekommt die Steuerspur mit Tempo und Takt plus ihre Notenspur, die
Noten bleiben unverändert. Die Namen kommen aus den Spurnamen: Soprano → Sopran,
Alto → Alt, Base/Bass → Bass, Voice1 → Stimme 1, Solist bleibt.

```bash
python3 tools/lieder.py stimmen nada-te-turbe "privat/data/taize/Nada te turbe.mid" --aufteilen
``` `stimmen <id> --entfernen` nimmt sie wieder
weg. Beim Ersetzen des Textes bleiben vorhandene Stimmen erhalten. MIDI-Dateien sind
winzig (etwa 0,5 KB pro Stimme), die Lieder-Datei wird dadurch kaum größer.

Wird beim Ersetzen des Textes (`--ersetzen`) keine neue `--noten`-Datei angegeben,
bleiben vorhandene Noten erhalten. Die Ausgabe zeigt nur Seitenzahl und Größe, nie den
Bildinhalt.

## Weitere Befehle

| Wunsch | Befehl |
|---|---|
| Text eines vorhandenen Liedes erneuern (neu kopiert) | `hinzufuegen --titel … --interpret … --ersetzen`. Nicht mitgegebene Angaben bleiben erhalten. Bei Liedern ohne Interpret zusätzlich `--ohne-version`. |
| Nur Angaben ändern | `bearbeiten <id> --songwriter … --interpret … --jahr … --titel …` |
| Lied löschen | `entfernen <id>`. Das Lied verschwindet auch aus allen Listen. Vorher kurz bestätigen lassen. |
| Listen pflegen | `liste "Advent" --hinzufuegen <id> <id>`, `--entfernen <id>`, `--loeschen` |
| Überblick (ohne Texte) | `uebersicht`. Zeigt auch die ids. |
| Ordner nach Neuem durchsuchen | `scan` |
| Lied aus dem Ordner einlesen | `aus-ordner "<gruppe>" [--liste …] [--ersetzen] [--probelauf]` |
| Vorhandenes Lied mit Dateien verbinden | `verknuepfen "<gruppe>" <id>` |
| Datei beim Scan übergehen | `ignorieren "<gruppe>"` |
| Formatierten Text ansehen | `vorschau [<id> …]`. Öffnet eine HTML-Seite im Browser, mit Noten. |
| Noten an vorhandenes Lied hängen | `noten <id> BILD [BILD …]`. Ersetzt vorhandene Noten, der Text bleibt. `noten <id> --entfernen` nimmt sie wieder weg. |

Die id wird aus Titel und Interpret gebildet. Meldet das Skript, dass es die id schon
gibt, frag nach, ob der Nutzer das vorhandene Lied aktualisieren will (`--ersetzen`) oder
eine andere Version meint. Eine andere Version bekommt über `--interpret` automatisch
eine andere id.

## Was das Skript beim Formatieren macht

Zur Einordnung, falls der Nutzer fragt oder etwas unerwartet aussieht:
- **Akkorde:** Akkordzeilen und ChordPro-Akkorde wie `[G]` werden entfernt.
- **Fußzeilen:** Alles ab der ersten CCLI- oder ©-Markierung in der zweiten Hälfte des
  Textes wird abgeschnitten. Dazu kommen Zeilen wie „Text:“ oder „Melodie:“ und eine
  SongSelect-Zeile „A | B | C“ mit den Songwritern.
- **Titelzeile:** Die erste Zeile wird entfernt, wenn sie dem Titel entspricht. Meldet
  der Probelauf „Entfernt: Titelzeile“, prüf kurz, ob das stimmt. Bei Kanons und
  Taizé-Gesängen ist die erste Liedzeile oft gleich dem Titel. Dann mit
  `--titelzeile-behalten` speichern.
- **Abschnittsnamen:** Sie stehen in einer eigenen Zeile und werden einheitlich deutsch
  benannt: Verse → Strophe, Chorus → Refrain, Ending/Tag → Schluss. Bridge, Pre-Chorus
  und Intro bleiben.
- **Wiederholungen:** Angaben wie „x2“, „2x“ oder „(2x)“ werden zu „(2x)“
  vereinheitlicht und nicht ausgeschrieben.
- **Leerzeilen und Leerzeichen:** Überflüssige werden entfernt.
