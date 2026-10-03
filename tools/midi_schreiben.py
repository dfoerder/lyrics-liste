#!/usr/bin/env python3
"""Mehrstimmige MIDI-Datei (eine Spur je Stimme) aus einer einfachen Textnotation schreiben.

Aufruf: python3 tools/midi_schreiben.py <name>.stimmen   →  schreibt <name>.mid daneben

Notation (.stimmen), Takte mit „|“ getrennt, Dauer in Schlägen nach „:“ (ohne = 1),
Pause „-“, Vorzeichen „b“/„#“ (Bb3, F#4). Die Tonart steht nur als Information in der
Datei – Vorzeichen werden immer ausgeschrieben:

    titel: Der Mond ist aufgegangen
    tempo: 84
    takt: 4/4
    tonart: F
    Sopran: F4 | G4 F4 Bb4 A4 | G4:2 F4 A4 | …
    Alt:    C4 | E4 F4 E4 F4 | E4:2 F4 F4 | …
    Tenor:  …
    Bass:   …

Alle Stimmen müssen je Takt gleich lang sein; das wird geprüft.
"""
import re
import struct
import sys
from pathlib import Path

STEPS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11, 'H': 11}
TRACK_NAMES = {'sopran': 'Soprano', 'alt': 'Alto', 'tenor': 'Tenor', 'bass': 'Bass'}
TPQ = 480
KEYS = {'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4}


def pitch(token):
    m = re.fullmatch(r'([A-H])(b|#)?(-?\d)', token)
    if not m:
        raise SystemExit(f'Unbekannter Ton: {token}')
    n = STEPS[m.group(1)] + {'b': -1, '#': 1, None: 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + n


def parse(path):
    meta, voices = {}, {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0] if line.lstrip().startswith('#') else line
        if ':' not in line:
            continue
        key, val = (x.strip() for x in line.split(':', 1))
        if key.lower() in ('titel', 'tempo', 'takt', 'tonart'):
            meta[key.lower()] = val
            continue
        bars = []
        for bar in val.split('|'):
            notes = []
            for tok in bar.split():
                ton, _, dauer = tok.partition(':')
                notes.append((None if ton == '-' else pitch(ton), float(dauer or 1)))
            bars.append(notes)
        voices[key] = bars
    return meta, voices


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def track(events):
    events.sort(key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90))   # note-off vor note-on
    data, last = b'', 0
    for t, ev in events:
        data += vlq(t - last) + ev
        last = t
    data += b'\x00\xFF\x2F\x00'
    return b'MTrk' + struct.pack('>I', len(data)) + data


def text_event(text):
    raw = text.encode('utf-8')
    return b'\xFF\x03' + vlq(len(raw)) + raw


def main(path):
    meta, voices = parse(path)
    if not voices:
        raise SystemExit('Keine Stimmen gefunden.')
    lengths = {name: [sum(d for _, d in bar) for bar in bars] for name, bars in voices.items()}
    ref_name, ref = next(iter(lengths.items()))
    for name, lens in lengths.items():
        if len(lens) != len(ref):
            raise SystemExit(f'{name}: {len(lens)} Takte, {ref_name}: {len(ref)} Takte')
        for i, (a, b) in enumerate(zip(lens, ref)):
            if abs(a - b) > 1e-9:
                raise SystemExit(f'Takt {i + 1}: {name} hat {a} Schläge, {ref_name} {b}')
    bpm = float(meta.get('tempo', 80))
    num, den = (int(x) for x in meta.get('takt', '4/4').split('/'))
    cond = [(0, text_event(meta.get('titel', Path(path).stem))),
            (0, b'\xFF\x51\x03' + struct.pack('>I', int(60000000 // bpm))[1:]),
            (0, b'\xFF\x58\x04' + bytes([num, den.bit_length() - 1, 24, 8]))]
    if meta.get('tonart') in KEYS:
        cond.append((0, b'\xFF\x59\x02' + struct.pack('b', KEYS[meta['tonart']]) + b'\x00'))
    tracks = [track(cond)]
    for ch, (name, bars) in enumerate(voices.items()):
        ev, t = [(0, text_event(TRACK_NAMES.get(name.lower(), name))), (0, bytes([0xC0 | ch, 52]))], 0
        for bar in bars:
            for p, d in bar:
                dur = int(round(d * TPQ))
                if p is not None:
                    ev.append((t, bytes([0x90 | ch, p, 80])))
                    ev.append((t + int(dur * 0.95), bytes([0x80 | ch, p, 0])))
                t += dur
        tracks.append(track(ev))
    out = Path(path).with_suffix('.mid')
    out.write_bytes(b'MThd' + struct.pack('>IHHH', 6, 1, len(tracks), TPQ) + b''.join(tracks))
    print(f'{out.name}: {len(voices)} Stimmen ({", ".join(voices)}), {len(ref)} Takte, Tempo {bpm:g}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
