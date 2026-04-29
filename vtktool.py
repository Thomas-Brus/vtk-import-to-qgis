# vtktool.py  –  Velocitek .VTK reader  (v4)
#
# Wire format: [uint16 LE length][protobuf vtk.Record]  repeated
#
# Output fields per Trackpoint:
#   time         str    "DD.MM.YY HH:MM:SS (UTC)"
#   latitude     float  WGS84
#   longitude    float  WGS84
#   sog          float  speed over ground in knots
#   cog          int    course over ground in degrees
#   q1..q4       float  quaternion components (raw, not scaled)
#   mag_heading  float  magnetic heading from quaternion (degrees)
#   heel         float  roll angle (degrees)
#   pitch        float  pitch angle (degrees)

import struct, csv, sys, math
from datetime import datetime, timezone


# ── protobuf import ──────────────────────────────────────────────────────────
def _try_pb():
    try:
        try:    from . import vtk_pb2
        except: import vtk_pb2
        _ = vtk_pb2.Record
        return vtk_pb2
    except Exception:
        return None


# ── zigzag decode (protobuf sint32) ─────────────────────────────────────────
def _zz(n): return (n >> 1) ^ -(n & 1)


# ── quaternion → mag_heading, heel, pitch ────────────────────────────────────
def _quat2euler(w, x, y, z):
    heel    = math.degrees(math.atan2(2*(w*x + y*z), 1 - 2*(x*x + y*y)))
    sinp    = max(-1.0, min(1.0, 2*(w*y - z*x)))
    pitch   = math.degrees(math.asin(sinp))
    heading = math.degrees(math.atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))) % 360
    return round(heading, 2), round(heel, 2), round(pitch, 2)


# ── timestamp → UTC string ───────────────────────────────────────────────────
def _ts_to_utc(seconds, centiseconds=0):
    """Convert device seconds + centiseconds to 'DD.MM.YY HH:MM:SS (UTC)'."""
    try:
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.strftime('%d.%m.%y %H:%M:%S (UTC)')
    except Exception:
        return str(seconds)


# ── pure-python protobuf field decoder (fallback) ────────────────────────────
def _fields(data):
    out, pos, n = {}, 0, len(data)
    while pos < n:
        tag, sh = 0, 0
        while True:
            if pos >= n: return out
            b = data[pos]; pos += 1
            tag |= (b & 0x7F) << sh; sh += 7
            if not (b & 0x80): break
        fn, wt = tag >> 3, tag & 7
        if wt == 0:
            v, sh = 0, 0
            while True:
                if pos >= n: return out
                b = data[pos]; pos += 1
                v |= (b & 0x7F) << sh; sh += 7
                if not (b & 0x80): break
            out[fn] = v
        elif wt == 1:
            if pos + 8 > n: return out
            out[fn] = struct.unpack_from('<Q', data, pos)[0]; pos += 8
        elif wt == 2:
            ln, sh = 0, 0
            while True:
                if pos >= n: return out
                b = data[pos]; pos += 1
                ln |= (b & 0x7F) << sh; sh += 7
                if not (b & 0x80): break
            out[fn] = data[pos:pos+ln]; pos += ln
        elif wt == 5:
            if pos + 4 > n: return out
            out[fn] = struct.unpack_from('<I', data, pos)[0]; pos += 4
        else:
            return out
    return out


def _row_from_raw(raw):
    """Pure-Python fallback parser (no protobuf library needed)."""
    rf = _fields(raw)
    tp_bytes = rf.get(1)
    if not isinstance(tp_bytes, (bytes, bytearray)) or not tp_bytes:
        return None
    tp  = _fields(tp_bytes)
    lat_raw = tp.get(3, 0)
    lon_raw = tp.get(4, 0)
    if lat_raw == 0 and lon_raw == 0:
        return None
    lat  = _zz(lat_raw) / 1e7
    lon  = _zz(lon_raw) / 1e7
    secs = tp.get(1, 0)
    cs   = tp.get(2, 0)
    sog  = tp.get(5, 0) / 10.0
    cog  = tp.get(6, 0)
    q1   = _zz(tp.get(7,  0)) / 1000.0
    q2   = _zz(tp.get(8,  0)) / 1000.0
    q3   = _zz(tp.get(9,  0)) / 1000.0
    q4   = _zz(tp.get(10, 0)) / 1000.0
    mh, hl, pt = _quat2euler(q1, q2, q3, q4)
    return dict(
        time        = _ts_to_utc(secs, cs),
        latitude    = round(lat, 7),
        longitude   = round(lon, 7),
        sog         = round(sog, 2),
        cog         = cog,
        q1          = round(q1, 3),
        q2          = round(q2, 3),
        q3          = round(q3, 3),
        q4          = round(q4, 3),
        mag_heading = mh,
        heel        = hl,
        pitch       = pt,
    )


# ── main parser ──────────────────────────────────────────────────────────────
def parse_vtk_file(vtk_path):
    """
    Read a Velocitek .VTK file and return list of dicts (one per Trackpoint).
    Wire format: uint16-LE length prefix + protobuf vtk.Record, repeated.
    """
    pb   = _try_pb()
    rows = []

    with open(vtk_path, 'rb') as f:
        while True:
            hdr = f.read(2)
            if len(hdr) < 2: break
            length = struct.unpack_from('<H', hdr)[0]
            if length == 0: continue
            raw = f.read(length)
            if len(raw) < length: break

            if pb is not None:
                try:
                    rec = pb.Record()
                    rec.ParseFromString(raw)
                    if rec.WhichOneof('record') != 'trackpoint':
                        continue
                    tp  = rec.trackpoint
                    lat = tp.latitudeE7  / 1e7
                    lon = tp.longitudeE7 / 1e7
                    if lat == 0.0 and lon == 0.0:
                        continue
                    sog = tp.sog_knotsE1 / 10.0
                    q1  = tp.q1E3 / 1000.0
                    q2  = tp.q2E3 / 1000.0
                    q3  = tp.q3E3 / 1000.0
                    q4  = tp.q4E3 / 1000.0
                    mh, hl, pt = _quat2euler(q1, q2, q3, q4)
                    rows.append(dict(
                        time        = _ts_to_utc(tp.seconds, tp.centiseconds),
                        latitude    = round(lat, 7),
                        longitude   = round(lon, 7),
                        sog         = round(sog, 2),
                        cog         = tp.cog,
                        q1          = round(q1, 3),
                        q2          = round(q2, 3),
                        q3          = round(q3, 3),
                        q4          = round(q4, 3),
                        mag_heading = mh,
                        heel        = hl,
                        pitch       = pt,
                    ))
                except Exception:
                    continue
            else:
                row = _row_from_raw(raw)
                if row:
                    rows.append(row)

    return rows


# ── CSV export ───────────────────────────────────────────────────────────────
FIELDNAMES = ['time', 'latitude', 'longitude', 'sog', 'cog',
              'q1', 'q2', 'q3', 'q4', 'mag_heading', 'heel', 'pitch']

def write_csv(rows, csv_path):
    if not rows: return 0
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)
    return len(rows)

def vtk_to_csv(vtk_path, csv_path):
    return write_csv(parse_vtk_file(vtk_path), csv_path)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python vtktool.py INPUT.VTK OUTPUT.csv")
        sys.exit(1)
    rows = parse_vtk_file(sys.argv[1])
    if not rows:
        print("FEHLER: keine Trackpoints gefunden.")
        sys.exit(1)
    print(f"Erster Trackpoint:")
    for k, v in rows[0].items():
        print(f"  {k}: {v}")
    n = write_csv(rows, sys.argv[2])
    print(f"\n{n} Trackpoints → {sys.argv[2]}")
