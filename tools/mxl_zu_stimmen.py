#!/usr/bin/env python3
"""MusicXML/MXL (z.B. aus Audiveris) in eine .stimmen-Notation für midi_schreiben.py umwandeln.

Aufruf: python3 tools/mxl_zu_stimmen.py <datei.mxl|.musicxml> [ziel.stimmen]

Takt für Takt: über Zeilenumbrüche geteilte Takte werden zusammengeführt, verirrte
Töne aus einer dritten Stimme der Stimme mit Lücke angehängt. Ist eine Stimme zu kurz
(z.B. fehlende Pause), wird sie am Rhythmus einer vollständigen Stimme ausgerichtet;
geht das nicht, kommt eine Pause an den Taktanfang und eine PRÜFEN-Meldung – dort fehlt
meist ein Ton.

Zuordnung: 2 Systeme mit je 2 Stimmen (oder zwei Stimmen als Akkorde) → Sopran/Alt oben,
Tenor/Bass unten; 4 Systeme mit je einer Stimme → Sopran, Alt, Tenor, Bass.
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

STEP = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
KEYS = {0: 'C', 1: 'G', 2: 'D', 3: 'A', 4: 'E', -1: 'F', -2: 'Bb', -3: 'Eb', -4: 'Ab'}
SATB = ['Sopran', 'Alt', 'Tenor', 'Bass']


def load_xml(path):
    p = Path(path)
    if p.suffix.lower() == '.mxl':
        z = zipfile.ZipFile(p)
        name = next(n for n in z.namelist() if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
        return ET.fromstring(z.read(name))
    return ET.parse(p).getroot()


def note_name(midi):
    return NAMES[midi % 12] + str(midi // 12 - 1)


def read_measures(root):
    """Je Teil: Liste von Takten; je Takt {stimme: [(dauer, [midi…] | None)]} in Reihenfolge."""
    meta, parts = {'beats': 4, 'beat_type': 4, 'fifths': None}, []
    for part in root.findall('part'):
        div, measures = 1, []
        for m in part.findall('measure'):
            voices = {}
            for el in m:
                if el.tag == 'attributes':
                    if el.find('divisions') is not None:
                        div = int(el.findtext('divisions'))
                    if el.find('time/beats') is not None:
                        meta['beats'], meta['beat_type'] = int(el.findtext('time/beats')), int(el.findtext('time/beat-type'))
                    if el.find('key/fifths') is not None:
                        meta['fifths'] = int(el.findtext('key/fifths'))
                elif el.tag == 'note' and el.find('grace') is None:
                    v = el.findtext('voice', '1')
                    if el.find('rest') is not None:
                        midi = None
                    else:
                        pi = el.find('pitch')
                        midi = 12 * (int(pi.findtext('octave')) + 1) + STEP[pi.findtext('step')] + int(float(pi.findtext('alter') or 0))
                    seq = voices.setdefault(v, [])
                    if el.find('chord') is not None and seq and seq[-1][1] is not None and midi is not None:
                        seq[-1][1].append(midi)          # Akkord in derselben Stimme
                    else:
                        seq.append((Fraction(int(el.findtext('duration', '0')), div), None if midi is None else [midi]))
            measures.append(voices)
        parts.append(measures)
    return meta, parts


def total(seq):
    return sum(d for d, _ in seq)


def to_satb(meta, parts):
    """→ Liste von Takten; je Takt {Stimmname: [(dauer, midi|None)]}; Meldungen werden gedruckt."""
    n = max(len(p) for p in parts)
    bar = Fraction(meta['beats'] * 4, meta['beat_type'])
    rows = []                                        # je Audiveris-Takt: {Stimmname: seq}
    for i in range(n):
        row = {}
        names = iter(SATB)
        for p in parts:
            voices = p[i] if i < len(p) else {}
            ids = sorted(voices, key=int)
            main, stray = ids[:2], ids[2:]
            if len(parts) == 4:
                main, stray = ids[:1], ids[1:]
            if len(parts) != 4 and len(main) == 1 and any(c and len(c) > 1 for _, c in voices[main[0]]):
                seq = voices[main[0]]                # zwei Stimmen als Akkorde in einer Stimme
                row[next(names)] = [(d, None if c is None else max(c)) for d, c in seq]
                row[next(names)] = [(d, None if c is None else min(c)) for d, c in seq]
            else:
                for k in range(1 if len(parts) == 4 else 2):
                    seq = voices.get(main[k], []) if k < len(main) else []
                    row[next(names)] = [(d, None if c is None else c[0]) for d, c in seq]
            local = list(row)[-(1 if len(parts) == 4 else 2):]
            for v in stray:                          # verirrte Töne der Stimme mit Lücke anhängen
                for d, c in voices[v]:
                    if c is None:
                        continue
                    short = [x for x in local if total(row[x]) + d <= bar]
                    # Vorrang: Stimme, die ihre Pause schon hat und der der Ton fehlt;
                    # sonst die tonlich nächste Stimme
                    def rank(x):
                        has_rest = any(m is None for _, m in row[x])
                        last = next((m for _, m in reversed(row[x]) if m is not None), c[0])
                        return (not has_rest, abs(last - c[0]))
                    target = min(short, key=rank) if short else None
                    if target:
                        row[target].append((d, c[0]))
                        print(f'Audiveris-Takt {i + 1}: verirrter Ton {note_name(c[0])} → {target}')
        rows.append(row)

    lengths = [max(total(seq) for seq in r.values()) for r in rows]
    bars, cur, cur_len = [], None, Fraction(0)
    for i, (r, ln) in enumerate(zip(rows, lengths)):
        if cur is not None and cur_len < bar and cur_len + ln <= bar:
            for k in cur:
                cur[k] = cur[k] + r[k]               # geteilten Takt zusammenführen
            cur_len += ln
            continue
        if cur is not None:
            bars.append((cur, cur_len))
        cur, cur_len = {k: list(v) for k, v in r.items()}, ln
    bars.append((cur, cur_len))
    return bars, bar


def repair(bars, bar):
    """Zu kurze Stimmen am Rhythmus einer vollständigen Stimme ausrichten, Rest melden."""
    out = []
    for i, (row, ln) in enumerate(bars):
        target = bar if 0 < i < len(bars) - 1 else ln       # Auftakt/Schluss: längste Stimme
        nr = i if bars[0][1] < bar else i + 1                  # Taktnummer (Auftakt = 0)
        for name, seq in row.items():
            have = total(seq)
            if have == target:
                continue
            if have > target:
                print(f'PRÜFEN: Takt {nr}, {name} ist zu lang ({float(have):g} statt {float(target):g} Viertel)')
                continue
            missing = target - have
            fixed = None
            for ref in row.values():                            # gleiche Rhythmik + eine Pause?
                if total(ref) != target:
                    continue
                t = Fraction(0)
                for d, m in ref:
                    if m is None and d == missing:
                        cand, u = [], Fraction(0)
                        for dd, mm in seq:
                            if u == t:
                                cand.append((d, None))
                            cand.append((dd, mm))
                            u += dd
                        if u == t:
                            cand.append((d, None))
                        if [x[0] for x in cand] == [x[0] for x in ref]:
                            fixed = cand
                        break
                    t += d
                if fixed:
                    break
            if fixed:
                row[name] = fixed
                print(f'Pause ergänzt: Takt {nr}, {name} (wie die anderen Stimmen)')
            else:
                row[name] = [(missing, None)] + seq
                print(f'PRÜFEN: Takt {nr}, {name} fehlen {float(missing):g} Viertel – Pause am Taktanfang eingesetzt; '
                      'dort fehlt vermutlich ein Ton (im Raster nachsehen)')
        out.append(row)
    return out


def fmt(d, m):
    tok = '-' if m is None else note_name(m)
    if d != 1:
        tok += ':' + (str(d.numerator) if d.denominator == 1 else f'{float(d):g}')
    return tok


def main(src, dst=None):
    root = load_xml(src)
    meta, parts = read_measures(root)
    if len(parts) not in (1, 2, 4):
        raise SystemExit(f'{len(parts)} Systeme – erwartet 2 (Violin + Bass) oder 4 (je Stimme).')
    bars, bar = to_satb(meta, parts)
    rows = repair(bars, bar)
    names = list(rows[0])
    title = root.findtext('work/work-title') or root.findtext('movement-title') or Path(src).stem
    head = [f'# Aus {Path(src).name} (Notenerkennung) – Meldungen mit PRÜFEN im Raster nachsehen.',
            f'titel: {title}', 'tempo: 84', f'takt: {meta["beats"]}/{meta["beat_type"]}']
    if meta['fifths'] in KEYS:
        head.append(f'tonart: {KEYS[meta["fifths"]]}')
    lines = [f'{n + ":":7} ' + ' | '.join(' '.join(fmt(d, m) for d, m in r[n]) for r in rows) for n in names]
    dst = Path(dst) if dst else Path(src).with_suffix('.stimmen')
    dst.write_text('\n'.join(head + lines) + '\n', encoding='utf-8')
    pick = bars[0][1] < bar
    print(f'{dst.name}: {len(names)} Stimmen ({", ".join(names)}), {len(rows)} Takte'
          + (f' inkl. Auftakt ({float(bars[0][1]):g} Viertel)' if pick else ''))


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
