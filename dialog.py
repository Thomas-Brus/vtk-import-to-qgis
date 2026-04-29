# dialog.py  –  QGIS plugin dialog for VTK Importer

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QComboBox, QFileDialog, QTabWidget, QWidget,
    QSpinBox, QMessageBox, QProgressBar
)


class VtkImporterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VTK Importer – Velocitek GPS")
        self.setMinimumWidth(520)
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # ── Input file ────────────────────────────────────────────────────────
        input_group = QGroupBox("Eingabe – .VTK Datei")
        input_lay   = QHBoxLayout(input_group)
        self.vtk_path_edit = QLineEdit()
        self.vtk_path_edit.setPlaceholderText("Pfad zur .VTK Datei …")
        btn_browse_vtk = QPushButton("Durchsuchen …")
        btn_browse_vtk.clicked.connect(self._browse_vtk)
        input_lay.addWidget(self.vtk_path_edit)
        input_lay.addWidget(btn_browse_vtk)
        main_layout.addWidget(input_group)

        # ── Tabs: CSV / GeoJSON / PostGIS ─────────────────────────────────────
        tabs = QTabWidget()

        # CSV tab
        csv_tab = QWidget()
        csv_lay = QVBoxLayout(csv_tab)
        csv_lay.setContentsMargins(8, 8, 8, 8)

        csv_out_lay = QHBoxLayout()
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Ausgabe .csv …")
        btn_browse_csv = QPushButton("Durchsuchen …")
        btn_browse_csv.clicked.connect(self._browse_csv_out)
        csv_out_lay.addWidget(self.csv_path_edit)
        csv_out_lay.addWidget(btn_browse_csv)
        csv_lay.addLayout(csv_out_lay)

        self.btn_export_csv = QPushButton("CSV exportieren")
        self.btn_export_csv.clicked.connect(self._export_csv)
        csv_lay.addWidget(self.btn_export_csv)
        csv_lay.addStretch()
        tabs.addTab(csv_tab, "CSV")

        # GeoJSON tab
        geo_tab = QWidget()
        geo_lay = QVBoxLayout(geo_tab)
        geo_lay.setContentsMargins(8, 8, 8, 8)

        geo_out_lay = QHBoxLayout()
        self.geo_path_edit = QLineEdit()
        self.geo_path_edit.setPlaceholderText("Ausgabe .geojson …")
        btn_browse_geo = QPushButton("Durchsuchen …")
        btn_browse_geo.clicked.connect(self._browse_geo_out)
        geo_out_lay.addWidget(self.geo_path_edit)
        geo_out_lay.addWidget(btn_browse_geo)
        geo_lay.addLayout(geo_out_lay)

        self.chk_linestring = QCheckBox("Auch als LineString (Tracklinie) exportieren")
        self.chk_load_layer = QCheckBox("Layer automatisch in QGIS laden")
        self.chk_load_layer.setChecked(True)
        geo_lay.addWidget(self.chk_linestring)
        geo_lay.addWidget(self.chk_load_layer)

        self.btn_export_geo = QPushButton("GeoJSON exportieren")
        self.btn_export_geo.clicked.connect(self._export_geojson)
        geo_lay.addWidget(self.btn_export_geo)
        geo_lay.addStretch()
        tabs.addTab(geo_tab, "GeoJSON")

        # PostGIS tab
        pg_tab = QWidget()
        pg_lay = QVBoxLayout(pg_tab)
        pg_lay.setContentsMargins(8, 8, 8, 8)

        def _row(label, widget):
            h = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(90)
            h.addWidget(lbl)
            h.addWidget(widget)
            return h

        self.pg_host     = QLineEdit("localhost")
        self.pg_port     = QSpinBox()
        self.pg_port.setRange(1, 65535)
        self.pg_port.setValue(5432)
        self.pg_db       = QLineEdit()
        self.pg_db.setPlaceholderText("datenbankname")
        self.pg_user     = QLineEdit()
        self.pg_user.setPlaceholderText("postgres")
        self.pg_password = QLineEdit()
        self.pg_password.setEchoMode(QLineEdit.Password)
        self.pg_schema   = QLineEdit("public")
        self.pg_table    = QLineEdit("vtk_trackpoints")

        pg_lay.addLayout(_row("Host:", self.pg_host))
        pg_lay.addLayout(_row("Port:", self.pg_port))
        pg_lay.addLayout(_row("Datenbank:", self.pg_db))
        pg_lay.addLayout(_row("Benutzer:", self.pg_user))
        pg_lay.addLayout(_row("Passwort:", self.pg_password))
        pg_lay.addLayout(_row("Schema:", self.pg_schema))
        pg_lay.addLayout(_row("Tabelle:", self.pg_table))

        self.btn_load_pg = QPushButton("In PostGIS laden")
        self.btn_load_pg.clicked.connect(self._load_postgis)
        pg_lay.addWidget(self.btn_load_pg)
        pg_lay.addStretch()
        tabs.addTab(pg_tab, "PostGIS")

        main_layout.addWidget(tabs)

        # Progress / status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_label = QLabel("")
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)

        # Close button
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.close)
        main_layout.addWidget(btn_close)

    # ── File browser helpers ──────────────────────────────────────────────────
    def _browse_vtk(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "VTK Datei öffnen", "", "VTK Files (*.VTK *.vtk)")
        if path:
            self.vtk_path_edit.setText(path)

    def _browse_csv_out(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV speichern", "", "CSV Files (*.csv)")
        if path:
            self.csv_path_edit.setText(path)

    def _browse_geo_out(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "GeoJSON speichern", "", "GeoJSON Files (*.geojson)")
        if path:
            self.geo_path_edit.setText(path)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _get_vtk_path(self):
        path = self.vtk_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Fehler", "Bitte eine .VTK Datei auswählen.")
            return None
        return path

    def _export_csv(self):
        vtk = self._get_vtk_path()
        if not vtk:
            return
        csv_out = self.csv_path_edit.text().strip()
        if not csv_out:
            QMessageBox.warning(self, "Fehler", "Bitte einen CSV Ausgabepfad angeben.")
            return
        try:
            from .vtktool import vtk_to_csv
            self._set_busy(True, "Exportiere CSV …")
            n = vtk_to_csv(vtk, csv_out)
            self._set_busy(False)
            self.status_label.setText(f"✓ {n} Trackpoints → {csv_out}")
            QMessageBox.information(self, "Fertig",
                f"{n} Trackpoints erfolgreich nach\n{csv_out}\nexportiert.")
        except Exception as e:
            self._set_busy(False)
            QMessageBox.critical(self, "Fehler", str(e))

    def _export_geojson(self):
        vtk = self._get_vtk_path()
        if not vtk:
            return
        geo_out = self.geo_path_edit.text().strip()
        if not geo_out:
            QMessageBox.warning(self, "Fehler", "Bitte einen GeoJSON Ausgabepfad angeben.")
            return
        try:
            from .vtktool import parse_vtk_file
            from .geojson_exporter import rows_to_geojson
            self._set_busy(True, "Lese VTK …")
            rows = parse_vtk_file(vtk)
            self._set_busy(True, "Schreibe GeoJSON …")
            rows_to_geojson(rows, geo_out,
                            as_linestring=self.chk_linestring.isChecked())
            self._set_busy(False)
            self.status_label.setText(f"✓ {len(rows)} Punkte → {geo_out}")

            if self.chk_load_layer.isChecked():
                from qgis.core import QgsVectorLayer, QgsProject
                layer = QgsVectorLayer(geo_out,
                    f"VTK – {__import__('os').path.basename(vtk)}", "ogr")
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
                    self.status_label.setText(
                        self.status_label.text() + " – Layer geladen ✓")

            QMessageBox.information(self, "Fertig",
                f"{len(rows)} Trackpoints → {geo_out}")
        except Exception as e:
            self._set_busy(False)
            QMessageBox.critical(self, "Fehler", str(e))

    def _load_postgis(self):
        vtk = self._get_vtk_path()
        if not vtk:
            return
        conn_params = {
            'host':     self.pg_host.text().strip(),
            'port':     self.pg_port.value(),
            'database': self.pg_db.text().strip(),
            'user':     self.pg_user.text().strip(),
            'password': self.pg_password.text(),
        }
        if not conn_params['database']:
            QMessageBox.warning(self, "Fehler", "Bitte Datenbankname angeben.")
            return
        try:
            from .vtktool import parse_vtk_file
            from .postgis_loader import load_rows_to_postgis
            import os
            self._set_busy(True, "Lese VTK …")
            rows = parse_vtk_file(vtk)
            self._set_busy(True, f"Lade {len(rows)} Punkte in PostGIS …")
            n = load_rows_to_postgis(
                rows, conn_params,
                schema=self.pg_schema.text().strip() or 'public',
                table=self.pg_table.text().strip() or 'vtk_trackpoints',
                source_file=os.path.basename(vtk)
            )
            self._set_busy(False)
            self.status_label.setText(
                f"✓ {n} Zeilen in {conn_params['database']}."
                f"{self.pg_schema.text()}.{self.pg_table.text()} geladen")
            QMessageBox.information(self, "Fertig",
                f"{n} Trackpoints erfolgreich in PostGIS geladen.")
        except Exception as e:
            self._set_busy(False)
            QMessageBox.critical(self, "Fehler", str(e))

    def _set_busy(self, busy, msg=""):
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)   # indeterminate
            self.status_label.setText(msg)
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
        QtWidgets.QApplication.processEvents()
