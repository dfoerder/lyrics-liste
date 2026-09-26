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
  vorschau      Formatierte Texte als HTML im Browser öffnen
  export        Datei für den Versand erzeugen (privat/versand/…)
"""
import argparse
import datetime
import html
import json
import os
import re
import subprocess
import sys
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


def read_input(args):
    if args.text_datei:
        return Path(args.text_datei).read_text(encoding='utf-8')
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

    lyrics, rep = clean_lyrics(raw, args.titel)
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

    total, sections = describe(lyrics)
    status = 'Probelauf – nichts gespeichert' if args.probelauf else ('aktualisiert' if existing else 'neu')
    print(f'{song_line(song)} (id: {song_id}) – {status}')
    if song['writers']:
        print(f'Songwriter: {song["writers"]}')
    if sections and any(name != '(ohne Namen)' for name, _ in sections):
        print(f'Text: {total} Zeilen in {len(sections)} Abschnitten: '
              + ', '.join(f'{n} ({c if c else "Wiederholung"})' for n, c in sections))
    else:
        print(f'Text: {total} Zeilen, keine Abschnittsnamen erkannt')
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
    for l in rep['fusszeilen']:
        print(f'  Fußzeile: {l[:100]}')
    h = rep['hinweise']
    if h:
        print('Hinweise aus der Fußzeile: ' + '; '.join(f'{HINT_NAMES[k]}: {v}' for k, v in h.items()))
    if total < 4:
        print('WARNUNG: sehr kurzer Text – war wirklich der Liedtext in der Zwischenablage?')
    if duplicate:
        print(f'WARNUNG: identischer Text wie bei {song_line(duplicate)} – vermutlich wurde der neue Text nicht kopiert.')
    if not song['writers'] or not song['performer'] or not song['year']:
        missing = [n for n, k in (('Songwriter', 'writers'), ('Interpret', 'performer'), ('Jahr', 'year')) if not song[k]]
        print('Leer: ' + ', '.join(missing))

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
    print(f'Geändert: {song_line(s)}' + (f' | Songwriter: {s["writers"]}' if s['writers'] else ''))
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


def cmd_uebersicht(args, data):
    print(f'{lieder(len(data["songs"]))}, {len(data["lists"])} Listen (Stand {data.get("created", "?")})')
    for s in sorted(data['songs'], key=lambda s: s['title'].casefold()):
        total, _ = describe(s.get('lyrics', ''))
        lists = [l['name'] for l in data['lists'] if s['id'] in l['songIds']]
        print(f'  [{s["id"]}] {song_line(s)} | {s.get("writers") or "Songwriter fehlt"} | {total} Zeilen'
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
        meta = ' · '.join(x for x in (s.get('performer'), s.get('year')) if x)
        parts.append(f'<section><h2>{html.escape(s["title"])}</h2>'
                     f'<div class="meta">{html.escape(meta)}</div>'
                     f'<div class="meta small">{"Songwriter: " + html.escape(s["writers"]) if s.get("writers") else ""}</div>'
                     f'<div class="lyrics">{"".join(body)}</div></section>')
    page = ('<!DOCTYPE html><html lang="de"><meta charset="utf-8"><title>Vorschau</title><style>'
            'body{font-family:-apple-system,sans-serif;background:#f4f6f7;color:#20313a;max-width:640px;margin:0 auto;padding:1rem}'
            'section{background:#fff;border:1px solid #dfe4e6;border-radius:.7rem;padding:1rem 1.2rem;margin-bottom:1rem}'
            'h2{margin:0 0 .15rem}.meta{color:#8b9aa2;font-size:.9rem}.small{font-size:.8rem;margin-bottom:1rem}'
            '.lyrics{font-size:1.08rem;line-height:1.55}.line{padding-left:1em;text-indent:-1em}.gap{height:.9em}'
            '.label{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#2a6a7a}'
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
            problems.append(f'Lied ohne id oder Titel: {s}')
        if s.get('id') in ids:
            problems.append(f'Doppelte id: {s["id"]}')
        ids.add(s.get('id'))
        if not s.get('lyrics'):
            problems.append(f'{song_line(s)} hat keinen Text')
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


def cmd_export(args, data):
    if not data['songs']:
        raise Fehler('Die Sammlung ist leer – erst Lieder hinzufügen.')
    problems = validate(data)
    if problems:
        raise Fehler('Die Sammlung hat Fehler, nichts exportiert:\n  ' + '\n  '.join(problems))
    send_dir = args.datei.parent / 'versand'
    send_dir.mkdir(parents=True, exist_ok=True)
    target = send_dir / f'familien-lieder-{today()}.json'
    previous = sorted(p for p in send_dir.glob('familien-lieder-*.json') if p != target)
    out = dict(data, created=today())
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'Export: {target}')
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


# ---------------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(description='Lieder-Sammlung der Lyrics-Liste pflegen.')
    p.add_argument('--datei', type=Path, default=DEFAULT_FILE, help='Sammlungsdatei (Standard: privat/familien-lieder.json)')
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
    a.add_argument('--text-datei', help='Text aus Datei statt Zwischenablage')

    b = sub.add_parser('bearbeiten', help='Angaben eines Liedes ändern')
    b.add_argument('id')
    b.add_argument('--titel')
    b.add_argument('--songwriter')
    b.add_argument('--interpret')
    b.add_argument('--jahr')

    e = sub.add_parser('entfernen', help='Lied löschen')
    e.add_argument('id')

    l = sub.add_parser('liste', help='Liste bearbeiten (wird bei Bedarf angelegt)')
    l.add_argument('name')
    l.add_argument('--hinzufuegen', nargs='+', metavar='ID')
    l.add_argument('--entfernen', nargs='+', metavar='ID')
    l.add_argument('--loeschen', action='store_true', help='ganze Liste löschen')

    sub.add_parser('uebersicht', help='alle Lieder und Listen ohne Text')
    v = sub.add_parser('vorschau', help='formatierte Texte im Browser ansehen')
    v.add_argument('ids', nargs='*')
    sub.add_parser('export', help='Datei für den Versand erzeugen')

    args = p.parse_args(argv)
    commands = {'hinzufuegen': cmd_hinzufuegen, 'bearbeiten': cmd_bearbeiten, 'entfernen': cmd_entfernen,
                'liste': cmd_liste, 'uebersicht': cmd_uebersicht, 'vorschau': cmd_vorschau, 'export': cmd_export}
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
