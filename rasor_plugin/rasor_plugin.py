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

# QGIS imports
from qgis.core import *
import qgis.utils
from qgis.gui import QgsMessageBar

# Custom imports RASOR
from rasor_api import rasor_api

# Initialize Qt resources from file resources.py
import resources_rc

# Import the code for the dialog
from rasor_plugin_dialog import rasorDialog
from rasor_plugin_down_dialog import rasorDownDialog
import os.path, json, tempfile, sys
from os.path import expanduser

# Global variables
user=""
pwd=""
haz=""
ecat=""
eatt=""
imp=""
evaluation=""
haz_cat=""
rlayers=""
first=1
rapi = rasor_api()

class rasor:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
	global haz, ecat, imp, eatt, evaluation, rapi, first, user, pwd, haz_cat, rlayers
	
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        self.cache_dir = os.path.dirname(__file__)+'/rapi_cache'
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self.plugin_dir,'i18n','rasor_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = rasorDialog()
        self.dlg_down = rasorDownDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Rasor Plugin')

	# TODO: We are going to let the user set this up in a future iteration
	self.toolbar = self.iface.addToolBar(u'rasor')
	self.toolbar.setObjectName(u'rasor')

	# Get RASOR info
	if first:
		# Saved user preferences
		user=rapi.load_file(self.cache_dir+'/infoU')
		pwd=rapi.load_file(self.cache_dir+'/infoP')
		server=rapi.load_file(self.cache_dir+'/server')
		rapi.set_server(server)
		first=0

		# Saved impacts/hazards/exposures/attributes/values
		imp=rapi.download_json(self.cache_dir+'/impact_types.json','/rasorapi/db/impact/types', False)
		haz=rapi.download_json(self.cache_dir+'/hazard_types.json','/rasorapi/db/hazard/hazards', False)
		ecat=rapi.download_json(self.cache_dir+'/exposure_categories.json','/rasorapi/db/exposure/categories', False)
		eatt=rapi.download_json(self.cache_dir+'/exposure_attributes.json','/rasorapi/db/exposure/attributes', False)
		evaluation=rapi.download_json(self.cache_dir+'/exposure_values.json','/rasorapi/db/exposure/valuesdecode', False)
				
		# Saved hazard evaluations
		haz_cat={}
		for elem in ecat['objects']:
			haz_cat[str(elem['id'])]=rapi.download_json(self.cache_dir+'/haz_cat'+str(elem['id'])+'.json','/rasorapi/db/hazard/hazardsattributes/?category='+str(elem['id']), False)
	
    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('rasor', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)
        return action

    def initGui(self):
		icon_up_path = ':/plugins/rasor/rasor_icon_upload.png'	
		icon_new_path = ':/plugins/rasor/rasor_icon_new.png'
		icon_build_path = ':/plugins/rasor/rasor_icon_buildings.png'
		icon_roads_path = ':/plugins/rasor/rasor_icon_osm.png'
			
		"""Create new exposure layer"""        	
		self.add_action(
			icon_new_path,
			text=self.tr(u'new RASOR exposure layer'),
			callback=self.run,
			parent=self.iface.mainWindow())

		"""Upload layer to RASOR-API"""        	    
		self.add_action(
			icon_up_path,
			text=self.tr(u'upload RASOR layer'),
			callback=self.run_upload,
			parent=self.iface.mainWindow())

		"""Download layer from RASOR-API"""        		    
		self.add_action(
			icon_roads_path,
			text=self.tr(u'download RASOR layer'),
			callback=self.run_download,
			parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Rasor Plugin'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
	global haz, ecat, eatt, evaluation, imp, haz_cat
	"""Create a new RASOR exposure layer"""

	# Categories single selection
	c=0
	self.dlg.exposureBox.clear()
	for elem in ecat['objects']:
		self.dlg.exposureBox.addItem(str(elem["name"]))
		c+=1
		
	# Hazards list (multiple selection)
	h=0
	self.dlg.hazardBox.clear()
	for elem in haz['objects']:
		self.dlg.hazardBox.addItem(str(elem["name"]))
		h+=1
	self.dlg.hazardBox.setCurrentRow(0)
	
	# Impacts list (multiple selection)
	i=0	
	self.dlg.impactBox.clear()
	for elem in imp['objects']:
		self.dlg.impactBox.addItem(str(elem["name"]))
		i+=1
	self.dlg.impactBox.setCurrentRow(0)
	
	# show the dialog
	self.dlg.show()

	# Run the dialog event loop
	result = self.dlg.exec_()
        
        # See if OK was pressed	
        if result and self.dlg.layernameText.text() != "":

		# Get new layer name + selection
		layerNew=str(self.dlg.layernameText.text())				
		
		# Exposure selection (single)
		selExp=str(self.dlg.exposureBox.currentText())	
		idExp=rapi.search_id(ecat, 'name', selExp)
		evalu=haz_cat[str(idExp)]
		if selExp == 'lifelines' or 'network' in selExp: 
			geom='Line'
		else:
			geom='Poly'		
		
		# Impact multiple selection (filter)
		selImp=self.dlg.impactBox.selectedItems()
		selImpInd=[]
		for im in selImp:
			idimp=rapi.search_id(imp, 'name', im.text())
			selImpInd.append(idimp)		
		
		# Hazard multiple selection (filter)
		selHaz=self.dlg.hazardBox.selectedItems()
		selAttr=dict()
		for hs in selHaz:
			idhaz=rapi.search_id(haz, 'name', hs.text())
			exphaz=rapi.search_object(evalu,'id',idhaz)		
			for attrib in exphaz['attributes']:
				# Filter by impact type
				if attrib['impact_type'] in selImpInd:
					selAttr[attrib['id']] = attrib
		
		# Get new vector layer (memory)
		if geom == 'Poly':
			ly = QgsVectorLayer("Polygon", layerNew, "memory")	
		else:
			ly = QgsVectorLayer("LineString", layerNew, "memory")		
		pr = ly.dataProvider()

		# Add attributes table
		ly.startEditing()

		# Get exposure attributes (selected)		
		valid_atts=rapi.search_category(eatt, int(idExp))
		
		labels=[]
		ids=[]
		
		# Mandatory
		for att in selAttr:
			attval = selAttr[att]
			labels.append(str(attval['name']))
			ids.append(str(attval['id']))
			pr.addAttributes([QgsField(str(attval['name'])+'#-[MAN]-'+str(int(attval['evaluation'])), QVariant.String)])
		
		# Optional dbf columns
		for att in valid_atts:
			if not(str(att['id']) in ids):
				labels.append(str(att['name']))
				ids.append(str(att['id']))
				pr.addAttributes([QgsField(str(att['name'])+'#-[OPT]-00', QVariant.String)])
	
		# Commit changes
		ly.commitChanges()

		# Get values for each attribute
		ind=0
		for id in ids:
			# Search for possible atts
			arr=rapi.search_attributes(evaluation, int(id))
			vals=dict()
			for att in arr:
				name=str(att['name'])
				iden=str(att['id'])
				if name or iden: 
					vals[name] = iden
			# Assign custom edit form
			if len(vals) > 0:
				ly.setEditorWidgetV2(ind,'ValueMap')
				ly.setEditorWidgetV2Config(ind, vals)
			ind+=1		
		
		# Add layer to QGIS		
		QgsMapLayerRegistry.instance().addMapLayer(ly)
			
    def run_upload(self):
		global rapi, ecat, eatt, user, pwd
		"""Upload a RASOR exposure layer"""	
		# Check connection
		online=rapi.check_connection()
		if online==True:
			print 'ONLINE: Downloading exposure attributes from RASOR platform'
			ecat=rapi.download_json(self.cache_dir+'/exposure_categories.json','/rasorapi/db/exposure/categories', False)
			eatt=rapi.download_json(self.cache_dir+'/exposure_attributes.json','/rasorapi/db/exposure/attributes', False)
		else:
			self.iface.messageBar().pushMessage("Upload layer", "Unable to connect to RASOR platform, you have to be online to upload a layer", level=QgsMessageBar.CRITICAL, duration=5)
			return

		# File selection
		dlgU=QFileDialog()
		dlgU.setWindowTitle('Select files to upload')
		dlgU.setViewMode(QFileDialog.Detail)
		dlgU.setNameFilters([self.tr('Shapefile (*.shp)')])
		dlgU.setDirectory(expanduser("~"))
		dlgU.setDefaultSuffix('.shp')
		if dlgU.exec_():
			# Exposure layer selection
			dlgE=QInputDialog()			
			exp=()
			for elem in ecat['objects']:
				exp+=(str(elem["name"]),)		
			dlgE.setComboBoxItems(exp)
			dlgE.setWindowTitle('Select category')
			dlgE.setOkButtonText('Upload')
			dlgE.setLabelText('Exposure:')
			dlgE.setTextValue('title')
			if dlgE.exec_():
				idcatexp=rapi.search_id(ecat, 'name', dlgE.textValue())
				# User input
				user=self.get_username()
				if user != "":
					rapi.save_file(self.cache_dir+'/infoU', user)
				else:
					return ## Quit
				
				# Password input
				pwd=self.get_password()
				if pwd != "":				
					rapi.save_file(self.cache_dir+'/infoP', pwd)
				else:
					return ## Quit
					
				# Translate & Upload				
				for f in dlgU.selectedFiles():					
					# Setup progressBar	
					self.iface.messageBar().clearWidgets()					
					progressMessageBar = self.iface.messageBar().createMessage("Uploading into the RASOR platform ...")
					progress = QProgressBar()
					progress.setMaximum(10)
					progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
					progressMessageBar.layout().addWidget(progress)
					self.iface.messageBar().pushWidget(progressMessageBar, self.iface.messageBar().INFO)	
					# Do the work					
					file_tmp=rapi.translate_file(self.iface, progress, f, idcatexp, eatt, evaluation, tempfile.gettempdir())
					err=rapi.upload_file(self.iface, progress, f, file_tmp, idcatexp, user, pwd)
					if err == 0:
						# Finish
						self.iface.messageBar().clearWidgets()
						self.iface.messageBar().pushMessage("Upload layer", "Congratulations, files were uploaded", level=QgsMessageBar.INFO, duration=3)

    def get_username(self):
		global user
		userD=QInputDialog()
		userD.setWindowTitle('RASOR auth')
		userD.setLabelText('Username:')
		userD.setTextValue(user)
		userD.setTextEchoMode(QLineEdit.Normal)
		if userD.exec_():
			return userD.textValue()
		return ""
	
    def get_password(self):
		global pwd
		pwdD=QInputDialog()
		pwdD.setWindowTitle('RASOR auth')
		pwdD.setLabelText('Password:')
		pwdD.setTextValue(pwd)
		pwdD.setTextEchoMode(QLineEdit.Password)
		if pwdD.exec_():
			return pwdD.textValue()
		return ""
		
    def run_download(self):
		global rapi, rlayers, ecat, eatt
		# Check connection
		online=rapi.check_connection()
		if online==True:
			print 'ONLINE: Downloading layers from RASOR platform'
			rlayers=rapi.download_json(self.cache_dir+'/rasor_layers.json','/api/layers', True)
			ecat=rapi.download_json(self.cache_dir+'/exposure_categories.json','/rasorapi/db/exposure/categories', False)
			eatt=rapi.download_json(self.cache_dir+'/exposure_attributes.json','/rasorapi/db/exposure/attributes', False)
		else:
			self.iface.messageBar().pushMessage("Download layer", "Unable to connect to RASOR platform, you have to be online to download a layer", level=QgsMessageBar.CRITICAL, duration=5)
			return

		# Load RASOR layers to table
		self.dlg_down.tableWidget.clear()
		self.dlg_down.tableWidget.setHorizontalHeaderItem(0, QTableWidgetItem("RASOR layer name"))
		self.dlg_down.tableWidget.setHorizontalHeaderItem(1, QTableWidgetItem("Owner username"))
		self.dlg_down.tableWidget.setRowCount(len(rlayers['objects']))
		lrow=0

		for rlay in rlayers['objects']:
			self.dlg_down.tableWidget.setItem(lrow,0,QTableWidgetItem(str(rlay["title"])))
			self.dlg_down.tableWidget.setItem(lrow,1,QTableWidgetItem(str(rlay["owner__username"])))
			lrow+=1

		# Resize table
		self.dlg_down.tableWidget.resizeColumnsToContents()

		# Show interface
		self.dlg_down.show()
		
		# Run the dialog event loop
		result = self.dlg_down.exec_()
		itemS = self.dlg_down.tableWidget.currentItem()
		
		# Selection + OK
		if result and itemS:
			# Get selected layer
			selrow = itemS.row()
			layerDown = self.dlg_down.tableWidget.item(selrow,0).text()
			self.dlg_down.destroy()

			## Setup progressBar	
			self.iface.messageBar().clearWidgets()					
			progressMessageBar = self.iface.messageBar().createMessage("Downloading from the RASOR platform ...")
			progress = QProgressBar()
			progress.setMaximum(10)
			progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
			progressMessageBar.layout().addWidget(progress)
			self.iface.messageBar().pushWidget(progressMessageBar, self.iface.messageBar().INFO)			

			# Download
			tempDir=tempfile.gettempdir()
			zipF=rapi.download_file_WFS(progress, layerDown, tempDir)
			if zipF == -1 or os.stat(zipF).st_size != 0:
				shpfile=rapi.unzip_file(progress, zipF, tempDir)
				if shpfile == -1:
					self.iface.messageBar().pushMessage("Download layer", "ERROR, the downloaded file is not a valid ZIP", level=QgsMessageBar.CRITICAL, duration=5)
				else:
					# Translate file
					file_tmp=rapi.inverse_translate_file(self.iface, progress, tempDir+'/'+shpfile, eatt, tempfile.gettempdir())
					layer = self.iface.addVectorLayer(file_tmp, layerDown, "ogr")
					# Finish
					self.iface.messageBar().clearWidgets()
					self.iface.messageBar().pushMessage("Download layer", "Congratulations, files were downloaded", level=QgsMessageBar.INFO, duration=3)
			else:
				self.iface.messageBar().pushMessage("Download layer", "ERROR, trying to connect to RASOR platform", level=QgsMessageBar.CRITICAL, duration=5)
