"""XA ADPCM audio of an STR movie (raw sectors from the disc image) -> WAV per channel.

    python tools/xa.py wav <GRP name> <file name> <outdir>     e.g. MOVIES.GRP SEXMOVIE.STR out/

Also gives the sector -> time mapping used for subtitles: at 2x CD speed a movie plays
150 sectors per second, so sector i of the file is shown/heard at i / 150 s.
"""
import os
import struct
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_disc import Disc  # noqa: E402
from grp import read_index  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE = os.path.join(ROOT, 'Gakkou de Atta Kowai Hanashi S (Japan).bin')
K0 = [0, 60, 115, 98, 122]
K1 = [0, 0, -52, -55, -60]
SECTORS_PER_SECOND = 150
RATE = {}          # channel -> sample rate of the last decoded file


def file_lba(d, gname, fname):
    g = {x['name']: x for x in read_index(os.path.join(ROOT, 'work', 'source', 'disc'))}[gname]
    rec = [f for f in g['files'] if f['name'] == fname][0]
    gp = [p for p in d.entries if p.endswith('/' + gname)][0]
    return d.entries[gp].lba + rec['sector'], rec['sectors']


def decode_sector(data, state, stereo=False):
    """2304 bytes of a 4-bit XA sector -> samples (mono: 4032; stereo: 2016 L/R pairs mixed
    to mono). state: [old, older] per channel side."""
    if len(state) < 4:
        state[:] = [0, 0, 0, 0]
    out = [[], []]
    for g in range(18):
        grp = data[g * 128:(g + 1) * 128]
        for u in range(8):
            side = (u & 1) if stereo else 0
            old, older = state[side * 2], state[side * 2 + 1]
            p = grp[4 + u]
            shift, filt = p & 15, min(p >> 4, 4)
            for j in range(28):
                b = grp[16 + j * 4 + u // 2]
                n = (b >> (4 * (u & 1))) & 15
                s = (n << 12) - 0x10000 if n & 8 else n << 12
                s = (s >> shift) + ((old * K0[filt] + older * K1[filt] + 32) >> 6)
                s = max(-32768, min(32767, s))
                older, old = old, s
                out[side].append(s)
            state[side * 2], state[side * 2 + 1] = old, older
    if not stereo:
        return out[0]
    return [(a + b) // 2 for a, b in zip(out[0], out[1])]


def channels(gname, fname):
    """-> {channel: [(sector index, samples)]}"""
    d = Disc(IMAGE, 'rb')
    lba, n = file_lba(d, gname, fname)
    out, states = {}, {}
    for i in range(n):
        r = d.raw(lba + i)
        ch, submode, ci = r[17], r[18], r[19]
        if not submode & 4:
            continue
        assert not (ci >> 4) & 3, 'only 4-bit XA handled (coding %02x)' % ci
        st = states.setdefault(ch, [0, 0, 0, 0])
        out.setdefault(ch, []).append((i, decode_sector(r[24:24 + 2304], st, stereo=bool(ci & 1))))
        RATE[ch] = 18900 if ci & 4 else 37800
    return out


def write_wav(path, samples, rate=37800):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack('<%dh' % len(samples), *samples))


def main():
    if sys.argv[1] == 'wav':
        gname, fname, outdir = sys.argv[2:5]
        os.makedirs(outdir, exist_ok=True)
        for ch, secs in channels(gname, fname).items():
            samples = [s for _, ss in secs for s in ss]
            p = os.path.join(outdir, '%s_ch%d.wav' % (os.path.splitext(fname)[0], ch))
            write_wav(p, samples, RATE[ch])
            first, last = secs[0][0], secs[-1][0]
            print('ch%d: %d sectors, %.1f s of audio, file sectors %d-%d (%.1f-%.1f s)' % (
                ch, len(secs), len(samples) / RATE[ch], first, last, first / SECTORS_PER_SECOND, last / SECTORS_PER_SECOND))


if __name__ == '__main__':
    main()
