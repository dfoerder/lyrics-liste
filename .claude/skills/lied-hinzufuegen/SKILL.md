---
name: lied-hinzufuegen
description: Nimmt ein Lied in die private Lieder-Sammlung der Lyrics-Liste auf. Holt den Songtext aus der Zwischenablage, formatiert ihn (Akkorde, CCLI- und Copyright-Fußzeilen raus, Abschnitte wie Strophe/Refrain einheitlich), erfasst die Version (Interpret und Jahr) und speichert alles in privat/familien-lieder.json. Verwende diesen Skill immer, wenn der Nutzer ein Lied oder einen Songtext hinzufügen, aufnehmen, aktualisieren oder entfernen will, Liedangaben korrigieren möchte oder Lieder in Listen wie „Advent“ oder „Sonntagsandacht“ einsortieren will. Das gilt auch, wenn er nur „neues Lied: …“, „hab den Text kopiert“ oder „nimm Oceans von Hillsong auf“ schreibt.
---

# Lied hinzufügen

Die Lyrics-Liste ist eine App für die Familienandachten des Nutzers. Die App selbst
ist leer. Lieder kommen nur über eine Import-Datei, die hier auf dem Mac gepflegt wird:
`privat/familien-lieder.json`. Der Ordner `privat/` ist von Git ausgenommen, damit
Songtexte nie auf GitHub landen.

Alle Arbeit erledigt das Skript `tools/lieder.py` (vom Projektordner aus aufrufen).

## Der Songtext wird nie abgetippt

Den Text kopiert der Nutzer aus einer Quelle, für die die Familie die Rechte hat,
zum Beispiel CCLI SongSelect, ein Liederbuch oder gekaufte Noten. Das Skript liest ihn
direkt aus der Zwischenablage. Dafür gibt es zwei Gründe:

- **Urheberrecht:** Songtexte sind geschützt. Du schreibst keine Liedtexte aus dem
  Gedächtnis, ergänzt keine fehlenden Zeilen und gibst den Text auch nicht im Chat
  wieder. Das Skript gibt deshalb absichtlich nur Zusammenfassungen aus, also Abschnitte
  und Zeilenzahlen. Lies die Texte nicht mit `cat` oder Ähnlichem aus der JSON-Datei.
- **Keine Abschreibfehler:** Was aus der Zwischenablage kommt, stimmt Buchstabe für
  Buchstabe.

Möchte der Nutzer den formatierten Text sehen, öffne die Vorschau im Browser:
`python3 tools/lieder.py vorschau <id>`.

Fügt der Nutzer den Text stattdessen in den Chat ein, bitte ihn freundlich, den Text zu
kopieren und nur „kopiert“ zu schreiben. Dann läuft alles über das Skript.

## Ablauf

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

## Weitere Befehle

| Wunsch | Befehl |
|---|---|
| Text eines vorhandenen Liedes erneuern (neu kopiert) | `hinzufuegen --titel … --interpret … --ersetzen`. Nicht mitgegebene Angaben bleiben erhalten. Bei Liedern ohne Interpret zusätzlich `--ohne-version`. |
| Nur Angaben ändern | `bearbeiten <id> --songwriter … --interpret … --jahr … --titel …` |
| Lied löschen | `entfernen <id>`. Das Lied verschwindet auch aus allen Listen. Vorher kurz bestätigen lassen. |
| Listen pflegen | `liste "Advent" --hinzufuegen <id> <id>`, `--entfernen <id>`, `--loeschen` |
| Überblick (ohne Texte) | `uebersicht`. Zeigt auch die ids. |
| Formatierten Text ansehen | `vorschau [<id> …]`. Öffnet eine HTML-Seite im Browser. |

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
