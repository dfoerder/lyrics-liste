#!/usr/bin/env python3
"""Stimmen-Notation (.stimmen, siehe midi_schreiben.py) als MusicXML ausgeben.

Aufruf: python3 tools/stimmen_zu_musicxml.py <name>.stimmen   →  schreibt <name>.musicxml daneben
        python3 tools/stimmen_zu_musicxml.py <name>.stimmen --chorsatz  →  <name>.chorsatz.musicxml
        (2 Systeme wie im Gesangbuch: Sopran/Alt oben, Tenor/Bass unten – für die App)

Je Stimme eine Partie (Sopran, Alt, Tenor mit oktaviertem Violinschlüssel, Bass), mit Tonart,
Taktart und Auftakt. Dauern, die keine einfache Notenlänge sind, werden in übergebundene Noten
zerlegt. Die Datei lässt sich in MuseScore, Sibelius, Finale o.ä. öffnen. Liedtext ist nicht dabei.

write_score() wird auch von midi_zu_musicxml.py benutzt.
"""
import re
import sys
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).parent))
from midi_schreiben import parse  # noqa: E402

DIV = 24                                  # Teilungen je Viertel (16tel und Triolen ganzzahlig)
KEYS = {'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4}
# Dauer in Vierteln → (Notentyp, Punkte, Triole)
TYPES = [(Fraction(4), 'whole', 0, False), (Fraction(3), 'half', 1, False), (Fraction(2), 'half', 0, False),
         (Fraction(3, 2), 'quarter', 1, False), (Fraction(4, 3), 'half', 0, True), (Fraction(1), 'quarter', 0, False),
         (Fraction(3, 4), 'eighth', 1, False), (Fraction(2, 3), 'quarter', 0, True), (Fraction(1, 2), 'eighth', 0, False),
         (Fraction(3, 8), '16th', 1, False), (Fraction(1, 3), 'eighth', 0, True), (Fraction(1, 4), '16th', 0, False),
         (Fraction(1, 6), '16th', 0, True), (Fraction(1, 8), '32nd', 0, False), (Fraction(1, 12), '32nd', 0, True)]
STEP_NAMES = {'H': 'B'}


def split_duration(d):
    """Dauer in möglichst wenige darstellbare Stücke zerlegen (größte zuerst).
    Nicht gierig: 5/12 wird zu 1/3 + 1/12, nicht zu 3/8 + (nicht darstellbaren) 1/24."""
    units = d * DIV
    if units.denominator != 1:
        raise SystemExit(f'Dauer {d} lässt sich nicht darstellen')
    n = int(units)
    sizes = [(int(item[0] * DIV), item) for item in TYPES]
    best = [None] * (n + 1)
    best[0] = []
    for u in range(1, n + 1):
        for size, item in sizes:
            if size <= u and best[u - size] is not None:
                cand = best[u - size] + [item]
                if best[u] is None or len(cand) < len(best[u]):
                    best[u] = cand
    if best[n] is None:
        raise SystemExit(f'Dauer {d} lässt sich nicht darstellen')
    return sorted(best[n], key=lambda item: -item[0])


def clef_for(name, pitches):
    """Schlüssel aus dem Stimmnamen, sonst aus der mittleren Tonhöhe."""
    n = name.lower()
    if n.startswith('sopran') or n.startswith('alt'):
        return ('G', 2, 0)
    if n.startswith('tenor'):
        return ('G', 2, -1)
    if n.startswith('bass'):
        return ('F', 4, 0)
    if not pitches:
        return ('G', 2, 0)
    avg = sum(pitches) / len(pitches)
    return ('F', 4, 0) if avg < 55 else ('G', 2, -1) if avg < 62 else ('G', 2, 0)


def pitch_xml(tok):
    m = re.fullmatch(r'([A-H])(b|#)?(-?\d)', tok)
    step = STEP_NAMES.get(m.group(1), m.group(1))
    alter = {'b': -1, '#': 1, None: 0}[m.group(2)]
    return (f'<pitch><step>{step}</step>' + (f'<alter>{alter}</alter>' if alter else '')
            + f'<octave>{m.group(3)}</octave></pitch>')


def midi_number(tok):
    m = re.fullmatch(r'([A-H])(b|#)?(-?\d)', tok)
    return 12 * (int(m.group(3)) + 1) + {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11, 'H': 11}[m.group(1)] \
        + {'b': -1, '#': 1, None: 0}[m.group(2)]


def emit_notes(out, bar, tied_in, voice=None, stem=None):
    """Noten eines Takts als <note>-Elemente anhängen; gibt zurück, ob die letzte Note übergebunden ist."""
    for toks, d, tie_next in bar:
        pieces = split_duration(Fraction(d))
        for k, (length, typ, dots, triplet) in enumerate(pieces):
            ties = []
            if toks and (tied_in or k > 0):
                ties.append('stop')
            if toks and (k < len(pieces) - 1 or tie_next):
                ties.append('start')
            tm = '<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>' if triplet else ''
            for c, tok in enumerate(toks or [None]):
                body = ('<chord/>' if c else '') + ('<rest/>' if tok is None else pitch_xml(tok))
                out.append('<note>' + body + f'<duration>{int(length * DIV)}</duration>'
                           + ''.join(f'<tie type="{t}"/>' for t in ties)
                           + (f'<voice>{voice}</voice>' if voice else '')
                           + f'<type>{typ}</type>' + '<dot/>' * dots + tm
                           + (f'<stem>{stem}</stem>' if stem and tok is not None else '')
                           + (('<notations>' + ''.join(f'<tied type="{t}"/>' for t in ties) + '</notations>') if ties else '')
                           + '</note>')
            tied_in = False
        tied_in = bool(toks) and tie_next
    return tied_in


def write_choral(target, title, parts, times, fifths=0, tempo=None, pickup=False):
    """Chorsatz wie im Gesangbuch: zwei Systeme – Sopran/Alt im Violin-, Tenor/Bass im Bassschlüssel,
    je zwei Stimmen (Hals nach oben/unten). parts braucht Sopran, Alt, Tenor, Bass."""
    staves = [('Sopran', 'Alt', ('G', 2)), ('Tenor', 'Bass', ('F', 4))]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
           '"http://www.musicxml.org/dtds/partwise.dtd">',
           '<score-partwise version="4.0">',
           f'<work><work-title>{escape(title)}</work-title></work>',
           '<part-list>']
    for i, (a, b, _) in enumerate(staves, 1):
        out.append(f'<score-part id="P{i}"><part-name>{a}/{b}</part-name>'
                   f'<score-instrument id="P{i}-I1"><instrument-name>Choir Aahs</instrument-name></score-instrument>'
                   f'<midi-instrument id="P{i}-I1"><midi-channel>{i}</midi-channel><midi-program>53</midi-program></midi-instrument>'
                   '</score-part>')
    out.append('</part-list>')
    nbars = len(parts['Sopran'])
    for i, (upper, lower, (sign, line)) in enumerate(staves, 1):
        out.append(f'<part id="P{i}">')
        tied = {upper: False, lower: False}
        for b in range(nbars):
            number = b if pickup else b + 1
            implicit = ' implicit="yes"' if pickup and b == 0 else ''
            out.append(f'<measure number="{number}"{implicit}>')
            attrs = ''
            if b == 0:
                attrs += f'<divisions>{DIV}</divisions><key><fifths>{fifths}</fifths></key>'
            if b == 0 or times[b] != times[b - 1]:
                attrs += f'<time><beats>{times[b][0]}</beats><beat-type>{times[b][1]}</beat-type></time>'
            if b == 0:
                attrs += f'<clef><sign>{sign}</sign><line>{line}</line></clef>'
            if attrs:
                out.append(f'<attributes>{attrs}</attributes>')
            if b == 0 and tempo and i == 1:
                out.append(f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
                           f'<per-minute>{tempo:g}</per-minute></metronome></direction-type>'
                           f'<sound tempo="{tempo:g}"/></direction>')
            tied[upper] = emit_notes(out, parts[upper][b], tied[upper], 1, 'up')
            length = sum(Fraction(d) for _, d, _ in parts[upper][b])
            out.append(f'<backup><duration>{int(length * DIV)}</duration></backup>')
            tied[lower] = emit_notes(out, parts[lower][b], tied[lower], 2, 'down')
            if b == nbars - 1:
                out.append('<barline location="right"><bar-style>light-heavy</bar-style></barline>')
            out.append('</measure>')
        out.append('</part>')
    out.append('</score-partwise>')
    Path(target).write_text('\n'.join(out) + '\n', encoding='utf-8')


def write_score(target, title, parts, times, fifths=0, tempo=None, pickup=False):
    """parts: {Name: [Takt: [(Töne|None, Dauer in Vierteln, gebunden_zum_nächsten)]]}
    times: je Takt (Zähler, Nenner). Töne = Liste von Tonnamen wie 'F#4' (mehrere = Akkord)."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
           '"http://www.musicxml.org/dtds/partwise.dtd">',
           '<score-partwise version="4.0">',
           f'<work><work-title>{escape(title)}</work-title></work>',
           '<part-list>']
    names = list(parts)
    for i, n in enumerate(names, 1):
        out.append(f'<score-part id="P{i}"><part-name>{escape(n)}</part-name>'
                   f'<score-instrument id="P{i}-I1"><instrument-name>Choir Aahs</instrument-name></score-instrument>'
                   f'<midi-instrument id="P{i}-I1"><midi-channel>{i}</midi-channel><midi-program>53</midi-program></midi-instrument>'
                   '</score-part>')
    out.append('</part-list>')
    for i, n in enumerate(names, 1):
        measures = parts[n]
        pitches = [midi_number(t) for bar in measures for toks, _, _ in bar if toks for t in toks]
        sign, line, octave = clef_for(n, pitches)
        out.append(f'<part id="P{i}">')
        tied_in = False
        for b, bar in enumerate(measures):
            number = b if pickup else b + 1
            implicit = ' implicit="yes"' if pickup and b == 0 else ''
            out.append(f'<measure number="{number}"{implicit}>')
            attrs = ''
            if b == 0:
                attrs += f'<divisions>{DIV}</divisions><key><fifths>{fifths}</fifths></key>'
            if b == 0 or times[b] != times[b - 1]:
                attrs += f'<time><beats>{times[b][0]}</beats><beat-type>{times[b][1]}</beat-type></time>'
            if b == 0:
                attrs += (f'<clef><sign>{sign}</sign><line>{line}</line>'
                          + (f'<clef-octave-change>{octave}</clef-octave-change>' if octave else '') + '</clef>')
            if attrs:
                out.append(f'<attributes>{attrs}</attributes>')
            if b == 0 and tempo and i == 1:
                out.append(f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
                           f'<per-minute>{tempo:g}</per-minute></metronome></direction-type>'
                           f'<sound tempo="{tempo:g}"/></direction>')
            tied_in = emit_notes(out, bar, tied_in)
            if b == len(measures) - 1:
                out.append('<barline location="right"><bar-style>light-heavy</bar-style></barline>')
            out.append('</measure>')
        out.append('</part>')
    out.append('</score-partwise>')
    Path(target).write_text('\n'.join(out) + '\n', encoding='utf-8')


def tokens(path):
    """Wie midi_schreiben.parse, aber mit den Original-Tonnamen (für die Schreibweise #/b)."""
    voices = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.lstrip().startswith('#') or ':' not in line:
            continue
        key, val = (x.strip() for x in line.split(':', 1))
        if key.lower() in ('titel', 'tempo', 'takt', 'tonart'):
            continue
        voices[key] = [[(t.partition(':')[0], Fraction(t.partition(':')[2] or '1')) for t in bar.split()]
                       for bar in val.split('|')]
    return voices


def main(path, choral=False):
    meta, _ = parse(path)                  # prüft nebenbei die Notation
    voices = tokens(path)
    num, den = (int(x) for x in meta.get('takt', '4/4').split('/'))
    bar_len = Fraction(num * 4, den)
    names = list(voices)
    parts = {n: [[(None if t == '-' else [t], d, False) for t, d in bar] for bar in voices[n]] for n in names}
    nbars = len(voices[names[0]])
    pickup = sum(d for _, d in voices[names[0]][0]) < bar_len
    args = (meta.get('titel', Path(path).stem), parts, [(num, den)] * nbars,
            KEYS.get(meta.get('tonart', 'C'), 0), float(meta['tempo']) if meta.get('tempo') else None, pickup)
    if choral:
        if set(names) != {'Sopran', 'Alt', 'Tenor', 'Bass'}:
            raise SystemExit('Chorsatz braucht genau die Stimmen Sopran, Alt, Tenor, Bass.')
        target = Path(path).with_suffix('.chorsatz.musicxml')
        write_choral(target, *args)
        print(f'{target.name}: Chorsatz (2 Systeme: Sopran/Alt, Tenor/Bass), {nbars} Takte')
        return
    target = Path(path).with_suffix('.musicxml')
    write_score(target, *args)
    print(f'{target.name}: {len(names)} Stimmen ({", ".join(names)}), {nbars} Takte'
          + (' inkl. Auftakt' if pickup else '') + f', {num}/{den}, Tonart {meta.get("tonart", "C")}')


if __name__ == '__main__':
    argv = [a for a in sys.argv[1:] if a != '--chorsatz']
    if len(argv) != 1:
        raise SystemExit(__doc__)
    main(argv[0], choral='--chorsatz' in sys.argv)
