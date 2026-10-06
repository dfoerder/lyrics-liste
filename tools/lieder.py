#!/usr/bin/env python3
"""Pflegt die private Lieder-Sammlung der Lyrics-Liste (privat/familien-lieder.json).

Songtexte kommen aus der Zwischenablage (oder --text-datei) und werden nie
ausgegeben – das Skript meldet nur Zusammenfassungen (Abschnitte, Zeilenzahlen,
entfernte Zeilen). Zum Ansehen gibt es `vorschau` (HTML im Browser).

Befehle:
  hinzufuegen   Lied aus der Zwischenablage formatieren und speichern
  bearbeiten    Angaben (Titel, Songwriter, Interpret, Jahr) ändern
  entfernen     Lied löschen (auch aus allen Listen)
  liste         Lieder einer Liste hinzufügen/entfernen, Liste löschen
  uebersicht    Alle Lieder und Listen (ohne Text)
  noten         Noten (GIF/PNG/JPEG/PDF) an ein Lied hängen oder entfernen
  stimmen       MIDI-Dateien je Stimme (Sopran, Alt, …) zum Üben anhängen oder entfernen
  vorschau      Formatierte Texte als HTML im Browser öffnen
  export        Datei für den Versand erzeugen (privat/versand/…)
"""
import argparse
import base64
import datetime
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / 'privat' / 'familien-lieder.json'
FILE_TYPE = 'lyrics-liste-sammlung'
UTF8_ENV = dict(os.environ, LANG='en_US.UTF-8', LC_ALL='en_US.UTF-8')


class Fehler(Exception):
    pass


# ---------------------------------------------------------------- Sammlung

def empty_collection():
    return {'type': FILE_TYPE, 'version': 2, 'created': today(), 'lists': [], 'songs': []}


def today():
    return datetime.date.today().isoformat()


def load(path):
    if not path.exists():
        return empty_collection()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('type') != FILE_TYPE:
        raise Fehler(f'{path} ist keine Lieder-Sammlung.')
    data.setdefault('lists', [])
    data.setdefault('songs', [])
    return data


def save(path, data):
    data['created'] = today()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def find_song(data, song_id):
    for s in data['songs']:
        if s['id'] == song_id:
            return s
    return None


def require_song(data, song_id):
    s = find_song(data, song_id)
    if not s:
        raise Fehler(f'Kein Lied mit der id "{song_id}". `uebersicht` zeigt alle ids.')
    return s


def find_list(data, name):
    key = slugify(name)
    for l in data['lists']:
        if l['id'] == key or l['name'].casefold() == name.casefold():
            return l
    return None


def slugify(text):
    text = text.replace('ß', 'ss')
    for a, b in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('Ä', 'Ae'), ('Ö', 'Oe'), ('Ü', 'Ue')):
        text = text.replace(a, b)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def lieder(n):
    return f'{n} Lied' if n == 1 else f'{n} Lieder'


def song_line(s):
    extra = ' · '.join(x for x in (s.get('performer'), s.get('year')) if x)
    return f'"{s["title"]}"' + (f' – {extra}' if extra else '')


# ---------------------------------------------------------------- Formatieren

SECTION_NAMES = [
    (r'pre-?chorus|prechorus|pre-?refrain', 'Pre-Chorus'),
    (r'verse|vers|strophe', 'Strophe'),
    (r'chorus|refrain|kehrvers', 'Refrain'),
    (r'bridge', 'Bridge'),
    (r'intro', 'Intro'),
    (r'outro|ending|ende|schluss|tag|coda', 'Schluss'),
    (r'interlude|zwischenspiel|zwischenteil|instrumental', 'Zwischenteil'),
]
LABEL_RE = re.compile(
    r'^[\[\(]?\s*(' + '|'.join(p for p, _ in SECTION_NAMES) + r')\s*(\d+)?\s*[\]\)]?'
    r'\s*(?:[\(\[]?\s*(?:(\d+)\s*[x×]|[x×]\s*(\d+))\s*[\)\]]?)?\s*:?\s*$', re.I)

CHORD = (r'[A-H](?:#|b|♯|♭)?(?:maj|min|dim|aug|sus|add|m|M|°|\+)?\d*'
         r'(?:(?:sus|add|maj|b|#)\d+)*(?:/[A-H](?:#|b|♯|♭)?)?')
CHORD_RE = re.compile(CHORD)
CHORD_FILLER = {'|', '||', '/', '-', '–', '(', ')', '.', '..', '...', 'N.C.', 'NC'}
INLINE_CHORD_RE = re.compile(r'\[(' + CHORD + r')\]')
REPEAT_TAIL_RE = re.compile(r'\s*[\(\[]\s*(?:(\d+)\s*[x×]|[x×]\s*(\d+))\s*[\)\]]\s*$|\s+(?:(\d+)[x×]|[x×](\d+))\s*$')

FOOTER_START_RE = re.compile(
    r'^(ccli|©|\(c\)|copyright|for use solely|nur zur verwendung|alle rechte|all rights reserved)', re.I)
# Nur mit Doppelpunkt bzw. "by" direkt dahinter – "Musik von Engeln …" ist eine Liedzeile
CREDIT_RE = re.compile(
    r'^(words (?:and|&) music|text (?:und|&) musik|worte (?:und|&) musik|words|music|lyrics|'
    r'text|worte|melodie|musik|übersetzung|übertragung|translation)\s*(?::|by\b)', re.I)
HINT_NAMES = {'writers': 'Songwriter', 'jahr_copyright': '© Jahr', 'ccli_nummer': 'CCLI'}
PAGE_RE = re.compile(r'^(seite|page)\s*\d+(\s*(von|of|/)\s*\d+)?$', re.I)
DIRECTIVE_RE = re.compile(r'^\{[^}]*\}$')


def is_chord_line(line):
    tokens = line.split()
    if not tokens:
        return False
    chords = 0
    for t in tokens:
        if CHORD_RE.fullmatch(t):
            chords += 1
        elif t not in CHORD_FILLER and not re.fullmatch(r'[\(\[]?[x×]?\d+[x×]?[\)\]]?', t):
            return False
    return chords > 0


def normalize_label(line):
    m = LABEL_RE.match(line.strip())
    if not m:
        return None
    word = m.group(1).lower()
    for pattern, name in SECTION_NAMES:
        if re.fullmatch(pattern, word):
            break
    label = name + (f' {m.group(2)}' if m.group(2) else '')
    rep = m.group(3) or m.group(4)
    return label + (f' ({rep}x)' if rep else '')


def comparable(text):
    return re.sub(r'[^a-z0-9äöüß]+', '', text.casefold())


def same_title(a, b):
    """Gleicher Liedtitel, Zusätze in Klammern wie "(Live)" ignoriert."""
    strip = lambda t: comparable(re.sub(r'[\(\[].*?[\)\]]', '', t))
    return strip(a) == strip(b)


def is_title_line(line, title):
    strip = lambda t: comparable(re.sub(r'[\(\[].*?[\)\]]', '', t))
    return comparable(line) == comparable(title) or strip(line) == strip(title)


def clean_lyrics(raw, title=''):
    """Formatiert einen eingefügten Songtext. Gibt (text, bericht) zurück."""
    report = {'akkordzeilen': 0, 'fusszeilen': [], 'titelzeile': False, 'sonstige': 0, 'hinweise': {}}
    text = raw.replace('\r\n', '\n').replace('\r', '\n').replace(' ', ' ').replace('\t', ' ')
    lines = [re.sub(r' {2,}', ' ', l).strip() for l in text.split('\n')]

    # Fußzeile (CCLI, ©, Nutzungsbedingungen …) ab der ersten Markierung in der zweiten Hälfte abschneiden
    nonblank = [i for i, l in enumerate(lines) if l]
    if nonblank:
        half = nonblank[len(nonblank) // 2]
        for i, l in enumerate(lines):
            if i >= half and FOOTER_START_RE.match(l):
                report['fusszeilen'] = [x for x in lines[i:] if x]
                lines = lines[:i]
                break

    out = []
    first_content = True
    for l in lines:
        if not l:
            out.append('')
            continue
        if first_content and title and is_title_line(l, title):
            report['titelzeile'] = True
            first_content = False
            continue
        first_content = False
        if CREDIT_RE.match(l):
            report['fusszeilen'].append(l)
            continue
        if PAGE_RE.match(l) or DIRECTIVE_RE.match(l):
            report['sonstige'] += 1
            continue
        if is_chord_line(l):
            report['akkordzeilen'] += 1
            continue
        label = normalize_label(l)
        if label:
            out.append(label)
            continue
        if INLINE_CHORD_RE.search(l):
            report['akkordzeilen'] += 1
            l = re.sub(r' {2,}', ' ', INLINE_CHORD_RE.sub('', l)).strip()
            if not l:
                continue
        m = REPEAT_TAIL_RE.search(l)
        if m:
            rep = next(g for g in m.groups() if g)
            l = l[:m.start()].rstrip() + f' ({rep}x)'
        out.append(l)

    # Songwriter-Zeile im SongSelect-Stil ("A | B | C") direkt vor der Fußzeile
    tail = [i for i, l in enumerate(out) if l]
    if tail and ' | ' in out[tail[-1]]:
        report['fusszeilen'].insert(0, out.pop(tail[-1]))

    # Leerzeilen: vor jedem Abschnittsnamen genau eine, direkt danach keine, sonst max. eine
    result = []
    for l in out:
        if l and normalize_label(l) == l:
            while result and result[-1] == '':
                result.pop()
            if result:
                result.append('')
            result.append(l)
        elif l == '':
            if result and result[-1] != '' and normalize_label(result[-1]) != result[-1]:
                result.append('')
        else:
            result.append(l)
    while result and result[-1] == '':
        result.pop()

    report['hinweise'] = footer_hints(report['fusszeilen'])
    return '\n'.join(result), report


def footer_hints(footer):
    hints = {}
    names = []
    for l in footer:
        m = CREDIT_RE.match(l)
        if ' | ' in l:
            parts = l.split('|')
        elif m:
            rest = re.sub(r'\(.*?\)|\b\d{4}\b', '', l[m.end():])
            parts = re.split(r',|&|\bund\b|\band\b|/', rest)
        else:
            parts = []
        for part in parts:
            name = part.strip(' .:;')
            if name and name not in names:
                names.append(name)
    if names:
        hints['writers'] = ', '.join(names)
    for l in footer:
        m = re.search(r'(?:©|\(c\)|copyright)\s*(\d{4})', l, re.I)
        if m and 'jahr_copyright' not in hints:
            hints['jahr_copyright'] = m.group(1)
        m = re.search(r'ccli[^0-9]*(?:song|lied)[^0-9]*(\d{4,9})', l, re.I)
        if m:
            hints['ccli_nummer'] = m.group(1)
    return hints


def describe(lyrics):
    """Abschnitte mit Zeilenzahlen – ohne den Text selbst."""
    sections, current, count = [], None, 0
    for l in lyrics.split('\n'):
        if l and normalize_label(l) == l:
            if current is not None or count:
                sections.append((current or '(ohne Namen)', count))
            current, count = l, 0
        elif l:
            count += 1
    if current is not None or count:
        sections.append((current or '(ohne Namen)', count))
    total = sum(c for _, c in sections)
    return total, sections


def stanza_sizes(lyrics):
    """Zeilen je Block zwischen Leerzeilen (Abschnittsnamen zählen nicht mit)."""
    blocks = [b for b in re.split(r'\n\s*\n', lyrics) if b.strip()]
    return [sum(1 for l in b.split('\n') if l.strip() and normalize_label(l) != l) for b in blocks]


IMAGE_TYPES = [(b'GIF87a', 'image/gif'), (b'GIF89a', 'image/gif'), (b'\x89PNG', 'image/png'),
               (b'\xff\xd8\xff', 'image/jpeg')]


PDF_SCALE = '2'   # 144 dpi


def image_uri(raw, name):
    mime = next((m for sig, m in IMAGE_TYPES if raw.startswith(sig)), None)
    if not mime:
        raise Fehler(f'{name} ist kein GIF-, PNG- oder JPEG-Bild und kein PDF.')
    if len(raw) > 1_000_000:
        print(f'WARNUNG: {name} ist {len(raw) // 1024} KB groß – die Lieder-Datei wird dadurch deutlich größer.')
    return f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')


def pdf_pages(path):
    """Jede PDF-Seite als PNG rendern (ganze Seite, ohne Zuschnitt) – siehe pdf_seiten.swift."""
    with tempfile.TemporaryDirectory() as tmp:
        res = subprocess.run(['swift', str(ROOT / 'tools' / 'pdf_seiten.swift'), str(path), tmp, PDF_SCALE],
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise Fehler(f'PDF {path.name} konnte nicht in Bilder umgewandelt werden: {res.stderr.strip()[:300]}')
        pages = [Path(line) for line in res.stdout.split() if line.endswith('.png')]
        if not pages:
            raise Fehler(f'PDF {path.name} hat keine Seiten.')
        return [image_uri(pg.read_bytes(), f'{path.name} Seite {i + 1}') for i, pg in enumerate(pages)]


def read_scores(path):
    """Notenbild(er) unverändert als data-URIs (Taizé: nur Originalfassung erlaubt).
    Bilder werden Byte für Byte übernommen, PDFs seitenweise als PNG gerendert."""
    p = Path(path).expanduser()
    try:
        raw = p.read_bytes()
    except OSError as err:
        raise Fehler(f'Notendatei nicht lesbar: {err}')
    if raw.startswith(b'%PDF'):
        uris = pdf_pages(p)
        print(f'PDF {p.name}: {len(uris)} {"Seite" if len(uris) == 1 else "Seiten"} als Bild übernommen')
        return uris
    return [image_uri(raw, p.name)]


def scores_info(song):
    """z.B. '1 Seite, 42 KB' – ohne Bildinhalt."""
    scores = song.get('scores') or []
    if not scores:
        return ''
    size = sum(len(x) * 3 // 4 for x in scores) // 1024
    return f'{len(scores)} {"Seite" if len(scores) == 1 else "Seiten"}, {size} KB'


def read_input(args):
    if args.text_datei:
        try:
            return Path(args.text_datei).read_text(encoding='utf-8')
        except OSError as err:
            raise Fehler(f'Textdatei nicht lesbar: {err}')
    res = subprocess.run(['pbpaste'], capture_output=True, env=UTF8_ENV)
    return res.stdout.decode('utf-8', errors='replace')


# ---------------------------------------------------------------- Befehle

def cmd_hinzufuegen(args, data):
    raw = read_input(args)
    if not raw.strip():
        raise Fehler('Die Zwischenablage ist leer. Bitte den Liedtext kopieren und nochmal versuchen.')
    if raw.lstrip().startswith(('{', '[')) and '"type"' in raw:
        raise Fehler('In der Zwischenablage liegt JSON statt eines Liedtexts.')
    if re.fullmatch(r'\s*https?://\S+\s*', raw):
        raise Fehler('In der Zwischenablage liegt nur ein Link statt eines Liedtexts.')

    # Bei Kanons/Taizé-Gesängen ist die erste Zeile oft gleich dem Titel, gehört aber zum Text
    lyrics, rep = clean_lyrics(raw, '' if args.titelzeile_behalten else args.titel)
    song_id = args.id or slugify(args.titel + (' ' + args.interpret if args.interpret else ''))
    existing = find_song(data, song_id)
    if existing and not args.ersetzen:
        raise Fehler(f'Es gibt schon {song_line(existing)} (id {song_id}). '
                     'Mit --ersetzen aktualisieren oder mit --id eine andere id vergeben.')
    duplicate = next((s for s in data['songs'] if s.get('lyrics') == lyrics and s['id'] != song_id), None)

    # Beim Ersetzen bleiben Angaben erhalten, die nicht neu mitgegeben werden
    keep = existing or {}
    pick = lambda value, field: value.strip() if value is not None else keep.get(field, '')
    song = {'id': song_id, 'title': args.titel.strip(), 'writers': pick(args.songwriter, 'writers'),
            'performer': pick(args.interpret, 'performer'), 'year': pick(args.jahr, 'year'), 'lyrics': lyrics}
    scores = [u for f in args.noten for u in read_scores(f)] if args.noten else keep.get('scores', [])
    if scores:
        song['scores'] = scores
    if keep.get('voices'):
        song['voices'] = keep['voices']
    link = pick(args.link, 'link')
    if link:
        song['link'] = check_link(link)

    total, sections = describe(lyrics)
    status = 'Probelauf – nichts gespeichert' if args.probelauf else ('aktualisiert' if existing else 'neu')
    print(f'{song_line(song)} (id: {song_id}) – {status}')
    if song['writers']:
        print(f'Songwriter: {song["writers"]}')
    if sections and any(name != '(ohne Namen)' for name, _ in sections):
        print(f'Text: {total} Zeilen in {len(sections)} Abschnitten: '
              + ', '.join(f'{n} ({c if c else "Wiederholung"})' for n, c in sections))
    else:
        sizes = stanza_sizes(lyrics)
        print(f'Text: {total} Zeilen in {len(sizes)} {"Strophe" if len(sizes) == 1 else "Strophen"} (durch Leerzeilen getrennt): '
              + ', '.join(map(str, sizes)) + ' Zeilen')
    if max(stanza_sizes(lyrics) or [0]) > 12:
        print('HINWEIS: Ein Block hat mehr als 12 Zeilen ohne Leerzeile – vermutlich fehlen '
              'Leerzeilen zwischen den Strophen. In der App wirkt das wie ein langer Block.')
    removed = []
    if rep['akkordzeilen']:
        removed.append(f'{rep["akkordzeilen"]} Zeilen mit Akkorden')
    if rep['fusszeilen']:
        removed.append(f'{len(rep["fusszeilen"])} Fußzeilen')
    if rep['titelzeile']:
        removed.append('Titelzeile')
    if rep['sonstige']:
        removed.append(f'{rep["sonstige"]} sonstige (Seitenzahlen, Steuerzeilen)')
    print('Entfernt: ' + (', '.join(removed) if removed else 'nichts'))
    if song.get('scores'):
        print(f'Noten: {scores_info(song)}' + (' (neu)' if args.noten else ' (beibehalten)'))
    if song.get('voices'):
        print(f'Stimmen: {voices_info(song)} (beibehalten)')
    if song.get('link'):
        print(f'Link: {song["link"]}' + ('' if args.link else ' (beibehalten)'))
    for l in rep['fusszeilen']:
        print(f'  Fußzeile: {l[:100]}')
    h = rep['hinweise']
    if h:
        print('Hinweise aus der Fußzeile: ' + '; '.join(f'{HINT_NAMES[k]}: {v}' for k, v in h.items()))
    if total < 4:
        print('WARNUNG: sehr kurzer Text – war wirklich der Liedtext in der Zwischenablage?')
    if duplicate:
        print(f'WARNUNG: identischer Text wie bei {song_line(duplicate)} – vermutlich wurde der neue Text nicht kopiert.')
    others = [s for s in data['songs'] if s['id'] != song_id and same_title(s['title'], song['title'])]
    for s in others:
        print(f'ANDERE VERSION in der Sammlung: {song_line(s)} (id {s["id"]})')
    if song['year'] and not re.fullmatch(r'\d{4}', song['year']):
        print(f'WARNUNG: Jahr "{song["year"]}" ist keine vierstellige Jahreszahl.')
    if not song['writers']:
        print('Songwriter: leer (nur aus Fußzeile oder Angabe des Nutzers übernehmen)')

    # Interpret und Jahr bestimmen die Version und damit den Text – deshalb Pflicht
    missing = [n for n, k in (('Interpret', 'performer'), ('Jahr', 'year')) if not song[k]]
    if missing and not args.ohne_version:
        message = (f'{" und ".join(missing)} {"fehlt" if len(missing) == 1 else "fehlen"}. '
                   'Sie bestimmen die Version und damit den Text. Mit --interpret/--jahr angeben '
                   '(oder --ohne-version für Texte ohne bestimmte Aufnahme, z.B. aus dem Liederbuch).')
        if args.probelauf:
            print('PFLICHT: ' + message)
        else:
            raise Fehler(message)

    if args.probelauf:
        return False
    if existing:
        data['songs'][data['songs'].index(existing)] = song
    else:
        data['songs'].append(song)
    for name in args.liste or []:
        add_to_list(data, name, [song_id])
        print(f'In Liste "{name}" aufgenommen')
    return True


def check_link(url):
    url = url.strip()
    if not re.fullmatch(r'https://\S+', url):
        raise Fehler(f'Link muss mit https:// beginnen und darf keine Leerzeichen enthalten: {url}')
    return url


def add_to_list(data, name, ids):
    l = find_list(data, name)
    if not l:
        l = {'id': slugify(name), 'name': name, 'songIds': []}
        data['lists'].append(l)
    for i in ids:
        require_song(data, i)
        if i not in l['songIds']:
            l['songIds'].append(i)
    return l


def cmd_bearbeiten(args, data):
    s = require_song(data, args.id)
    for field, value in (('title', args.titel), ('writers', args.songwriter),
                         ('performer', args.interpret), ('year', args.jahr)):
        if value is not None:
            s[field] = value.strip()
    if args.link is not None:
        if args.link.strip():
            s['link'] = check_link(args.link)
        else:
            s.pop('link', None)                  # --link "" entfernt den Link
    print(f'Geändert: {song_line(s)}' + (f' | Songwriter: {s["writers"]}' if s['writers'] else '')
          + (f' | Link: {s["link"]}' if s.get('link') else ''))
    return True


def cmd_entfernen(args, data):
    s = require_song(data, args.id)
    data['songs'].remove(s)
    for l in data['lists']:
        if s['id'] in l['songIds']:
            l['songIds'].remove(s['id'])
            print(f'Aus Liste "{l["name"]}" entfernt')
    print(f'Gelöscht: {song_line(s)}')
    return True


def cmd_liste(args, data):
    if args.loeschen:
        l = find_list(data, args.name)
        if not l:
            raise Fehler(f'Keine Liste "{args.name}".')
        data['lists'].remove(l)
        print(f'Liste "{l["name"]}" gelöscht (Lieder bleiben in der Sammlung)')
        return True
    l = add_to_list(data, args.name, args.hinzufuegen or [])
    for i in args.entfernen or []:
        if i in l['songIds']:
            l['songIds'].remove(i)
    print(f'Liste "{l["name"]}": {lieder(len(l["songIds"]))}')
    for i in l['songIds']:
        print(f'  {song_line(find_song(data, i))}')
    return True


VOICE_SUFFIXES = {'s': 'Sopran', 'a': 'Alt', 't': 'Tenor', 'b': 'Bass'}
VOICE_ORDER = ['Sopran', 'Alt', 'Tenor', 'Bass']


def voice_name(path):
    """Stimmname aus dem Dateinamen: …-s.mid → Sopran, -a Alt, -t Tenor, -b Bass,
    sonst der Teil nach dem letzten Bindestrich (z.B. …-bariton.mid → Bariton)."""
    tail = path.stem.rsplit('-', 1)[-1]
    return VOICE_SUFFIXES.get(tail.lower(), tail[:1].upper() + tail[1:])


def read_midi(path):
    p = Path(path).expanduser()
    try:
        raw = p.read_bytes()
    except OSError as err:
        raise Fehler(f'MIDI-Datei nicht lesbar: {err}')
    if not raw.startswith(b'MThd'):
        raise Fehler(f'{p.name} ist keine MIDI-Datei.')
    return p, raw


def midi_uri(raw):
    return 'data:audio/midi;base64,' + base64.b64encode(raw).decode('ascii')


def read_voice(path, name=None):
    p, raw = read_midi(path)
    return {'name': name or voice_name(p), 'midi': midi_uri(raw)}


# Spurnamen in mehrstimmigen MIDI-Dateien (z.B. Taizé „4voix“) → Stimmnamen der App
TRACK_NAMES = {'soprano': 'Sopran', 'sopran': 'Sopran', 'alto': 'Alt', 'alt': 'Alt', 'tenor': 'Tenor',
               'bass': 'Bass', 'base': 'Bass', 'basse': 'Bass', 'solist': 'Solist', 'solo': 'Solist'}


def split_voices(path):
    """Mehrstimmige MIDI-Datei (Format 1, eine Spur je Stimme) in einzelne Stimmen aufteilen.
    Jede Stimme = Steuerspur (Tempo/Takt) + ihre Notenspur, Noten unverändert."""
    import struct
    p, raw = read_midi(path)
    hlen = struct.unpack('>I', raw[4:8])[0]
    fmt, ntracks, div = struct.unpack('>HHH', raw[8:14])
    if fmt != 1:
        raise Fehler(f'{p.name} hat MIDI-Format {fmt} – aufteilen geht nur bei Format 1 (eine Spur je Stimme).')
    chunks, pos = [], 8 + hlen
    while pos + 8 <= len(raw) and len(chunks) < ntracks:
        size = struct.unpack('>I', raw[pos + 4:pos + 8])[0]
        chunks.append(raw[pos:pos + 8 + size])
        pos += 8 + size

    def info(chunk):
        """(Spurname, enthält Noten?) – einfacher Durchlauf durch die Ereignisse."""
        data, q, status, tname, notes = chunk[8:], 0, 0, '', False
        def vlq():
            nonlocal q
            v = 0
            while q < len(data):
                c = data[q]; q += 1; v = (v << 7) | (c & 0x7F)
                if not c & 0x80:
                    break
            return v
        while q < len(data):
            vlq()
            c = data[q]
            if c == 0xFF:
                typ = data[q + 1]; q += 2; ln = vlq()
                if typ == 0x03:
                    tname = data[q:q + ln].decode('latin-1').strip()
                q += ln
                continue
            if c in (0xF0, 0xF7):
                q += 1; q += vlq()
                continue
            if c & 0x80:
                status = c; q += 1
            hi = status & 0xF0
            d2 = data[q + 1] if hi not in (0xC0, 0xD0) else 0
            if hi == 0x90 and d2 > 0:
                notes = True
            q += 1 if hi in (0xC0, 0xD0) else 2
        return tname, notes

    conductor = chunks[0]
    voices = []
    for i, chunk in enumerate(chunks[1:], 1):
        tname, notes = info(chunk)
        if not notes:
            continue
        key = tname.lower()
        m = re.fullmatch(r'voice\s*(\d+)', key)
        name = TRACK_NAMES.get(key) or (f'Stimme {m.group(1)}' if m else (tname or f'Stimme {i}'))
        midi = raw[:8 + hlen][:10] + struct.pack('>H', 2) + raw[12:8 + hlen] + conductor + chunk
        voices.append({'name': name, 'midi': midi_uri(midi)})
    if len(voices) < 2:
        raise Fehler(f'{p.name}: nur {len(voices)} Notenspur gefunden – nichts aufzuteilen.')
    return voices


def voices_info(song):
    """z.B. 'Sopran, Alt, Tenor, Bass (3 KB)' – ohne Inhalt."""
    voices = song.get('voices') or []
    if not voices:
        return ''
    size = max(1, sum(len(v['midi']) * 3 // 4 for v in voices) // 1024)
    return f'{", ".join(v["name"] for v in voices)} ({size} KB)'


def cmd_stimmen(args, data):
    s = require_song(data, args.id)
    if args.entfernen:
        s.pop('voices', None)
        print(f'Stimmen entfernt: {song_line(s)}')
        return True
    if not args.dateien:
        raise Fehler('Bitte mindestens eine MIDI-Datei angeben (oder --entfernen).')
    if args.name and len(args.name) != len(args.dateien):
        raise Fehler('--name muss so oft angegeben werden, wie es MIDI-Dateien gibt.')
    if args.aufteilen:
        if len(args.dateien) != 1:
            raise Fehler('--aufteilen erwartet genau eine mehrstimmige MIDI-Datei.')
        voices = split_voices(args.dateien[0])
    else:
        voices = [read_voice(f, args.name[i] if args.name else None) for i, f in enumerate(args.dateien)]
    names = [v['name'] for v in voices]
    if len(set(names)) != len(names):
        raise Fehler(f'Stimmnamen doppelt: {", ".join(names)} – mit --name eindeutig benennen.')
    order = {n: i for i, n in enumerate(VOICE_ORDER)}
    voices.sort(key=lambda v: order.get(v['name'], len(order)))
    s['voices'] = voices
    print(f'Stimmen gesetzt: {song_line(s)} – {voices_info(s)}')
    return True


def cmd_noten(args, data):
    s = require_song(data, args.id)
    if args.entfernen:
        s.pop('scores', None)
        print(f'Noten entfernt: {song_line(s)}')
        return True
    if not args.bilder:
        raise Fehler('Bitte mindestens ein Notenbild angeben (oder --entfernen).')
    s['scores'] = [u for f in args.bilder for u in read_scores(f)]
    print(f'Noten gesetzt: {song_line(s)} – {scores_info(s)}')
    return True


def cmd_uebersicht(args, data):
    print(f'{lieder(len(data["songs"]))}, {len(data["lists"])} Listen (Stand {data.get("created", "?")})')
    for s in sorted(data['songs'], key=lambda s: s['title'].casefold()):
        total, _ = describe(s.get('lyrics', ''))
        stanzas = len(stanza_sizes(s.get('lyrics', '')))
        lists = [l['name'] for l in data['lists'] if s['id'] in l['songIds']]
        print(f'  [{s["id"]}] {song_line(s)} | {s.get("writers") or "Songwriter fehlt"} | '
              f'{total} Zeilen in {stanzas} {"Strophe" if stanzas == 1 else "Strophen"}'
              + (f' | Noten: {scores_info(s)}' if s.get('scores') else '')
              + (f' | Stimmen: {voices_info(s)}' if s.get('voices') else '')
              + (' | Link' if s.get('link') else '')
              + (f' | Listen: {", ".join(lists)}' if lists else ''))
    for l in data['lists']:
        print(f'Liste "{l["name"]}": {lieder(len(l["songIds"]))}')
    return False


def cmd_vorschau(args, data):
    songs = [require_song(data, i) for i in args.ids] if args.ids else \
        sorted(data['songs'], key=lambda s: s['title'].casefold())
    parts = []
    for s in songs:
        body = []
        for l in s.get('lyrics', '').split('\n'):
            if not l:
                body.append('<div class="gap"></div>')
            elif normalize_label(l) == l:
                body.append(f'<div class="label">{html.escape(l)}</div>')
            else:
                body.append(f'<div class="line">{html.escape(l)}</div>')
        # wie in der App: ohne Interpret steht der Songwriter vorne, ohne Beschriftung
        meta = ' · '.join(x for x in (s.get('performer') or s.get('writers'), s.get('year')) if x)
        images = ''.join(f'<img src="{src}" alt="Noten">' for src in s.get('scores') or [])
        parts.append(f'<section><h2>{html.escape(s["title"])}</h2>'
                     f'<div class="meta">{html.escape(meta)}</div>'
                     f'<div class="meta small">{"Songwriter: " + html.escape(s["writers"]) if s.get("writers") and s.get("performer") else ""}</div>'
                     + (f'<p><a href="{html.escape(s["link"])}" target="_blank">▶ Song spielen</a></p>' if s.get('link') else '')
                     + f'{images}<div class="lyrics">{"".join(body)}</div></section>')
    page = ('<!DOCTYPE html><html lang="de"><meta charset="utf-8"><title>Vorschau</title><style>'
            'body{font-family:-apple-system,sans-serif;background:#f4f6f7;color:#20313a;max-width:640px;margin:0 auto;padding:1rem}'
            'section{background:#fff;border:1px solid #dfe4e6;border-radius:.7rem;padding:1rem 1.2rem;margin-bottom:1rem}'
            'h2{margin:0 0 .15rem}.meta{color:#8b9aa2;font-size:.9rem}.small{font-size:.8rem;margin-bottom:1rem}'
            '.lyrics{font-size:1.08rem;line-height:1.55}.line{padding-left:1em;text-indent:-1em}.gap{height:.9em}'
            '.label{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#2a6a7a}'
            'img{display:block;width:100%;height:auto;border:1px solid #dfe4e6;border-radius:.4rem;margin-bottom:.8rem}'
            '</style>' + ''.join(parts) + '</html>')
    out = args.datei.parent / 'vorschau.html'
    out.write_text(page, encoding='utf-8')
    subprocess.run(['open', str(out)])
    print(f'Vorschau mit {len(songs)} Lied(ern) geöffnet: {out}')
    return False


def validate(data):
    problems = []
    ids = set()
    for s in data['songs']:
        if not s.get('id') or not s.get('title'):
            problems.append(f'Lied ohne id oder Titel: {s.get("title") or s.get("id") or "?"}')
        if s.get('id') in ids:
            problems.append(f'Doppelte id: {s["id"]}')
        ids.add(s.get('id'))
        if s.get('link') and not re.fullmatch(r'https://\S+', s['link']):
            problems.append(f'{song_line(s)}: Link muss mit https:// beginnen')
        if not s.get('lyrics') and not s.get('scores'):
            problems.append(f'{song_line(s)} hat weder Text noch Noten')
    for l in data['lists']:
        for i in l['songIds']:
            if i not in ids:
                problems.append(f'Liste "{l["name"]}" enthält unbekannte id {i}')
    return problems


def diff(old, new):
    old_songs = {s['id']: s for s in old.get('songs', [])}
    new_songs = {s['id']: s for s in new['songs']}
    added = [new_songs[i] for i in new_songs if i not in old_songs]
    removed = [old_songs[i] for i in old_songs if i not in new_songs]
    changed = [new_songs[i] for i in new_songs if i in old_songs and new_songs[i] != old_songs[i]]
    old_lists = {l['id']: l for l in old.get('lists', [])}
    lists = []
    for l in new['lists']:
        if l['id'] not in old_lists:
            lists.append(f'neue Liste "{l["name"]}"')
        elif l != old_lists[l['id']]:
            lists.append(f'Liste "{l["name"]}" geändert')
    for i, l in old_lists.items():
        if i not in {x['id'] for x in new['lists']}:
            lists.append(f'Liste "{l["name"]}" entfernt')
    return added, changed, removed, lists


def export_order(path):
    """Sortierschlüssel für Versanddateien; ältere Namen ohne Uhrzeit zählen als 00:00."""
    m = re.fullmatch(r'familien-lieder-(\d{4}-\d{2}-\d{2})(?:-(\d{2}-\d{2}))?\.json', path.name)
    return (m.group(1), m.group(2) or '00-00') if m else ('', path.name)


def cmd_export(args, data):
    if not data['songs']:
        raise Fehler('Die Sammlung ist leer – erst Lieder hinzufügen.')
    problems = validate(data)
    if problems:
        raise Fehler('Die Sammlung hat Fehler, nichts exportiert:\n  ' + '\n  '.join(problems))
    send_dir = args.datei.parent / 'versand'
    send_dir.mkdir(parents=True, exist_ok=True)
    # Uhrzeit im Namen, damit mehrere Versände am selben Tag eigene Dateien bekommen
    target = send_dir / f'familien-lieder-{datetime.datetime.now():%Y-%m-%d-%H-%M}.json'
    previous = sorted((p for p in send_dir.glob('familien-lieder-*.json') if p != target), key=export_order)
    out = dict(data, created=today())
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'Export: {target} ({target.stat().st_size // 1024} KB)')
    print(f'Inhalt: {lieder(len(data["songs"]))}, {len(data["lists"])} Listen, Stand {today()}')
    if previous:
        old = json.loads(previous[-1].read_text(encoding='utf-8'))
        added, changed, removed, lists = diff(old, out)
        print(f'Seit dem letzten Versand ({previous[-1].name}):')
        if not (added or changed or removed or lists):
            print('  keine Änderungen')
        for label, items in (('neu', added), ('geändert', changed), ('entfernt', removed)):
            for s in items:
                print(f'  {label}: {song_line(s)}')
        for l in lists:
            print(f'  {l}')
    else:
        print('Erster Versand – bisher gibt es keine frühere Datei in privat/versand/.')
    return False


# ---------------------------------------------------------------- Ordner privat/data

# Ein Lied im Ordner = gleicher Dateiname mit .txt (Kopf + Text), .pdf (Noten), .mid (Stimmen).
# Varianten: Noten als Bild (name.png / name-noten.png), Stimmen einzeln (name-s/-a/-t/-b.mid).
DEFAULT_DATA = ROOT / 'privat' / 'data'
SCAN_EXT = {'.pdf', '.mid', '.txt', '.png', '.gif', '.jpg', '.jpeg'}
IMAGE_EXT = {'.png', '.gif', '.jpg', '.jpeg'}
IGNORE_DIRS = {'alt', 'mp3'}          # Ablage-Unterordner, keine Lieder
VOICE_TAIL = re.compile(r'-(s|a|t|b)$', re.I)


def state_path(args):
    return args.datei.parent / 'data-import.json'


def load_state(args):
    p = state_path(args)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def save_state(args, state):
    state_path(args).write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def scan_groups(daten):
    """Dateien unter privat/data nach Liedname gruppieren (Schlüssel: Unterordner/Name)."""
    groups = {}
    for f in sorted(daten.rglob('*')):
        if not f.is_file() or f.name.startswith('.') or f.suffix.lower() not in SCAN_EXT:
            continue
        rel_dir = f.parent.relative_to(daten)
        if any(part.lower() in IGNORE_DIRS for part in rel_dir.parts):
            continue
        stem, ext = f.stem, f.suffix.lower()
        kind = ext
        m = VOICE_TAIL.search(stem) if ext == '.mid' else None
        if m:
            stem, kind = stem[:m.start()], 'stimme'
        elif ext in IMAGE_EXT:
            stem, kind = (stem[:-6] if stem.endswith('-noten') else stem), 'bild'
        key = stem if str(rel_dir) == '.' else str(rel_dir / stem)
        key = unicodedata.normalize('NFC', key)   # macOS liefert Umlaute zerlegt (NFD)
        g = groups.setdefault(key, {'txt': None, 'pdf': None, 'mid': None, 'bild': [], 'stimmen': []})
        if kind in ('bild', 'stimme'):
            g['bild' if kind == 'bild' else 'stimmen'].append(f)
        else:
            g[ext[1:]] = f
    return groups


def group_files(g):
    return [f for f in (g['txt'], g['pdf'], g['mid']) if f] + g['bild'] + g['stimmen']


def file_hashes(g):
    import hashlib
    return {f.name: hashlib.sha1(f.read_bytes()).hexdigest() for f in group_files(g)}


def parse_song_txt(path):
    """Kopf: „Titel, Person, Jahr“ in der ersten Zeile (oder Titel / Jahr / Person in bis zu 3 Zeilen),
    danach eine Leerzeile und der Liedtext."""
    lines = path.read_text(encoding='utf-8').replace('\r\n', '\n').split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    head = []
    while lines and lines[0].strip():
        head.append(lines.pop(0).strip())
    if not head:
        raise Fehler(f'{path.name}: Datei ist leer.')
    first = head[0]
    for pattern, order in ((r'(.+),\s*([^,]+?),\s*(\d{4})', 'tpj'), (r'(.+),\s*(\d{4}),\s*([^,]+)', 'tjp'),
                           (r'(.+),\s*(\d{4})', 'tj')):
        m = re.fullmatch(pattern, first)
        if m:
            parts = dict(zip(order, m.groups()))
            title, person, year = parts['t'], parts.get('p', ''), parts['j']
            body = head[1:] + lines          # falls die Leerzeile nach dem Kopf fehlt
            break
    else:
        # Titel in Zeile 1, darunter „Person, Jahr“ (oder Person und Jahr in eigenen Zeilen)
        rest = [x.strip() for line in head[1:] for x in line.split(',') if x.strip()]
        years = [x for x in rest if re.fullmatch(r'\d{4}', x)]
        if 2 <= len(head) <= 3 and years:
            year, title = years[0], head[0]
            person = ', '.join(x for x in rest if x != year)
            body = lines
        else:
            raise Fehler(f'{path.name}: Kopfzeile nicht erkannt. Erwartet z.B. „Titel, Person, 1768“ '
                         'in der ersten Zeile, dann eine Leerzeile und den Text.')
    lyrics = '\n'.join(body).strip('\n')
    if not lyrics.strip():
        raise Fehler(f'{path.name}: kein Liedtext unter der Kopfzeile.')
    return title.strip().rstrip(','), person.strip(), year, lyrics


def cmd_scan(args, data):
    daten = args.daten
    if not daten.exists():
        raise Fehler(f'Ordner {daten} gibt es nicht.')
    state, groups = load_state(args), scan_groups(daten)
    neu, geaendert, unvollst, bekannt = [], [], [], 0
    for key, g in sorted(groups.items()):
        missing = [n for n, ok in (('.txt', g['txt']), ('.pdf', g['pdf'] or g['bild']), ('.mid', g['mid'] or g['stimmen']))
                   if not ok]
        if state.get(key, {}).get('ignoriert'):
            continue
        if key in state:
            old, cur = state[key].get('hashes', {}), file_hashes(g)
            changes = sorted(n for n in set(old) | set(cur) if old.get(n) != cur.get(n))
            if changes:
                geaendert.append(f'{key} → {state[key]["id"]}: ' + ', '.join(
                    f'{n} ({"neu" if n not in old else "entfernt" if n not in cur else "geändert"})' for n in changes))
            else:
                bekannt += 1
            continue
        if not g['txt'] and not g['pdf']:
            continue                          # z.B. lose MIDI-Datei – kein Lied
        if not g['txt']:
            unvollst.append(f'{key}: .txt fehlt')
            continue
        try:
            title, person, year, lyrics = parse_song_txt(g['txt'])
        except Fehler as err:
            unvollst.append(f'{key}: {err}')
            continue
        sid = slugify(title)
        hint = f' – ACHTUNG: id „{sid}“ gibt es schon ({song_line(find_song(data, sid))})' if find_song(data, sid) else ''
        neu.append(f'{key} → „{title}“ · {person or "ohne Person"} · {year}'
                   + (f' (fehlt: {", ".join(missing)})' if missing else '') + hint)
    print(f'Ordner {daten}: {len(groups)} Dateigruppen, {bekannt} schon eingelesen und unverändert')
    for label, items in (('NEU', neu), ('GEÄNDERT', geaendert), ('UNVOLLSTÄNDIG', unvollst)):
        for item in items:
            print(f'{label}: {item}')
    if not (neu or geaendert or unvollst):
        print('Nichts Neues.')
    return False


def cmd_aus_ordner(args, data):
    groups = scan_groups(args.daten)
    g = groups.get(args.gruppe)
    if not g:
        raise Fehler(f'Kein Lied „{args.gruppe}“ in {args.daten}. `scan` zeigt alle Namen.')
    if not g['txt']:
        raise Fehler(f'{args.gruppe}: .txt mit Titel und Text fehlt.')
    title, person, year, raw = parse_song_txt(g['txt'])
    state = load_state(args)
    sid = args.id or (state.get(args.gruppe, {}).get('id')) or slugify(title)
    existing = find_song(data, sid)
    if existing and not args.ersetzen:
        raise Fehler(f'Es gibt schon {song_line(existing)} (id {sid}). Mit --ersetzen aktualisieren.')
    # Eine Zeile, die nur aus einem Link besteht (z.B. Spotify), wird zum Link des Liedes
    urls = re.findall(r'^[ \t]*(https://\S+)[ \t]*$', raw, re.M)
    raw = re.sub(r'^[ \t]*https?://\S+[ \t]*$', '', raw, flags=re.M)
    lyrics, rep = clean_lyrics(raw, '')      # Kopfzeile ist schon abgetrennt – erste Liedzeile bleibt
    song = {'id': sid, 'title': title, 'writers': person, 'performer': '', 'year': year, 'lyrics': lyrics}

    if g['pdf']:
        song['scores'] = read_scores(g['pdf'])
    elif g['bild']:
        song['scores'] = [u for f in sorted(g['bild']) for u in read_scores(f)]
    elif existing and existing.get('scores'):
        song['scores'] = existing['scores']
    if g['mid']:
        try:
            voices = split_voices(g['mid'])
        except Fehler:
            voices = [read_voice(g['mid'], 'Alle')]   # einstimmige Datei: als eine Stimme
    elif g['stimmen']:
        voices = [read_voice(f) for f in g['stimmen']]
        order = {n: i for i, n in enumerate(VOICE_ORDER)}
        voices.sort(key=lambda v: order.get(v['name'], len(order)))
    else:
        voices = existing.get('voices') if existing else None
    if voices:
        song['voices'] = voices
    if urls:
        song['link'] = re.sub(r'\?si=\S*$', '', urls[0])   # Spotify-Tracking-Anhang weglassen
    elif existing and existing.get('link'):
        song['link'] = existing['link']

    total, _ = describe(lyrics)
    sizes = stanza_sizes(lyrics)
    status = 'Probelauf – nichts gespeichert' if args.probelauf else ('aktualisiert' if existing else 'neu')
    print(f'{song_line(song)} (id: {sid}) – {status}')
    print(f'Kopf: Titel „{title}“, Person „{person or "-"}“, Jahr {year}')
    print(f'Text: {total} Zeilen in {len(sizes)} {"Strophe" if len(sizes) == 1 else "Strophen"}: '
          + ', '.join(map(str, sizes)) + ' Zeilen')
    if max(sizes or [0]) > 12:
        print('HINWEIS: Ein Block hat mehr als 12 Zeilen ohne Leerzeile – vermutlich fehlen Leerzeilen zwischen den Strophen.')
    if rep['akkordzeilen'] or rep['fusszeilen'] or rep['sonstige']:
        print(f'Entfernt: {rep["akkordzeilen"]} Akkordzeilen, {len(rep["fusszeilen"])} Fußzeilen, {rep["sonstige"]} sonstige')
    print('Noten: ' + (scores_info(song) or 'keine'))
    print('Stimmen: ' + (voices_info(song) or 'keine'))
    if song.get('link'):
        print(f'Link: {song["link"]}' + ('' if urls else ' (beibehalten)'))
    others = [s for s in data['songs'] if s['id'] != sid and same_title(s['title'], title)]
    for s in others:
        print(f'ANDERE VERSION in der Sammlung: {song_line(s)} (id {s["id"]})')
    if args.probelauf:
        return False
    if existing:
        data['songs'][data['songs'].index(existing)] = song
    else:
        data['songs'].append(song)
    for name in args.liste or []:
        add_to_list(data, name, [sid])
        print(f'In Liste "{name}" aufgenommen')
    state[args.gruppe] = {'id': sid, 'hashes': file_hashes(g)}
    save_state(args, state)
    return True


def cmd_verknuepfen(args, data):
    """Vorhandenes Lied mit einer Dateigruppe verbinden (ohne neu einzulesen)."""
    s = require_song(data, args.id)
    g = scan_groups(args.daten).get(args.gruppe)
    if not g:
        raise Fehler(f'Kein Lied „{args.gruppe}“ in {args.daten}.')
    state = load_state(args)
    state[args.gruppe] = {'id': s['id'], 'hashes': file_hashes(g)}
    save_state(args, state)
    print(f'Verknüpft: {args.gruppe} → {song_line(s)}')
    return False


def cmd_ignorieren(args, data):
    """Dateigruppe beim Scan übergehen (z.B. Sammeldateien, die kein einzelnes Lied sind)."""
    state = load_state(args)
    state[args.gruppe] = {'ignoriert': True}
    save_state(args, state)
    print(f'Wird beim Scan übergangen: {args.gruppe}')
    return False


# ---------------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(description='Lieder-Sammlung der Lyrics-Liste pflegen.')
    p.add_argument('--datei', type=Path, default=DEFAULT_FILE, help='Sammlungsdatei (Standard: privat/familien-lieder.json)')
    p.add_argument('--daten', type=Path, default=DEFAULT_DATA, help='Ordner mit Lied-Dateien (Standard: privat/data)')
    sub = p.add_subparsers(dest='befehl', required=True)

    a = sub.add_parser('hinzufuegen', help='Lied aus der Zwischenablage aufnehmen')
    a.add_argument('--titel', required=True)
    a.add_argument('--songwriter')
    a.add_argument('--interpret')
    a.add_argument('--jahr')
    a.add_argument('--id', help='eigene id (Standard: aus Titel + Interpret)')
    a.add_argument('--liste', action='append', help='in diese Liste aufnehmen (mehrfach möglich)')
    a.add_argument('--ersetzen', action='store_true', help='vorhandenes Lied mit gleicher id überschreiben')
    a.add_argument('--probelauf', action='store_true', help='nur zeigen, was passieren würde')
    a.add_argument('--noten', action='append', metavar='BILD',
                   help='Noten anhängen: GIF/PNG/JPEG oder PDF (alle Seiten), mehrfach möglich')
    a.add_argument('--titelzeile-behalten', action='store_true',
                   help='erste Zeile nicht als Titelzeile entfernen, auch wenn sie dem Titel gleicht')
    a.add_argument('--ohne-version', action='store_true',
                   help='Interpret/Jahr dürfen fehlen (Text ohne bestimmte Aufnahme, z.B. Liederbuch)')
    a.add_argument('--text-datei', help='Text aus Datei statt Zwischenablage')
    a.add_argument('--link', help='Link zum Anhören (Spotify, YouTube, …), Knopf „Song spielen“ in der App')

    b = sub.add_parser('bearbeiten', help='Angaben eines Liedes ändern')
    b.add_argument('id')
    b.add_argument('--titel')
    b.add_argument('--songwriter')
    b.add_argument('--interpret')
    b.add_argument('--jahr')
    b.add_argument('--link', help='Link zum Anhören setzen; --link "" entfernt ihn')

    e = sub.add_parser('entfernen', help='Lied löschen')
    e.add_argument('id')

    l = sub.add_parser('liste', help='Liste bearbeiten (wird bei Bedarf angelegt)')
    l.add_argument('name')
    l.add_argument('--hinzufuegen', nargs='+', metavar='ID')
    l.add_argument('--entfernen', nargs='+', metavar='ID')
    l.add_argument('--loeschen', action='store_true', help='ganze Liste löschen')

    n = sub.add_parser('noten', help='Notenbilder eines Liedes setzen oder entfernen')
    n.add_argument('id')
    n.add_argument('bilder', nargs='*', metavar='BILD')
    n.add_argument('--entfernen', action='store_true', help='Noten des Liedes entfernen')

    m = sub.add_parser('stimmen', help='MIDI-Dateien je Stimme setzen oder entfernen')
    m.add_argument('id')
    m.add_argument('dateien', nargs='*', metavar='MIDI',
                   help='MIDI-Dateien; Stimme aus dem Namensende: -s Sopran, -a Alt, -t Tenor, -b Bass')
    m.add_argument('--name', action='append', help='Stimmname je Datei in gleicher Reihenfolge (statt aus dem Dateinamen)')
    m.add_argument('--aufteilen', action='store_true',
                   help='eine mehrstimmige MIDI-Datei (eine Spur je Stimme, z.B. Taizé 4voix) in Stimmen aufteilen')
    m.add_argument('--entfernen', action='store_true', help='Stimmen des Liedes entfernen')

    sub.add_parser('scan', help='privat/data nach neuen oder geänderten Liedern durchsuchen')
    o = sub.add_parser('aus-ordner', help='Lied aus privat/data einlesen (.txt + .pdf + .mid)')
    o.add_argument('gruppe', help='Name wie von `scan` angezeigt, z.B. "taize/Ubi caritas"')
    o.add_argument('--liste', action='append', help='in diese Liste aufnehmen (mehrfach möglich)')
    o.add_argument('--ersetzen', action='store_true', help='vorhandenes Lied aktualisieren')
    o.add_argument('--id', help='eigene id (Standard: aus dem Titel)')
    o.add_argument('--probelauf', action='store_true', help='nur zeigen, was passieren würde')
    k = sub.add_parser('verknuepfen', help='vorhandenes Lied mit einer Dateigruppe verbinden')
    k.add_argument('gruppe')
    k.add_argument('id')
    i = sub.add_parser('ignorieren', help='Dateigruppe beim Scan übergehen')
    i.add_argument('gruppe')

    sub.add_parser('uebersicht', help='alle Lieder und Listen ohne Text')
    v = sub.add_parser('vorschau', help='formatierte Texte im Browser ansehen')
    v.add_argument('ids', nargs='*')
    sub.add_parser('export', help='Datei für den Versand erzeugen')

    args = p.parse_args(argv)
    if getattr(args, 'gruppe', None):
        args.gruppe = unicodedata.normalize('NFC', args.gruppe)
    commands = {'hinzufuegen': cmd_hinzufuegen, 'bearbeiten': cmd_bearbeiten, 'entfernen': cmd_entfernen,
                'liste': cmd_liste, 'noten': cmd_noten, 'stimmen': cmd_stimmen, 'scan': cmd_scan,
                'aus-ordner': cmd_aus_ordner, 'verknuepfen': cmd_verknuepfen, 'ignorieren': cmd_ignorieren, 'uebersicht': cmd_uebersicht, 'vorschau': cmd_vorschau, 'export': cmd_export}
    try:
        data = load(args.datei)
        if commands[args.befehl](args, data):
            save(args.datei, data)
            print(f'Gespeichert: {args.datei} ({lieder(len(data["songs"]))}, {len(data["lists"])} Listen)')
    except Fehler as err:
        print(f'FEHLER: {err}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
