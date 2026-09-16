"""Minimal .aseprite (ASE) reader/writer, stdlib only.

Implements the subset of the v1.3 spec this project needs:
  header, frames, colour profile, palette (0x2019), layers (0x2004),
  zlib-compressed cels (0x2005) and frame tags (0x2018), in RGBA colour depth.

The reader exists so the build can verify its own output round-trips, since
Aseprite is not necessarily installed on the machine running the build.
Spec: https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md
"""

import struct
import zlib

ASE_MAGIC = 0xA5E0
FRAME_MAGIC = 0xF1FA

CHUNK_PALETTE = 0x2019
CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_TAGS = 0x2018
CHUNK_COLOR_PROFILE = 0x2007

LOOP_FORWARD = 0


def _u8(v):
    return struct.pack("<B", v)


def _u16(v):
    return struct.pack("<H", v)


def _i16(v):
    return struct.pack("<h", v)


def _u32(v):
    return struct.pack("<I", v)


def _string(s):
    b = s.encode("utf-8")
    return _u16(len(b)) + b


def _chunk(ctype, data):
    return _u32(len(data) + 6) + _u16(ctype) + data


# ----------------------------------------------------------------- writer ---
def _palette_chunk(colors):
    """colors: [((r, g, b, a), name), ...]"""
    data = _u32(len(colors)) + _u32(0) + _u32(len(colors) - 1) + b"\x00" * 8
    for (r, g, b, a), name in colors:
        data += _u16(1) + bytes((r, g, b, a)) + _string(name)
    return _chunk(CHUNK_PALETTE, data)


def _layer_chunk(name, visible=True, opacity=255):
    flags = (1 if visible else 0) | 2            # visible | editable
    data = (_u16(flags) + _u16(0) + _u16(0) + _u16(0) + _u16(0) + _u16(0)
            + _u8(opacity) + b"\x00" * 3 + _string(name))
    return _chunk(CHUNK_LAYER, data)


def _cel_chunk(layer_index, x, y, w, h, rgba, opacity=255):
    data = (_u16(layer_index) + _i16(x) + _i16(y) + _u8(opacity)
            + _u16(2)                             # cel type: compressed image
            + _i16(0)                             # z-index
            + b"\x00" * 5
            + _u16(w) + _u16(h) + zlib.compress(rgba, 9))
    return _chunk(CHUNK_CEL, data)


def _tags_chunk(tags):
    """tags: [(name, from_frame, to_frame, (r, g, b)), ...]"""
    data = _u16(len(tags)) + b"\x00" * 8
    for name, f, t, color in tags:
        data += (_u16(f) + _u16(t) + _u8(LOOP_FORWARD)
                 + _u16(0)                        # repeat: infinite
                 + b"\x00" * 6
                 + bytes(color) + b"\x00"
                 + _string(name))
    return _chunk(CHUNK_TAGS, data)


def _color_profile_chunk():
    return _chunk(CHUNK_COLOR_PROFILE, _u16(1) + _u16(0) + _u32(0) + b"\x00" * 8)


def _frame(chunks, duration_ms):
    body = b"".join(chunks)
    n = len(chunks)
    header = (_u32(len(body) + 16) + _u16(FRAME_MAGIC)
              + _u16(n if n < 0xFFFF else 0xFFFF)
              + _u16(duration_ms) + b"\x00" * 2 + _u32(n))
    return header + body


def write(path, width, height, layers, frames, palette, tags, grid=16):
    """Write an .aseprite file.

    layers  : [layer_name, ...]            bottom-up, index 0 is the bottom
    frames  : [([rgba_bytes_per_layer], duration_ms), ...]
              a layer entry of None means "no cel on this layer in this frame"
    palette : [((r, g, b, a), name), ...]
    tags    : [(name, from, to, (r, g, b)), ...]
    """
    out = []
    for i, (layer_pixels, ms) in enumerate(frames):
        chunks = []
        if i == 0:
            chunks.append(_color_profile_chunk())
            chunks.append(_palette_chunk(palette))
            for name in layers:
                chunks.append(_layer_chunk(name))
        for li, rgba in enumerate(layer_pixels):
            if rgba is not None:
                chunks.append(_cel_chunk(li, 0, 0, width, height, rgba))
        if i == 0 and tags:
            chunks.append(_tags_chunk(tags))
        out.append(_frame(chunks, ms))

    body = b"".join(out)
    header = (
        _u32(len(body) + 128) + _u16(ASE_MAGIC) + _u16(len(frames))
        + _u16(width) + _u16(height) + _u16(32)       # RGBA
        + _u32(1)                                     # layer opacity is valid
        + _u16(100) + _u32(0) + _u32(0)
        + _u8(0) + b"\x00" * 3
        + _u16(len(palette))
        + _u8(1) + _u8(1)                             # 1:1 pixel ratio
        + _i16(0) + _i16(0) + _u16(grid) + _u16(grid)
        + b"\x00" * 84
    )
    assert len(header) == 128, len(header)
    with open(path, "wb") as fh:
        fh.write(header + body)
    return len(header + body)


# ----------------------------------------------------------------- reader ---
def read(path):
    """Parse an .aseprite file into a plain dict (verification helper)."""
    with open(path, "rb") as fh:
        buf = fh.read()

    size, magic, nframes, w, h, depth = struct.unpack_from("<IHHHHH", buf, 0)
    if magic != ASE_MAGIC:
        raise ValueError(f"bad magic 0x{magic:04x}")
    if size != len(buf):
        raise ValueError(f"header size {size} != actual {len(buf)}")
    ncolors = struct.unpack_from("<H", buf, 32)[0]

    doc = {"width": w, "height": h, "depth": depth, "ncolors": ncolors,
           "layers": [], "tags": [], "palette": [], "frames": []}

    off = 128
    for _ in range(nframes):
        fsize, fmagic, old_n, dur = struct.unpack_from("<IHHH", buf, off)
        if fmagic != FRAME_MAGIC:
            raise ValueError(f"bad frame magic 0x{fmagic:04x} at {off}")
        new_n = struct.unpack_from("<I", buf, off + 12)[0]
        nchunks = new_n or old_n
        frame = {"duration": dur, "cels": []}
        c = off + 16
        for _ in range(nchunks):
            csize, ctype = struct.unpack_from("<IH", buf, c)
            data = buf[c + 6:c + csize]
            if ctype == CHUNK_LAYER:
                nlen = struct.unpack_from("<H", data, 16)[0]
                doc["layers"].append(data[18:18 + nlen].decode("utf-8"))
            elif ctype == CHUNK_CEL:
                li, cx, cy, op, ctyp = struct.unpack_from("<HhhBH", data, 0)
                if ctyp != 2:
                    raise ValueError(f"unsupported cel type {ctyp}")
                cw, ch = struct.unpack_from("<HH", data, 16)
                px = zlib.decompress(data[20:])
                if len(px) != cw * ch * 4:
                    raise ValueError("cel pixel count mismatch")
                frame["cels"].append({"layer": li, "x": cx, "y": cy,
                                      "w": cw, "h": ch, "pixels": px})
            elif ctype == CHUNK_TAGS:
                ntags = struct.unpack_from("<H", data, 0)[0]
                p = 10
                for _ in range(ntags):
                    f0, f1 = struct.unpack_from("<HH", data, p)
                    nlen = struct.unpack_from("<H", data, p + 17)[0]
                    name = data[p + 19:p + 19 + nlen].decode("utf-8")
                    doc["tags"].append({"name": name, "from": f0, "to": f1})
                    p += 19 + nlen
            elif ctype == CHUNK_PALETTE:
                first, last = struct.unpack_from("<II", data, 4)
                p = 20
                for _ in range(last - first + 1):
                    flags = struct.unpack_from("<H", data, p)[0]
                    rgba = tuple(data[p + 2:p + 6])
                    p += 6
                    name = ""
                    if flags & 1:
                        nlen = struct.unpack_from("<H", data, p)[0]
                        name = data[p + 2:p + 2 + nlen].decode("utf-8")
                        p += 2 + nlen
                    doc["palette"].append((rgba, name))
            c += csize
        if c != off + fsize:
            raise ValueError(f"frame chunk overrun: {c} != {off + fsize}")
        doc["frames"].append(frame)
        off += fsize

    if off != len(buf):
        raise ValueError(f"trailing bytes: parsed {off} of {len(buf)}")
    return doc
