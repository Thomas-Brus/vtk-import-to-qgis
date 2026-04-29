# geojson_exporter.py
# Converts a list of trackpoint dicts (from vtktool.parse_vtk_file)
# to a GeoJSON FeatureCollection file.

import json


def rows_to_geojson(rows, output_path, as_linestring=False):
    """
    Write trackpoint rows as GeoJSON.

    Parameters
    ----------
    rows          : list of dicts with keys latitude, longitude, + attributes
    output_path   : path to the output .geojson file
    as_linestring : if True, also add a LineString track geometry

    Returns
    -------
    path to the written file
    """
    features = []

    for row in rows:
        lat = row.get('latitude')
        lon = row.get('longitude')
        if lat is None or lon is None:
            continue

        properties = {k: v for k, v in row.items()
                      if k not in ('latitude', 'longitude')}

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]   # GeoJSON is [lon, lat]
            },
            "properties": properties
        }
        features.append(feature)

    if as_linestring and len(rows) >= 2:
        coords = [[r['longitude'], r['latitude']] for r in rows
                  if r.get('latitude') and r.get('longitude')]
        track_feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "type": "track",
                "point_count": len(coords)
            }
        }
        features.append(track_feature)

    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "EPSG:4326"}
        },
        "features": features
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    return output_path


def csv_to_geojson(csv_path, geojson_path, as_linestring=False):
    """Read a CSV produced by vtktool and write GeoJSON."""
    import csv
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                'timestamp':   int(row.get('timestamp', 0)),
                'latitude':    float(row.get('latitude', 0)),
                'longitude':   float(row.get('longitude', 0)),
                'speed_knots': float(row.get('speed_knots', 0)),
                'heading':     float(row.get('heading', 0)),
                'heel':        float(row.get('heel', 0)),
                'pitch':       float(row.get('pitch', 0)),
            })
    return rows_to_geojson(rows, geojson_path, as_linestring=as_linestring)
