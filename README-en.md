# VTK Importer – QGIS Plugin
## Documentation & Data Field Description

---

## 1. Background

Velocitek GPS devices (e.g., ProStart) store sailing data in the proprietary `.VTK` format. The open-source project [velocitek/vtk_protocol](https://github.com/velocitek/vtk_protocol) on GitHub documents the binary format and provides a Python library.

The goal of this plugin is to open `.VTK` files directly in QGIS and provide the GPS track data as a CSV, GeoJSON, or PostGIS layer.

---

## 2. How the Plugin Came About

### 2.1 Analysis of the File Format

The `.VTK` format uses **Protocol Buffers (protobuf)** as its serialization format. The messages are length-delimited – however, not with the usual protobuf variant prefix, but with a **2-byte little-endian length prefix** (`uint16 LE`):

```
[2 bytes LE length] [N bytes protobuf vtk.Record]

[2 bytes LE length] [N bytes protobuf vtk.Record]
...
```

This format was identified by analyzing a hex dump of a genuine `.VTK` file:

```
0000: 09 00 8a 01 06 08 01 10 07 18 2e 22 00 0a 20 08

^^^^^ = 9 bytes length (uint16 LE)
```

### 2.2 Protobuf Scheme (vtk.proto)

The The `Record` message contains a `oneof` field with the following types:

| Field Number | Type | Meaning |
|---|---|---|
| 1 | `Trackpoint` | GPS measuring point (main data) |
| 2 | `TimerEvent` | Start timer event |
| 16 | `ButtonEvent` | Button press |
| 17 | `HardwareDescription` | Device information |
| 18 | `MagneticDeclination` | Magnetic declination |

The `Trackpoint` sub-message contains the coordinates as **zigzag-encoded `sint32` values** multiplied by 1×10⁷ (for lat/longitude) or 1000 (for quaternion components).

### 2.3 Plugin Structure

The plugin consists of the following modules:

| File | Function |
|---|---|
| `vtktool.py` | Core parser: reads `.VTK` → list of dictionaries |
| `vtk_pb2.py` | Generated protobuf module (from `vtk.proto`) |
| `geojson_exporter.py` | Converts trackpoints to GeoJSON |
| `postgis_loader.py` | Loads trackpoints into PostGIS via psycopg2 |
| `dialog.py` | Qt dialog with three tabs (CSV / GeoJSON / PostGIS) |
| `plugin.py` | QGIS plugin entry point |
| `__init__.py` | Plugin registration (`classFactory`) |
| `metadata.txt` | Plugin metadata for QGIS Plugin Manager |

### 2.4 Important Implementation Details

**Zigzag Decoding:** Coordinates are stored as `sint32` zigzag-encoded. Without correct decoding, only `0.0` values ​​result:

```python
def _zz(n): return (n >> 1) ^ -(n & 1)

lat = _zz(tp.latitudeE7) / 1e7 # e.g., 478025024 → 47.8025024°
lon = _zz(tp.longitudeE7) / 1e7
sog = tp.sog_knotsE1 / 10.0 # e.g., 52 → 5.2 kn
```

**Quaternion → Euler angle:** Course, heel, and trim are calculated from the four quaternion components:

```python
heading = atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z)) # mag_heading
heel = atan2(2*(w*x + y*z), 1 - 2*(x*x + y*y)) # Heel
pitch = asin (2*(w*y - z*x)) # Trim
```

**Fallback Parser:** If `google.protobuf` is not installed in the QGIS Python environment, a built-in, pure Python Protobuf decoder is used as a fallback.

### 2.5 Installation

```
QGIS → Extensions → Manage and Install Extensions

→ Install from ZIP → Select vtk_importer_v4.zip

```

For PostGIS export, additionally (OSGeo4W Shell / Terminal):

```bash
`pip install psycopg2-binary`

```

---

## 3. Data Fields

| Field | Description | Unit / Format | Example |
|---|---|---|---|
| `time` | Timestamp in UTC | `DD.MM.YY HH:MM:SS (UTC)` | `18.04.26 09:42:27 (UTC)` |
| `latitude` | WGS84 latitude | Decimal degrees | `43.8478535` |
| longitude` | WGS84 longitude | Decimal degrees | `15.5327151` |
| `sog` | Speed ​​Over Ground | Nodes | `6.1` |
| `cog` | Course Over Ground | Degrees (0–359°) | `317` |
| `q1` | Quaternion W-component | Dimensionless (−1 … +1) | `−0.928` |
| `q2` | Quaternion X-component | Dimensionless (−1 … +1) | 0.200 |
q3 | Quaternion Y-component | Dimensionless (−1 … +1) | −0.050 |
q4 | Quaternion Z-component | Dimensionless (−1 … +1) | −0.310 |
mag_heading | Magnetic heading (from quaternion) | Degrees (0–359°) | 325 |
heel | Heel angle | Degrees (negative = port) | −20 |
pitch | Trim angle | Degrees (negative = bow dives) | −13 |

### Notes on the Quaternion Fields

The fields `q1`–`q4` represent the device's position in space as a unit quaternion (W, X, Y, Z). Internally, the Velocitek device scales these values ​​by a factor of 1000 and stores them as integers (`q1E3` … `q4E3`). Upon import, these values ​​are normalized back to the range -1 … +1.

`mag_heading`, `heel`, and `pitch` are calculated from these four values. The raw values ​​are particularly useful when custom position calculations or filtering (e.g., Kalman filters) are desired.

---

## 4. Compatibility with QGIS 4

QGIS 4 introduces several changes that affect the plugin:

### What's Changing

| Scope | QGIS 3
x | QGIS 4.x | Adjustment required |
|---|---|---|---|
| Qt version | Qt 5 | Qt 6 | Yes |
| Python imports | `qgis.PyQt` | `qgis.PyQt` (remains) | No |
| PyQt 5 → PyQt 6 | `PyQt 5` direct | `PyQt 6` direct | Only for direct PyQt 5 imports |
| Plugin API | `iface.addPluginToVectorMenu` | likely the same | No |
| `QgsProject` | same | same | No |

### Specific adjustments for QGIS 4

**1. `metadata.txt` – Increase minimum version:**
```ini
qgisMinimumVersion=4.0
```

**2. `dialog.py` – `QLineEdit.Password` → `QLineEdit.EchoMode.Password`** (Qt6 style):
```python
# QGIS 3 (Qt5):
self.pg_password.setEchoMode(QLineEdit.Password)

# QGIS 4 (Qt6):
self.pg_password.setEchoMode(QLineEdit.EchoMode.Password)
```

**3. `dialog.py` – `QFileDialog` Return value:** Remains the same, no changes required.

**4. No more `SIP v1`:** If `sip.setapi()` is called anywhere, it must be removed. This is not the case in the current plugin.

** ### Conclusion

The parser core (`vtktool.py`, `vtk_pb2.py`, `geojson_exporter.py`, `postgis_loader.py`) is completely Qt-independent and runs without modification under QGIS 4. Only `dialog.py` requires an adjustment to `EchoMode`. The plugin can therefore be ported to QGIS 4 with minimal effort.

## 5. Workflow Overview

```

.VTK File (Velocitek GPS)
    │
    ▼
  vtktool.py (Parser)
  • uint16-LE Framing
  • protobuf Decoding
  • Zigzag Coordinates
  • Quaternion → Euler
      │
      ├──► CSV Export
      │   (all fields, UTF-8)
      │
      ├──► GeoJSON Export
      │   (Point Features + optional LineString)
      │   → directly loadable as a QGIS layer
      │
      └──► PostGIS Export
          (table vtk_trackpoints,
          GEOMETRY(Point, 4326),
          GIST index automatically)
```
