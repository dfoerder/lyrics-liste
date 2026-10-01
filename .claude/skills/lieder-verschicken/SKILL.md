---
name: lieder-verschicken
description: Bereitet den Versand der Lieder-Datei der Lyrics-Liste per WhatsApp an die Familie vor. Prüft die Sammlung, erzeugt die datierte Import-Datei in privat/versand/, fasst die Änderungen seit dem letzten Versand zusammen, legt einen Begleittext in die Zwischenablage und öffnet WhatsApp und den Finder. Das Senden übernimmt der Nutzer selbst. Verwende diesen Skill immer, wenn der Nutzer die Lieder, die Lieder-Datei oder die Sammlung verschicken, teilen, an die Familie schicken, per WhatsApp senden oder „rausschicken“ will, oder wenn er fragt, was sich seit dem letzten Versand geändert hat.
---

# Lieder verschicken

Die Familie importiert die Lieder-Datei in die Lyrics-Liste
(https://dfoerder.github.io/lyrics-liste/). Ein Import **ersetzt** alles auf dem Gerät.
Deshalb wird immer die komplette Sammlung verschickt, nie nur die neuen Lieder.

## Ablauf

1. **Export erzeugen** (vom Projektordner aus):
   ```bash
   python3 tools/lieder.py export
   ```
   Das Skript prüft die Sammlung. Es meldet zum Beispiel Lieder ohne Text oder Listen,
   die auf gelöschte Lieder zeigen. Bei Fehlern wird nichts exportiert. Dann zeig dem
   Nutzer die Probleme und hilf sie zu beheben, meist mit `/lied-hinzufuegen`.
   Ohne Fehler entsteht `privat/versand/familien-lieder-JJJJ-MM-TT-hh-mm.json`, und das
   Skript listet die Änderungen seit dem letzten Versand auf. Nimm für den nächsten
   Schritt genau den Pfad, den das Skript unter „Export:“ ausgibt.

2. **Keine Änderungen?** Sag das und frag, ob die Datei trotzdem raus soll, zum Beispiel
   für ein neues Familienmitglied.

3. **Begleittext schreiben:** kurz, freundlich, auf Deutsch, ohne Liedtexte. Nenne nur
   Titel und Interpreten der Änderungen. Vorlage:

   ```
   Neue Lieder für unsere Andachten (Stand 26.09.2026) 🎵
   Neu: Oceans (Hillsong United), Großer Gott, wir loben dich
   Geändert: Unter deinem Dach
   So geht's: Datei antippen → „In Dateien sichern“, dann in der Lyrics-Liste oben rechts 📥 antippen – die Datei steht meist ganz oben unter „Zuletzt verwendet“.
   App: https://dfoerder.github.io/lyrics-liste/
   ```
   - **Erster Versand:** Lass „Neu:“ weg und erkläre kurz, dass man die App über
     „Zum Home-Bildschirm“ installieren kann. In diesem Fall wird dort importiert, nicht
     in Safari, weil die Homescreen-App einen eigenen Speicher hat.
   - **Viele Änderungen:** Fasse sie zusammen („7 neue Lieder, u.a. …“).

4. **Text in die Zwischenablage legen.** Das `LANG` ist nötig, damit Umlaute richtig
   ankommen:
   ```bash
   printf '%s' "<Begleittext>" | LANG=en_US.UTF-8 pbcopy
   ```

5. **Finder und WhatsApp öffnen:**
   ```bash
   open -R "privat/versand/familien-lieder-JJJJ-MM-TT-hh-mm.json"
   open -a WhatsApp
   ```

6. **Dem Nutzer sagen, was noch zu tun ist:** die Datei aus dem Finder in den Chat der
   Familiengruppe ziehen, den Text mit ⌘V einfügen und senden. Zeig ihm den Begleittext
   auch im Chat, damit er ihn vor dem Senden sieht.

## Warum Claude nicht selbst sendet

Das Senden bleibt bewusst beim Nutzer. Nachrichten in seinem Namen sind seine
Entscheidung, und nur er sieht sicher, ob die richtige Gruppe offen ist. Eine falsche
Gruppe würde Songtexte an Leute schicken, für die sie nicht gedacht sind. Bittet der
Nutzer darum, dass du selbst sendest, erkläre das kurz und bleib bei der Vorbereitung.

## Hinweise

- Verschickt wird nur die Datei aus `privat/versand/`, nie `privat/familien-lieder.json`
  selbst. Die Arbeitsdatei kann halbfertige Änderungen enthalten.
- Frühere Versanddateien bleiben liegen. Das Skript vergleicht mit der neuesten davon.
  Nicht löschen, außer der Nutzer will aufräumen.
