"""Extract translatable strings from a non-localized Skyrim SE plugin into
Dynamic String Distributor (DSD) entries: original/form_id/type/index/editor_id.

Usage: python dsd_extract.py <plugin.esp> <out.json>
"""
import json
import struct
import sys
import zlib
import os

GENERIC = {'FULL', 'DESC', 'SHRT', 'RNAM'}   # one value per record
SKIP_FULL_TYPES = {'NAVM', 'LAND', 'TES4'}


def records(b):
    hs = struct.unpack_from('<I', b, 4)[0]
    hdr = b[24:24 + hs]
    masters = [v.rstrip(b'\0').decode('cp1252') for t, v in subrecords(hdr) if t == 'MAST']
    flags = struct.unpack_from('<I', b, 8)[0]
    yield None, flags, masters
    stack = [(24 + hs, len(b))]
    i, end = 24 + hs, len(b)

    def walk(i, end):
        while i < end:
            t = b[i:i + 4]
            sz = struct.unpack_from('<I', b, i + 4)[0]
            if t == b'GRUP':
                yield from walk(i + 24, i + sz)
                i += sz
                continue
            fl, fid = struct.unpack_from('<II', b, i + 8)
            d = b[i + 24:i + 24 + sz]
            if fl & 0x40000:
                d = zlib.decompress(d[4:])
            yield t.decode('latin1'), fid, d
            i += 24 + sz
    yield from walk(i, end)


def subrecords(d):
    i = 0
    big = None
    while i < len(d):
        t = d[i:i + 4].decode('latin1')
        sz = struct.unpack_from('<H', d, i + 4)[0]
        if t == 'XXXX':
            big = struct.unpack_from('<I', d, i + 6)[0]
            i += 10
            continue
        if big is not None:
            sz, big = big, None
        yield t, d[i + 6:i + 6 + sz]
        i += 6 + sz


def text(v):
    v = v.rstrip(b'\0')
    try:
        return v.decode('utf-8')
    except UnicodeDecodeError:
        return v.decode('cp1252', errors='replace')


def extract(path):
    name = os.path.basename(path)
    b = open(path, 'rb').read()
    it = records(b)
    _, flags, masters = next(it)
    if flags & 0x80:
        raise SystemExit('localized plugin - use .strings files instead')
    out = []
    seen = set()
    for rt, fid, body in it:
        if rt in SKIP_FULL_TYPES:
            continue
        mi = fid >> 24
        base = masters[mi] if mi < len(masters) else name
        form = f'{fid & 0xFFFFFF:08X}|{base}'
        edid = None
        resp = obj = stage = None
        itxt = 0
        for st, v in subrecords(body):
            if st == 'EDID':
                edid = v.rstrip(b'\0').decode('latin1')
                continue
            if rt == 'INFO' and st == 'TRDT':
                resp = v[12]
                continue
            if rt == 'QUST' and st == 'QOBJ':
                obj = struct.unpack_from('<H', v)[0]
                continue
            if rt == 'QUST' and st == 'INDX':
                stage = struct.unpack_from('<H', v)[0]
                continue
            key = None
            if rt == 'INFO' and st == 'NAM1':
                key = ('INFO NAM1', resp)
            elif rt == 'INFO' and st == 'RNAM':
                key = ('INFO RNAM', None)
            elif rt == 'QUST' and st == 'NNAM':
                key = ('QUST NNAM', obj)
            elif rt == 'QUST' and st == 'CNAM':
                key = ('QUST CNAM', stage)
            elif rt == 'MESG' and st == 'ITXT':
                key = ('MESG ITXT', itxt)
                itxt += 1
            elif rt == 'MGEF' and st == 'DNAM':
                key = ('MGEF DNAM', None)
            elif rt == 'BOOK' and st == 'CNAM':
                key = ('BOOK CNAM', None)
            elif st in GENERIC and rt not in ('INFO', 'QUST'):
                if st == 'RNAM' and rt not in ('ACTI', 'FLOR'):
                    continue  # NPC_/HDPT/RACE RNAM are form ids, not text
                key = (f'{rt} {st}', None)
            if not key or len(v) <= 1:
                continue
            s = text(v)
            if not s.strip() or any(ord(c) < 9 for c in s):
                continue
            k = (form, key[0], key[1])
            if k in seen:
                continue
            seen.add(k)
            out.append({'original': s, 'string': '', 'form_id': form,
                        'type': key[0], 'index': key[1], 'editor_id': edid})
    return out


if __name__ == '__main__':
    data = extract(sys.argv[1])
    json.dump(data, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    from collections import Counter
    print(len(data), Counter(e['type'] for e in data).most_common())
