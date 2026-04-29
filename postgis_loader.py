# postgis_loader.py
# Loads trackpoint rows into a PostGIS table via psycopg2.
#
# Requirements: psycopg2-binary  (pip install psycopg2-binary)
# or use QGIS's built-in PostgreSQL provider as alternative.

import os


# ── psycopg2 availability check ───────────────────────────────────────────────
def _get_psycopg2():
    try:
        import psycopg2
        return psycopg2
    except ImportError:
        raise ImportError(
            "psycopg2 is not installed.\n"
            "Install it inside QGIS's Python environment:\n"
            "  OSGeo4W Shell: pip install psycopg2-binary\n"
            "  macOS/Linux:   pip3 install psycopg2-binary"
        )


# ── Connection helper ─────────────────────────────────────────────────────────
def make_connection(host, port, database, user, password):
    """Return an open psycopg2 connection."""
    psycopg2 = _get_psycopg2()
    conn = psycopg2.connect(
        host=host,
        port=int(port),
        dbname=database,
        user=user,
        password=password,
    )
    return conn


# ── Schema / table setup ──────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {schema}.{table} (
    id           SERIAL PRIMARY KEY,
    timestamp    BIGINT,
    speed_knots  DOUBLE PRECISION,
    heading      DOUBLE PRECISION,
    heel         DOUBLE PRECISION,
    pitch        DOUBLE PRECISION,
    source_file  TEXT,
    geom         GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS {schema}_{table}_geom_idx
    ON {schema}.{table} USING GIST (geom);
"""

INSERT_SQL = """
INSERT INTO {schema}.{table}
    (timestamp, speed_knots, heading, heel, pitch, source_file, geom)
VALUES
    (%(timestamp)s, %(speed_knots)s, %(heading)s, %(heel)s, %(pitch)s,
     %(source_file)s,
     ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326));
"""


def load_rows_to_postgis(rows, conn_params, schema='public',
                         table='vtk_trackpoints', source_file=''):
    """
    Insert trackpoint rows into PostGIS.

    Parameters
    ----------
    rows        : list of dicts from vtktool.parse_vtk_file
    conn_params : dict with keys host, port, database, user, password
    schema      : target schema (default 'public')
    table       : target table name (default 'vtk_trackpoints')
    source_file : original .VTK filename stored as metadata

    Returns
    -------
    int  number of rows inserted
    """
    if not rows:
        return 0

    psycopg2 = _get_psycopg2()

    conn   = make_connection(**conn_params)
    cursor = conn.cursor()

    # Ensure PostGIS extension exists
    cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Create table if needed
    cursor.execute(
        CREATE_TABLE_SQL.format(schema=schema, table=table)
    )

    # Insert rows
    insert_sql = INSERT_SQL.format(schema=schema, table=table)
    for row in rows:
        row_copy = dict(row)
        row_copy['source_file'] = source_file
        cursor.execute(insert_sql, row_copy)

    conn.commit()
    count = len(rows)
    cursor.close()
    conn.close()
    return count


def load_csv_to_postgis(csv_path, conn_params,
                        schema='public', table='vtk_trackpoints'):
    """Read a VTK-generated CSV and push it to PostGIS."""
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
    source = os.path.basename(csv_path)
    return load_rows_to_postgis(rows, conn_params,
                                schema=schema, table=table,
                                source_file=source)
