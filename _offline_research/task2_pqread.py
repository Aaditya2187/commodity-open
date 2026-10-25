"""Minimal pure-Python Parquet reader (flat columns) for environments without pyarrow.

Supports: thrift compact footer, SNAPPY (via libsnappy ctypes) / UNCOMPRESSED / GZIP,
data pages V1 and V2, PLAIN and RLE_DICTIONARY encodings, definition levels for
optional flat columns. Nested (repeated) columns are skipped.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import gzip
import struct
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- snappy
_snappy = None


def _load_snappy():
    global _snappy
    if _snappy is None:
        name = ctypes.util.find_library("snappy") or "libsnappy.so.1"
        _snappy = ctypes.CDLL(name)
        _snappy.snappy_uncompressed_length.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        _snappy.snappy_uncompress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t)]
    return _snappy


def snappy_decompress(buf: bytes) -> bytes:
    lib = _load_snappy()
    n = ctypes.c_size_t()
    if lib.snappy_uncompressed_length(buf, len(buf), ctypes.byref(n)) != 0:
        raise ValueError("snappy: bad length")
    out = ctypes.create_string_buffer(n.value)
    m = ctypes.c_size_t(n.value)
    if lib.snappy_uncompress(buf, len(buf), out, ctypes.byref(m)) != 0:
        raise ValueError("snappy: decompress failed")
    return out.raw[: m.value]


def decompress(codec: int, buf: bytes, uncompressed_size: int) -> bytes:
    if codec == 0:
        return buf
    if codec == 1:
        return snappy_decompress(buf)
    if codec == 2:
        return gzip.decompress(buf)
    if codec == 6:
        return _zstd().decompress(buf)
    raise NotImplementedError(f"codec {codec}")


_zstd_mod = None


def _zstd():
    global _zstd_mod
    if _zstd_mod is None:
        try:
            from compression import zstd as z  # Python 3.14+
        except ImportError:
            from backports import zstd as z
        _zstd_mod = z
    return _zstd_mod


# ---------------------------------------------------------------- thrift compact
class _Reader:
    __slots__ = ("b", "i")

    def __init__(self, b: bytes, i: int = 0):
        self.b = b
        self.i = i

    def byte(self) -> int:
        v = self.b[self.i]
        self.i += 1
        return v

    def varint(self) -> int:
        shift = 0
        result = 0
        while True:
            v = self.byte()
            result |= (v & 0x7F) << shift
            if not v & 0x80:
                return result
            shift += 7

    def zigzag(self) -> int:
        n = self.varint()
        return (n >> 1) ^ -(n & 1)

    def binary(self) -> bytes:
        n = self.varint()
        v = self.b[self.i : self.i + n]
        self.i += n
        return v

    def value(self, t: int):
        if t == 1:
            return True
        if t == 2:
            return False
        if t == 3:
            return struct.unpack("<b", bytes([self.byte()]))[0]
        if t in (4, 5, 6):
            return self.zigzag()
        if t == 7:
            v = struct.unpack("<d", self.b[self.i : self.i + 8])[0]
            self.i += 8
            return v
        if t == 8:
            return self.binary()
        if t in (9, 10):
            h = self.byte()
            n = h >> 4
            et = h & 0x0F
            if n == 15:
                n = self.varint()
            return [self.value(et) for _ in range(n)]
        if t == 11:
            n = self.varint()
            if n == 0:
                return {}
            h = self.byte()
            kt, vt = h >> 4, h & 0x0F
            return {self.value(kt): self.value(vt) for _ in range(n)}
        if t == 12:
            return self.struct()
        raise ValueError(f"thrift type {t}")

    def struct(self) -> dict:
        out = {}
        last = 0
        while True:
            h = self.byte()
            if h == 0:
                return out
            delta = h >> 4
            t = h & 0x0F
            if delta:
                fid = last + delta
            else:
                fid = self.zigzag()
            last = fid
            out[fid] = self.value(t)


# ---------------------------------------------------------------- RLE / bit-packing
def _rle_hybrid(r: _Reader, bit_width: int, count: int, length: int | None = None) -> np.ndarray:
    """Decode an RLE/bit-packed hybrid run of `count` values."""
    end = r.i + length if length is not None else len(r.b)
    out = np.empty(count, dtype=np.int64)
    pos = 0
    nbytes = (bit_width + 7) // 8
    mask = (1 << bit_width) - 1
    while pos < count and r.i < end:
        header = r.varint()
        if header & 1:
            groups = header >> 1
            nvals = groups * 8
            raw = r.b[r.i : r.i + groups * bit_width]
            r.i += groups * bit_width
            if bit_width == 0:
                vals = np.zeros(nvals, dtype=np.int64)
            else:
                bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8), bitorder="little")
                bits = bits[: nvals * bit_width].reshape(nvals, bit_width)
                vals = (bits.astype(np.int64) * (1 << np.arange(bit_width, dtype=np.int64))).sum(axis=1)
            take = min(nvals, count - pos)
            out[pos : pos + take] = vals[:take]
            pos += take
        else:
            n = header >> 1
            v = int.from_bytes(r.b[r.i : r.i + nbytes], "little") & mask if nbytes else 0
            r.i += nbytes
            take = min(n, count - pos)
            out[pos : pos + take] = v
            pos += take
    r.i = end if length is not None else r.i
    return out


def _bit_width(max_level: int) -> int:
    return int(max_level).bit_length()


# ---------------------------------------------------------------- schema
@dataclass
class Column:
    name: str
    ptype: int
    type_length: int
    max_def: int
    max_rep: int
    converted: int | None
    logical: dict | None
    scale: int | None = None
    precision: int | None = None


def _schema(elems: list[dict]) -> list[Column]:
    """Flatten the schema; return leaf columns in order with max def/rep levels."""
    cols: list[Column] = []
    idx = 1  # skip root

    def walk(prefix, def_lvl, rep_lvl):
        nonlocal idx
        e = elems[idx]
        idx += 1
        name = e[4].decode()
        rep = e.get(3, 0)  # 0 required, 1 optional, 2 repeated
        d = def_lvl + (1 if rep in (1, 2) else 0)
        r = rep_lvl + (1 if rep == 2 else 0)
        nchild = e.get(5, 0)
        full = (prefix + [name])
        if nchild:
            for _ in range(nchild):
                walk(full, d, r)
        else:
            cols.append(Column(".".join(full), e.get(1), e.get(2, 0), d, r, e.get(6), e.get(10), e.get(7), e.get(8)))

    while idx < len(elems):
        walk([], 0, 0)
    return cols


# ---------------------------------------------------------------- values
def _plain(r: _Reader, ptype: int, n: int, type_length: int):
    b = r.b
    if ptype == 0:  # boolean, bit packed
        nbytes = (n + 7) // 8
        bits = np.unpackbits(np.frombuffer(b[r.i : r.i + nbytes], dtype=np.uint8), bitorder="little")[:n]
        r.i += nbytes
        return bits.astype(bool)
    if ptype == 1:
        v = np.frombuffer(b, dtype="<i4", count=n, offset=r.i)
        r.i += 4 * n
        return v
    if ptype == 2:
        v = np.frombuffer(b, dtype="<i8", count=n, offset=r.i)
        r.i += 8 * n
        return v
    if ptype == 4:
        v = np.frombuffer(b, dtype="<f4", count=n, offset=r.i)
        r.i += 4 * n
        return v
    if ptype == 5:
        v = np.frombuffer(b, dtype="<f8", count=n, offset=r.i)
        r.i += 8 * n
        return v
    if ptype == 6:
        out = []
        i = r.i
        for _ in range(n):
            ln = int.from_bytes(b[i : i + 4], "little")
            i += 4
            out.append(b[i : i + ln])
            i += ln
        r.i = i
        return np.array(out, dtype=object)
    if ptype == 7:
        out = [b[r.i + k * type_length : r.i + (k + 1) * type_length] for k in range(n)]
        r.i += n * type_length
        return np.array(out, dtype=object)
    if ptype == 3:  # int96 timestamps, rare
        raw = np.frombuffer(b, dtype="<u1", count=12 * n, offset=r.i).reshape(n, 12)
        r.i += 12 * n
        nanos = raw[:, :8].copy().view("<i8").ravel()
        days = raw[:, 8:12].copy().view("<i4").ravel()
        return (days.astype(np.int64) - 2440588) * 86_400_000_000_000 + nanos
    raise NotImplementedError(f"ptype {ptype}")


def _read_column(data: bytes, cc: dict, col: Column):
    md = cc[3]
    codec = md.get(4, 0)
    num_values = md[5]
    start = md.get(11) if md.get(11) is not None else md[9]
    start = min(start, md[9]) if md.get(11) is not None else md[9]
    r = _Reader(data, start)
    dictionary = None
    values_parts = []
    defs_parts = []
    got = 0
    while got < num_values:
        ph = r.struct()
        ptype_page = ph[1]
        comp = ph[3]
        uncomp = ph[2]
        page = data[r.i : r.i + comp]
        r.i += comp
        if ptype_page == 2:  # dictionary page
            raw = decompress(codec, page, uncomp)
            dh = ph[7]
            dictionary = _plain(_Reader(raw), col.ptype, dh[1], col.type_length)
            continue
        if ptype_page == 0:  # data page v1
            dh = ph[5]
            n = dh[1]
            enc = dh[2]
            raw = decompress(codec, page, uncomp)
            pr = _Reader(raw)
            if col.max_rep > 0:
                ln = int.from_bytes(raw[pr.i : pr.i + 4], "little")
                pr.i += 4 + ln
            if col.max_def > 0:
                ln = int.from_bytes(raw[pr.i : pr.i + 4], "little")
                pr.i += 4
                defs = _rle_hybrid(pr, _bit_width(col.max_def), n, ln)
            else:
                defs = np.full(n, col.max_def, dtype=np.int64)
        elif ptype_page == 3:  # data page v2
            dh = ph[8]
            n = dh[1]
            enc = dh[4]
            dl = dh.get(5, 0)
            rl = dh.get(6, 0)
            is_comp = dh.get(7, True)
            levels = page[: rl + dl]
            body = page[rl + dl :]
            raw = decompress(codec, body, uncomp - rl - dl) if is_comp else body
            if col.max_def > 0:
                defs = _rle_hybrid(_Reader(levels, rl), _bit_width(col.max_def), n, dl)
            else:
                defs = np.full(n, col.max_def, dtype=np.int64)
            pr = _Reader(raw)
        else:
            raise NotImplementedError(f"page type {ptype_page}")
        nvalid = int((defs == col.max_def).sum())
        if enc == 0:
            vals = _plain(pr, col.ptype, nvalid, col.type_length)
        elif enc in (2, 8):
            bw = pr.byte()
            idx = _rle_hybrid(pr, bw, nvalid)
            vals = dictionary[idx]
        else:
            raise NotImplementedError(f"encoding {enc} on {col.name}")
        values_parts.append(np.asarray(vals))
        defs_parts.append(defs)
        got += n
    vals = np.concatenate(values_parts) if values_parts else np.array([])
    defs = np.concatenate(defs_parts) if defs_parts else np.array([], dtype=np.int64)
    return vals, defs


def _to_series(vals, defs, col: Column) -> pd.Series:
    n = len(defs)
    valid = defs == col.max_def
    conv = col.converted
    lt = col.logical or {}
    is_str = conv == 0 or 1 in lt
    if col.ptype in (6, 7) and is_str:
        vals = np.array([v.decode("utf-8", "replace") for v in vals], dtype=object)
    if col.ptype == 7 and conv == 5:  # decimal fixed-len
        scale = col.scale or 0
        vals = np.array([int.from_bytes(v, "big", signed=True) / (10**scale) for v in vals], dtype=float)
    if col.ptype in (1, 2) and conv == 5:
        scale = col.scale or 0
        vals = vals.astype(float) / (10**scale)
    # timestamps
    ts = lt.get(8)
    if col.ptype == 2 and (ts is not None or conv in (9, 10)):
        if ts is not None:
            unit = "ms" if 1 in ts[2] else "us" if 2 in ts[2] else "ns"
            utc = ts.get(1, False)
        else:
            unit = "ms" if conv == 9 else "us"
            utc = True
        out = np.full(n, np.datetime64("NaT"), dtype=f"datetime64[{unit}]")
        out[valid] = vals.astype(f"datetime64[{unit}]")
        s = pd.Series(out, name=col.name)
        if utc:
            s = s.dt.tz_localize("UTC")
        return s
    if col.ptype == 3:
        out = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
        out[valid] = vals.astype("datetime64[ns]")
        return pd.Series(out, name=col.name).dt.tz_localize("UTC")
    if col.ptype == 1 and (conv == 6 or 6 in lt):
        out = np.full(n, np.datetime64("NaT"), dtype="datetime64[D]")
        out[valid] = vals.astype("datetime64[D]")
        return pd.Series(out.astype("datetime64[s]"), name=col.name)
    if valid.all():
        return pd.Series(vals, name=col.name)
    if col.ptype in (1, 2):
        out = np.full(n, np.nan)
        out[valid] = vals
        return pd.Series(out, name=col.name).astype("Int64") if col.ptype in (1, 2) else pd.Series(out, name=col.name)
    if col.ptype in (4, 5):
        out = np.full(n, np.nan)
        out[valid] = vals
        return pd.Series(out, name=col.name)
    out = np.full(n, None, dtype=object)
    out[valid] = vals
    return pd.Series(out, name=col.name)


def read_metadata(path: str):
    with open(path, "rb") as f:
        data = f.read()
    assert data[-4:] == b"PAR1"
    n = struct.unpack("<I", data[-8:-4])[0]
    meta = _Reader(data[-8 - n : -8]).struct()
    return data, meta


def read_parquet(path: str, columns: list[str] | None = None) -> pd.DataFrame:
    data, meta = read_metadata(path)
    cols = _schema(meta[2])
    want = [c for c in cols if (columns is None or c.name in columns) and c.max_rep == 0]
    frames = []
    for rg in meta[4]:
        chunks = rg[1]
        series = {}
        for cc, col in zip(chunks, cols):
            if col not in want:
                continue
            vals, defs = _read_column(data, cc, col)
            series[col.name] = _to_series(vals, defs, col)
        frames.append(pd.DataFrame(series))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame({c.name: [] for c in want})
    if columns is not None:
        df = df[[c for c in columns if c in df.columns]]
    return df


def schema(path: str):
    _, meta = read_metadata(path)
    return [(c.name, c.ptype, c.converted, c.logical, c.max_def, c.max_rep) for c in _schema(meta[2])]
