# __init__.py  –  QGIS plugin entry point
def classFactory(iface):
    from .plugin import VtkImporterPlugin
    return VtkImporterPlugin(iface)
