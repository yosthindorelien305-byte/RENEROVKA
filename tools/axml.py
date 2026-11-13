import struct, sys, json
from xml.sax.saxutils import escape, quoteattr

def parse(data):
    # string pool
    off = 8
    strings = []
    out = []
    ns = {}
    while off < len(data):
        t, hs, sz = struct.unpack_from('<HHI', data, off)
        if t == 0x0001:
            cnt, sc, flags, sstart, ststart = struct.unpack_from('<IIIII', data, off + 8)
            utf8 = flags & 0x100
            offs = struct.unpack_from('<%dI' % cnt, data, off + 28)
            base = off + sstart
            for o in offs:
                p = base + o
                if utf8:
                    l = data[p]; p += 1
                    if l & 0x80: p += 1
                    l2 = data[p]; p += 1
                    if l2 & 0x80:
                        l2 = ((l2 & 0x7f) << 8) | data[p]; p += 1
                    strings.append(data[p:p + l2].decode('utf-8', 'replace'))
                else:
                    l = struct.unpack_from('<H', data, p)[0]; p += 2
                    if l & 0x8000:
                        l = ((l & 0x7fff) << 16) | struct.unpack_from('<H', data, p)[0]; p += 2
                    strings.append(data[p:p + l * 2].decode('utf-16le', 'replace'))
        elif t == 0x0102:
            ln, _ = struct.unpack_from('<II', data, off + 8)
            nsi, name, _, ac, _, _, _ = struct.unpack_from('<iiHHHHH', data, off + 16)
            # header: nsidx, nameidx, attrStart(2), attrSize(2), attrCount(2), id,class,style
            nsi, name, astart, asize, acount = struct.unpack_from('<iiHHH', data, off + 16)
            ap = off + 16 + 8 + astart - 0
            ap = off + 16 + 20 if astart == 20 else off + 16 + astart
            attrs = []
            for i in range(acount):
                ans, an, raw, vs, res, vt, vd = struct.unpack_from('<iiiHBBi', data, ap + i * asize)
                if raw != -1:
                    val = strings[raw]
                elif vt == 3:
                    val = strings[vd]
                elif vt == 0x10:
                    val = str(vd)
                elif vt == 0x12:
                    val = 'true' if vd else 'false'
                elif vt == 0x04:
                    val = str(struct.unpack('<f', struct.pack('<i', vd))[0])
                elif vt == 0x01:
                    val = '@res/%08x' % (vd & 0xffffffff)
                else:
                    val = '%d' % vd
                attrs.append((strings[an], val))
            out.append(('s', strings[name], attrs))
        elif t == 0x0103:
            nsi, name = struct.unpack_from('<ii', data, off + 16)
            out.append(('e', strings[name], None))
        elif t == 0x0104:
            ln, _, idx = struct.unpack_from('<IIi', data, off + 8)
            out.append(('t', strings[idx], None))
        off += sz
    return out

def to_xml(ev):
    lines = []
    depth = 0
    for k, n, a in ev:
        if k == 's':
            lines.append('  ' * depth + '<' + n + ''.join(' %s=%s' % (x, quoteattr(y)) for x, y in a) + '>')
            depth += 1
        elif k == 'e':
            depth -= 1
            lines.append('  ' * depth + '</' + n + '>')
        else:
            lines.append('  ' * depth + escape(n))
    return '\n'.join(lines)

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    open(sys.argv[2], 'w', encoding='utf-8').write(to_xml(parse(d)))
