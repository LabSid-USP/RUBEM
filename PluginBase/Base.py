# -*- coding: utf-8 -*-
"""
/***************************************************************************
 **Nombre del plugin
                                 A QGIS plugin
 **Descripcion
                             -------------------
        begin                : **Fecha
        copyright            : **COPYRIGHT
        email                : **Mail de contacto
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 #   any later version.                                                    *
 *                                                                         *
 ***************************************************************************/
"""
import os.path
from qgis.core import *

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QAction

from PluginBase.BaseDialog import BaseDialog
import PluginBase.gui.generated.resources_rc

try:
    import sys
    from pydevd import *
except:
    None

class Base:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction(QIcon(":/imgBase/images/icon.jpg"), u"Template", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&Template", self.action)


    def unload(self):
        self.iface.removePluginMenu(u"&Template", self.action)
        self.iface.removeToolBarIcon(self.action)
 

    def run(self):
        self.dlg = BaseDialog(self.iface)
        self.dlg.setWindowFlags(Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        self.dlg.exec_()