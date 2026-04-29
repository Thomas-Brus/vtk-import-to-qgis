# plugin.py  –  VTK Importer QGIS Plugin
import os
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication


class VtkImporterPlugin:
    def __init__(self, iface):
        self.iface    = iface
        self.action   = None
        self.dialog   = None
        self._plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icon_path = os.path.join(self._plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QgsApplication.getThemeIcon('/mActionAddOgrLayer.svg')

        self.action = QAction(icon, "VTK Importer", self.iface.mainWindow())
        self.action.setToolTip("Velocitek .VTK Dateien importieren")
        self.action.triggered.connect(self.run)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu("&VTK Importer", self.action)

    def unload(self):
        self.iface.removePluginVectorMenu("&VTK Importer", self.action)
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def run(self):
        from .dialog import VtkImporterDialog
        if self.dialog is None:
            self.dialog = VtkImporterDialog(self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
