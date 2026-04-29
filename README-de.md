
# VTK Importer – QGIS Plugin
## Dokumentation & Datenfeldbeschreibung

---

## 1. Hintergrund

Velocitek GPS-Geräte (z. B. ProStart) speichern Segeldaten im proprietären `.VTK`-Format. Das Open-Source-Projekt [velocitek/vtk_protocol](https://github.com/velocitek/vtk_protocol) auf GitHub dokumentiert das Binärformat und stellt eine Python-Bibliothek bereit.

Ziel dieses Plugins ist es, `.VTK`-Dateien direkt in QGIS zu öffnen und die GPS-Trackdaten als CSV, GeoJSON oder PostGIS-Layer bereitzustellen.

---

## 2. Wie das Plugin entstanden ist

### 2.1 Analyse des Dateiformats

Das `.VTK`-Format verwendet **Protocol Buffers (protobuf)** als Serialisierungsformat. Die Nachrichten sind length-delimited verpackt – allerdings nicht mit dem üblichen protobuf-Varint-Prefix, sondern mit einem **2-Byte Little-Endian Längenprefix** (`uint16 LE`):

```
[2 Byte LE Länge] [N Byte protobuf vtk.Record]
[2 Byte LE Länge] [N Byte protobuf vtk.Record]
...
```

Dieses Format wurde durch Analyse eines Hex-Dumps einer echten `.VTK`-Datei identifiziert:

```
0000: 09 00 8a 01 06 08 01 10 07 18 2e 22 00 0a 20 08
      ^^^^^ = 9 Bytes Länge (uint16 LE)
```

### 2.2 Protobuf-Schema (vtk.proto)

Das `Record`-Message enthält ein `oneof`-Feld mit folgenden Typen:

| Feldnummer | Typ | Bedeutung |
|---|---|---|
| 1 | `Trackpoint` | GPS-Messpunkt (Hauptdaten) |
| 2 | `TimerEvent` | Startuhr-Ereignis |
| 16 | `ButtonEvent` | Knopfdruck |
| 17 | `HardwareDescription` | Geräteinformationen |
| 18 | `MagneticDeclination` | Magnetische Deklination |

Das `Trackpoint`-Sub-Message enthält die Koordinaten als **zigzag-kodierte `sint32`-Werte** multipliziert mit 1×10⁷ (für Lat/Lon) bzw. 1000 (für Quaternion-Komponenten).

### 2.3 Aufbau des Plugins

Das Plugin besteht aus folgenden Modulen:

| Datei | Funktion |
|---|---|
| `vtktool.py` | Kern-Parser: liest `.VTK` → Liste von Dicts |
| `vtk_pb2.py` | Generiertes protobuf-Modul (aus `vtk.proto`) |
| `geojson_exporter.py` | Konvertiert Trackpoints → GeoJSON |
| `postgis_loader.py` | Lädt Trackpoints via psycopg2 in PostGIS |
| `dialog.py` | Qt-Dialog mit drei Tabs (CSV / GeoJSON / PostGIS) |
| `plugin.py` | QGIS-Plugin-Einstiegspunkt |
| `__init__.py` | Plugin-Registrierung (`classFactory`) |
| `metadata.txt` | Plugin-Metadaten für QGIS Plugin Manager |

### 2.4 Wichtige Implementierungsdetails

**Zigzag-Dekodierung:** Koordinaten sind als `sint32` zigzag-kodiert gespeichert. Ohne korrekte Dekodierung ergeben sich nur `0.0`-Werte:

```python
def _zz(n): return (n >> 1) ^ -(n & 1)

lat = _zz(tp.latitudeE7) / 1e7   # z.B. 478025024 → 47.8025024°
lon = _zz(tp.longitudeE7) / 1e7
sog = tp.sog_knotsE1 / 10.0       # z.B. 52 → 5.2 kn
```

**Quaternion → Euler-Winkel:** Kurs, Krängung und Trimm werden aus den vier Quaternion-Komponenten berechnet:

```python
heading = atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))  # mag_heading
heel    = atan2(2*(w*x + y*z), 1 - 2*(x*x + y*y))   # Krängung
pitch   = asin (2*(w*y - z*x))                        # Trimm
```

**Fallback-Parser:** Falls `google.protobuf` in der QGIS-Python-Umgebung nicht installiert ist, greift ein eingebauter reiner Python-Protobuf-Decoder als Fallback.

### 2.5 Installation

```
QGIS → Erweiterungen → Erweiterungen verwalten und installieren
→ Aus ZIP installieren → vtk_importer_v4.zip auswählen
```

Für PostGIS-Export zusätzlich (OSGeo4W Shell / Terminal):

```bash
pip install psycopg2-binary
```

---

## 3. Datenfelder

| Feld | Beschreibung | Einheit / Format | Beispiel |
|---|---|---|---|
| `time` | Zeitstempel in UTC | `DD.MM.YY HH:MM:SS (UTC)` | `18.04.26 09:42:27 (UTC)` |
| `latitude` | Breitengrad WGS84 | Dezimalgrad | `43.8478535` |
| `longitude` | Längengrad WGS84 | Dezimalgrad | `15.5327151` |
| `sog` | Speed Over Ground | Knoten | `6.1` |
| `cog` | Course Over Ground | Grad (0–359°) | `317` |
| `q1` | Quaternion W-Komponente | dimensionslos (−1 … +1) | `−0.928` |
| `q2` | Quaternion X-Komponente | dimensionslos (−1 … +1) | `0.200` |
| `q3` | Quaternion Y-Komponente | dimensionslos (−1 … +1) | `−0.050` |
| `q4` | Quaternion Z-Komponente | dimensionslos (−1 … +1) | `−0.310` |
| `mag_heading` | Magnetischer Kurs (aus Quaternion) | Grad (0–359°) | `325` |
| `heel` | Krängung / Roll-Winkel | Grad (neg. = Backbord) | `−20` |
| `pitch` | Trimm / Pitch-Winkel | Grad (neg. = Bug taucht) | `−13` |

### Hinweise zu den Quaternion-Feldern

Die Felder `q1`–`q4` repräsentieren die Lage des Geräts im Raum als Einheitsquaternion (W, X, Y, Z). Sie werden vom Velocitek-Gerät intern mit dem Faktor 1000 skaliert als Integer gespeichert (`q1E3` … `q4E3`) und beim Einlesen wieder auf den Wertebereich −1 … +1 normiert.

Aus diesen vier Werten werden `mag_heading`, `heel` und `pitch` berechnet. Die Rohwerte sind vor allem dann nützlich, wenn eine eigene Lageberechnung oder Filterung (z. B. Kalman-Filter) gewünscht wird.

---

## 4. Kompatibilität mit QGIS 4

QGIS 4 bringt einige Änderungen mit, die das Plugin betreffen:

### Was sich ändert

| Bereich | QGIS 3.x | QGIS 4.x | Anpassung nötig |
|---|---|---|---|
| Qt-Version | Qt 5 | Qt 6 | Ja |
| Python-Imports | `qgis.PyQt` | `qgis.PyQt` (bleibt) | Nein |
| PyQt5 → PyQt6 | `PyQt5` direkt | `PyQt6` direkt | Nur bei direkten PyQt5-Imports |
| Plugin-API | `iface.addPluginToVectorMenu` | voraussichtlich gleich | Nein |
| `QgsProject` | gleich | gleich | Nein |

### Konkrete Anpassungen für QGIS 4

**1. `metadata.txt` – Mindestversion erhöhen:**
```ini
qgisMinimumVersion=4.0
```

**2. `dialog.py` – `QLineEdit.Password` → `QLineEdit.EchoMode.Password`** (Qt6-Stil):
```python
# QGIS 3 (Qt5):
self.pg_password.setEchoMode(QLineEdit.Password)

# QGIS 4 (Qt6):
self.pg_password.setEchoMode(QLineEdit.EchoMode.Password)
```

**3. `dialog.py` – `QFileDialog` Rückgabewert:** bleibt gleich, kein Änderungsbedarf.

**4. Kein `SIP v1` mehr:** Falls irgendwo `sip.setapi()` aufgerufen wird, muss das entfernt werden. Im aktuellen Plugin ist das nicht der Fall.

### Fazit

Der Parser-Kern (`vtktool.py`, `vtk_pb2.py`, `geojson_exporter.py`, `postgis_loader.py`) ist vollständig Qt-unabhängig und läuft ohne Änderung unter QGIS 4. Nur `dialog.py` benötigt die eine Anpassung bei `EchoMode`. Das Plugin ist damit mit minimalem Aufwand auf QGIS 4 portierbar.

---

## 5. Workflow-Übersicht

```
.VTK Datei (Velocitek GPS)
        │
        ▼
  vtktool.py (Parser)
  • uint16-LE Framing
  • protobuf Dekodierung
  • Zigzag-Koordinaten
  • Quaternion → Euler
        │
        ├──► CSV-Export
        │    (alle Felder, UTF-8)
        │
        ├──► GeoJSON-Export
        │    (Point-Features + opt. LineString)
        │    → direkt als QGIS-Layer ladbar
        │
        └──► PostGIS-Export
             (Tabelle vtk_trackpoints,
              GEOMETRY(Point, 4326),
              GIST-Index automatisch)
```

