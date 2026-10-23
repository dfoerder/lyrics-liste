#!/usr/bin/env python3
"""MIDI-Datei(en) als MusicXML-Partitur ausgeben (je Stimmspur eine Partie).

Aufruf: python3 tools/midi_zu_musicxml.py <datei.mid> [<datei2.mid> …] [--ziel <name>.musicxml]

Eine mehrstimmige Datei (Format 1, eine Spur je Stimme, z.B. die Taizé-MIDIs) wird zu einer
Partitur. Mehrere Dateien (z.B. name-s/-a/-t/-b.mid) werden zu einer Partitur zusammengeführt;
das Ziel heißt dann wie die Dateien ohne Stimmkürzel.

Eingespielte MIDIs sind nicht taktgenau: Einsätze werden auf ein Raster von 1/12 Viertel gerückt
(16tel und Triolen), kleine Lücken vor dem nächsten Ton (Artikulation) werden geschlossen, echte
Pausen bleiben. Tonart, Taktart(wechsel) und Tempo kommen aus der Datei. Ohne Liedtext.
"""
import re
import struct
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stimmen_zu_musicxml import write_score  # noqa: E402

SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLATS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
SUFFIX = {'s': 'Sopran', 'a': 'Alt', 't': 'Tenor', 'b': 'Bass'}


def voice_name(raw, fallback):
    l = (raw or '').strip().lower()
    if l.startswith('sopran'):
        return 'Sopran'
    if l.startswith('alt'):
        return 'Alt'
    if l.startswith('tenor'):
        return 'Tenor'
    if l.startswith('bass') or l.startswith('base'):
        return 'Bass'
    m = re.match(r'voice\s*(\d+)', l)
    if m:
        return 'Stimme ' + m.group(1)
    return (raw or '').strip() or fallback


def vlq(b, p):
    v = 0
    while True:
        c = b[p]
        p += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def read_midi(path):
    b = Path(path).read_bytes()
    if b[:4] != b'MThd':
        raise SystemExit(f'{path}: keine MIDI-Datei')
    _, _, div = struct.unpack('>HHH', b[8:14])
    if div & 0x8000:
        raise SystemExit(f'{path}: SMPTE-Zeit wird nicht unterstützt')
    p = 8 + struct.unpack('>I', b[4:8])[0]
    meta = {'times': [], 'fifths': None, 'tempo': None}
    tracks = []
    while p + 8 <= len(b):
        ln = struct.unpack('>I', b[p + 4:p + 8])[0]
        data, p = b[p + 8:p + 8 + ln], p + 8 + ln
        q = t = status = 0
        name, notes, open_ = '', [], {}
        while q < len(data):
            d, q = vlq(data, q)
            t += d
            c = data[q]
            if c == 0xFF:
                typ = data[q + 1]
                l, q2 = vlq(data, q + 2)
                val, q = data[q2:q2 + l], q2 + l
                if typ == 0x03 and not name:
                    name = val.decode('latin-1')
                elif typ == 0x58:
                    meta['times'].append((t, val[0], 2 ** val[1]))
                elif typ == 0x59 and meta['fifths'] is None:
                    meta['fifths'] = struct.unpack('b', val[:1])[0]
                elif typ == 0x51 and meta['tempo'] is None:
                    meta['tempo'] = round(60_000_000 / int.from_bytes(val, 'big'))
                continue
            if c in (0xF0, 0xF7):
                l, q = vlq(data, q + 1)
                q += l
                continue
            if c & 0x80:
                status = c
                q += 1
            hi = status & 0xF0
            d1 = data[q]
            q += 1
            d2 = 0
            if hi not in (0xC0, 0xD0):
                d2 = data[q]
                q += 1
            if hi == 0x90 and d2 > 0:
                open_.setdefault(d1, []).append(t)
            elif hi == 0x80 or (hi == 0x90 and d2 == 0):
                if open_.get(d1):
                    notes.append((open_[d1].pop(0), t, d1))
        if notes:
            tracks.append((name, sorted(notes)))
    return div, meta, tracks


def track_segments(notes, div):
    """→ Liste (start, ende, [Tonhöhen] | None) in Ticks, lückenlos ab 0, auf Raster gerückt."""
    g = div / 12
    q = lambda t: int(round(t / g) * g)
    chords = {}
    for on, off, pitch in notes:
        s = q(on)
        e = max(q(off), s)
        if s in chords:
            chords[s][1] = max(chords[s][1], e)
            if pitch not in chords[s][0]:
                chords[s][0].append(pitch)
        else:
            chords[s] = [[pitch], e]
    starts = sorted(chords)
    segs, pos = [], 0
    for k, s in enumerate(starts):
        pitches, e = chords[s]
        nxt = starts[k + 1] if k + 1 < len(starts) else None
        if nxt is not None:
            if nxt - e < div / 2:          # kleine Lücke = Artikulation, Ton bis zum nächsten halten
                e = nxt
            e = min(e, nxt)
        if e <= s:
            e = s + int(g)
        if s > pos:
            segs.append((pos, s, None))
        segs.append((s, e, sorted(pitches, reverse=True)))
        pos = e
    return segs


def measure_grid(meta, div, end):
    """Taktgrenzen (Ticks) und Taktarten je Takt bis mindestens end."""
    times = sorted(meta['times']) or [(0, 4, 4)]
    if times[0][0] > 0:
        times.insert(0, (0, 4, 4))
    bounds, sigs, t, i = [0], [], 0, 0
    while t < end or not sigs:
        while i + 1 < len(times) and times[i + 1][0] <= t:
            i += 1
        num, den = times[i][1], times[i][2]
        length = num * 4 * div // den
        nxt_change = times[i + 1][0] if i + 1 < len(times) else None
        if nxt_change is not None and t < nxt_change < t + length:
            length = nxt_change - t           # unvollständiger Takt vor einem Taktwechsel
        t += length
        bounds.append(t)
        sigs.append((num, den))
    return bounds, sigs


def to_measures(segs, bounds, div, fifths):
    names = FLATS if (fifths or 0) < 0 else SHARPS
    tok = lambda p: names[p % 12] + str(p // 12 - 1)
    end = bounds[-1]
    if not segs or segs[-1][1] < end:
        segs = segs + [((segs[-1][1] if segs else 0), end, None)]
    measures = [[] for _ in range(len(bounds) - 1)]
    for s, e, pitches in segs:
        cur = s
        while cur < e:
            m = max(i for i in range(len(bounds) - 1) if bounds[i] <= cur)
            stop = min(e, bounds[m + 1])
            toks = [tok(p) for p in pitches] if pitches else None
            measures[m].append((toks, Fraction(stop - cur, div), bool(pitches) and stop < e))
            cur = stop
    return measures


def main(args):
    target = None
    if '--ziel' in args:
        i = args.index('--ziel')
        target = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    files = [Path(a) for a in args]
    if not files:
        raise SystemExit(__doc__)
    div0, meta0, parts_raw = None, None, []
    for f in files:
        div, meta, tracks = read_midi(f)
        if div0 is None:
            div0, meta0 = div, meta
        suffix = re.search(r'-([satb])$', f.stem, re.I)
        for k, (name, notes) in enumerate(tracks):
            scale = Fraction(div0, div)       # alle Dateien auf die Auflösung der ersten bringen
            notes = [(int(on * scale), int(off * scale), p) for on, off, p in notes]
            nm = SUFFIX[suffix.group(1).lower()] if suffix and len(tracks) == 1 else voice_name(name, f'Stimme {len(parts_raw) + 1}')
            parts_raw.append((nm, notes))
    segs = {nm: track_segments(notes, div0) for nm, notes in parts_raw}
    end = max(s[-1][1] for s in segs.values())
    bounds, sigs = measure_grid(meta0, div0, end)
    parts = {nm: to_measures(sg, bounds, div0, meta0['fifths']) for nm, sg in segs.items()}

    # Prüfen: jeder Takt hat in jeder Stimme genau seine Länge, kein Ton ging verloren
    for nm, ms in parts.items():
        for i, bar in enumerate(ms):
            want = Fraction(sigs[i][0] * 4, sigs[i][1])
            have = sum(d for _, d, _ in bar)
            if have != want and Fraction(bounds[i + 1] - bounds[i], div0) != have:
                raise SystemExit(f'{nm}, Takt {i + 1}: {have} statt {want} Viertel')
        onsets = sum(1 for bar in ms for toks, _, _ in bar if toks)
        chords = sum(1 for s in segs[nm] if s[2])
        assert onsets >= chords, (nm, onsets, chords)

    if target is None:
        stem = re.sub(r'-[satb]$', '', files[0].stem, flags=re.I) if len(files) > 1 else files[0].stem
        target = files[0].with_name(stem + '.musicxml')
    title = target.stem.replace('-', ' ')
    write_score(target, title, parts, sigs, meta0['fifths'] or 0, meta0['tempo'])
    poly = [nm for nm, sg in segs.items() if any(s[2] and len(s[2]) > 1 for s in sg)]
    print(f'{target.name}: {len(parts)} Stimmen ({", ".join(parts)}), {len(sigs)} Takte, '
          f'Tonart {meta0["fifths"] or 0:+d} Vorzeichen, Tempo {meta0["tempo"]}'
          + (f' – mit Akkorden in: {", ".join(poly)}' if poly else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
