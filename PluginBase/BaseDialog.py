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
from qgis.gui import *
import shutil
import os.path
from qgis.PyQt.QtCore import Qt
from qgis.gui import *
import os
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import subprocess
import processing
import shutil
import sys



from PyQt5.QtWidgets import QDialog

from PluginBase.gui.generated.ui_dialog import Ui_BaseDialog


try:
    import sys
    from pydevd import *
except:
    None
 

#Path_config= str('C:/Users/omary/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/PluginBase/config.ini')
Path_config= " "
Path_config1= ("D:/")

class BaseDialog(QDialog, Ui_BaseDialog):
    def __init__(self, iface):
        QDialog.__init__(self)
        self.setupUi(self)
        self.iface = iface
        self.lastOpenedFile = None
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))


    def NewProject(self,ptype=False):
        template=os.path.join(self.plugin_dir, "config/config.ini")
        if ptype:
            tempname = QFileDialog.getSaveFileName(self, "Save "+ptype+" project as",Path_config1, "*.ini")
        else:
            tempname = QFileDialog.getSaveFileName(self, "Save .ini as", Path_config1, "*.ini")
     
        out=str(tempname).partition("('")[2].partition("',")[0]
        newPath = shutil.copy(template, out)
        # clear project canvas
        qgsProject = QgsProject.instance()
        qgsProject.clear()
        global Path_config
        Path_config=newPath
        self.lineEdit_4.setText(" ") 
        self.lineEdit_2.setText(" ") 
        self.lineEdit_3.setText(" ") 
        self.lineEdit.setText(" ") 
        Default_start_date = "01/01/2000";
        Data = QDate.fromString(Default_start_date,"dd/MM/yyyy");
        self.dateEdit.setDate(Data)
        Default_End_date = "31/12/2000";
        Data2 = QDate.fromString(Default_start_date,"dd/MM/yyyy");
        self.dateEdit_2.setDate(Data2)
       
        
        
        
    def showlabel(self):
        a=self.mMapLayerComboBox.currentLayer().name()
        self.label.setText(a)

    def SetInput(self):
    
        selected_dir = QFileDialog.getExistingDirectory(self, caption='Choose Directory', directory=os.getcwd())
        self.lineEdit_4.setText(selected_dir) 
        OutputPathConfig = self.lineEdit_4.text()
        

        a_file = open(Path_config, "r")
        list_of_lines = a_file.readlines()
        list_of_lines[3] = str('input = '+OutputPathConfig+'\n')
        a_file = open(Path_config, "w")
        a_file.writelines(list_of_lines)
        a_file.close()

    def SetOutput(self):

        selected_dir = QFileDialog.getExistingDirectory(self, caption='Choose Directory',  directory=os.getcwd())
        self.lineEdit_2.setText(selected_dir) 
        OutputPathConfig = self.lineEdit_2.text()
        

        a_file = open(Path_config, "r")
        list_of_lines = a_file.readlines()
        list_of_lines[6] = str('output = '+OutputPathConfig+'\n')
        a_file = open(Path_config, "w")
        a_file.writelines(list_of_lines)
        a_file.close()

          

    def SearchDem(self):
        Dem_File, _= QFileDialog.getOpenFileName(self,"Search Dem",self.lastOpenedFile,"*.map")
        self.lineEdit.setText(Dem_File) 
        DemPathConfig = self.lineEdit.text()
        self.fileInfo=QFileInfo(Dem_File)
        self.baseName=self.fileInfo.baseName()
        self.Demlayer=QgsRasterLayer(Dem_File,self.baseName)
        QgsProject.instance().addMapLayer(self.Demlayer)
        
     
        a_file = open(Path_config, "r")
        list_of_lines = a_file.readlines()
        list_of_lines[9] = str('dem = ' +DemPathConfig+'\n')
        a_file = open(Path_config, "w")
        a_file.writelines(list_of_lines)
        a_file.close()

    def SearchKc_min(self):
        Kc_min_File, _= QFileDialog.getOpenFileName(self,"SearchKc_min",self.lastOpenedFile,"*.txt")
        self.lineEdit_3.setText(Kc_min_File) 
        Kc_minPathConfig = self.lineEdit_3.text()

        a_file = open(Path_config, "r")
        list_of_lines = a_file.readlines()
        list_of_lines[17] = str('Kc_min = '+Kc_minPathConfig+'\n')
        a_file = open(Path_config, "w")
        a_file.writelines(list_of_lines)
        a_file.close()

    def SetStartDate(self):
 
        year=str(self.dateEdit.date().year())
        month=str(self.dateEdit.date().month())
        day=str(self.dateEdit.date().day())
               

        a_file = open(Path_config, "r")
        list_of_lines = a_file.readlines()
        list_of_lines[13] = str('start = '+day+"/"+month+"/"+year+'\n')
        a_file = open(Path_config, "w")
        a_file.writelines(list_of_lines)
        a_file.close()

    def SetEndDate(self):
     
        year=str(self.dateEdit_2.date().year())
        month=str(self.dateEdit_2.date().month())
        day=str(self.dateEdit_2.date().day())
               

        a_file = open(Path_config, "r")
        list_of_lines = a_file.readlines()
        list_of_lines[14] = str('end = '+day+"/"+month+"/"+year+'\n')
        a_file = open(Path_config, "w")
        a_file.writelines(list_of_lines)
        a_file.close()


    # def DLL_Create(self):
        
    #     command ="path to .exe"
    #     os.chdir("path files")
    #     subprocess.run(command, shell=True, check=True)
    #     test_File= 
    #     self.fileInfo=QFileInfo(test_File)
    #     self.baseName=self.fileInfo.baseName()
    #     self.testlayer=QgsRasterLayer(test_File,self.baseName)
    #     QgsProject.instance().addMapLayer(self.testlayer)


    def saveAsProject(self, ptype=False):
        if ptype:
            tempname = QFileDialog.getSaveFileName(self, "Save "+ptype+" project as",Path_config2, "*.qgs")
        else:
            tempname = QFileDialog.getSaveFileName(self, "Save current project as", Path_config2, "*.qgs")
        #if tempname:
            #self.currentConfigFileName = tempname
            #self.saveProject()
            # write the qgs project file
        qgsProjectFileName = str(tempname)
        qgsProject = QgsProject.instance()
        qgsProject.setFileName(qgsProjectFileName)
        qgsProject.write()