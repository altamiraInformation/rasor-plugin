# -*- coding: utf-8 -*-
"""
/***************************************************************************
 rasor
                                 A QGIS plugin
 Plugin in order to generate Rasor compliant data and upload it to the platform
                              -------------------
        begin                : 2015-03-11
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Joan Sala
        email                : joan.sala@altamira-information.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# PyQT4 imports
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import QtCore, QtGui

class rasor_settings:
	'''Save/Load user defined settings'''
	def __init__(self):
		self.qsettings = QSettings()

	def set_user_up(self, val):
		self.qsettings.setValue("rasor_plugin/user_up", val)
	def set_pass_up(self, val):
		self.qsettings.setValue("rasor_plugin/pass_up", val)
	def set_user_down(self, val):
		self.qsettings.setValue("rasor_plugin/user_down", val)
	def set_pass_down(self, val):
		self.qsettings.setValue("rasor_plugin/pass_down", val)

	def get_user_up(self):
		return self.qsettings.value("rasor_plugin/user_up")
	def get_pass_up(self):
		return self.qsettings.value("rasor_plugin/pass_up")
	def get_user_down(self):
		return self.qsettings.value("rasor_plugin/user_down")
	def get_pass_down(self):
		return self.qsettings.value("rasor_plugin/pass_down")
