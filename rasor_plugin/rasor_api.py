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

import urllib, urllib2, httplib2, json, os, socket, sys, base64, zipfile, re
import requests  # downloaded packages
from qgis.gui import QgsMessageBar
from osgeo import gdal
from osgeo import ogr
from urllib2 import HTTPError

class rasor_api:
	#### Internet available (3 seconds timeout)
	def check_connection(self):
		try:
			response=urllib2.urlopen(self.rasor_api, timeout=3)
			return True
		except: pass
		return False

	#### Download a file
	def download_file_WFS(self, progress, layerName, tempDir):
		try:
			progress.setValue(4)
			socket.setdefaulttimeout(10)
			url=self.rasor_api+'/geoserver/wfs?typename=geonode%3A'+layerName+'&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature'
			print url
			req = urllib2.urlopen(url, timeout=180)
			fname=tempDir+'/'+layerName+'.zip'
			with open(fname, 'wb') as f:
			   while True:
			      chunk = req.read(1024)	      
			      if not chunk: break
			      f.write(chunk)
			f.close()
			return fname
		except:
			progress.setValue(0)
			return -1 # ERROR timeout

	#### Download a raster
	def download_raster(self, iface, progress, layerName, tempDir, user, passwd):
		try:
			progress.setValue(7)
			socket.setdefaulttimeout(7200) # 2hours
			# Build URL + access
			url=self.rasor_api+'/geonode-rasters/'+layerName+'/'+layerName+'.geotiff'
			print url
			request=urllib2.Request(url)
			base64string = base64.encodestring('%s:%s' % (user, passwd)).replace('\n', '')
			request.add_header("Authorization", "Basic %s" % base64string) 
			response=urllib2.urlopen(request)
			fname=tempDir+'/'+layerName+'.geotiff'
			print fname
			# Read response in blocks
			with open(fname, 'wb') as f:
			   while True:
			      chunk = response.read(1024)
			      if not chunk: break
			      f.write(chunk)
			f.close()
			return fname
		except ValueError:
			progress.setValue(0)
			iface.messageBar().clearWidgets()
			iface.messageBar().pushMessage("Download layer", "There is something wrong with the attributes on this layer", level=QgsMessageBar.CRITICAL, duration=5)
			return -1 # ERROR timeout
		except HTTPError:
			progress.setValue(0)
			iface.messageBar().clearWidgets()
			iface.messageBar().pushMessage("Download layer", "You are not authorized to download this layer", level=QgsMessageBar.CRITICAL, duration=5)
			return -1 # ERROR Authentication

	#### Unzip file
	def unzip_file(self, progress, zipName, tempDir):
		try:
			progress.setValue(7)			
			res = -1
			## Unzip contents
			zfile = zipfile.ZipFile(zipName)
			for name in zfile.namelist():
				(dirname, filename) = os.path.split(name)
				if not os.path.exists(tempDir):
					os.makedirs(tempDir)
				zfile.extract(name, tempDir)	
				## Return the shp file
				if name.endswith('.shp'): res=name				
			return res
		except:
			progress.setValue(0)
			return -1

	#### Inverse Translate -> FOR DOWNLOAD
	def inverse_translate_file(self, iface, progress, fileName, eatt, evaluation, tmpdir, layerType, indicators):		
		progress.setValue(9)
		## Read the input layer
		layerName = os.path.splitext(os.path.basename(fileName))[0]
		inDataSource = ogr.Open(fileName, 1)
		inLayer = inDataSource.GetLayer()
		inLayer_defn = inLayer.GetLayerDefn()
		
		## Create the output Layer	
		outShapefile = tmpdir+'/'+layerName+'.tmp'
		print "Temporary file: "+outShapefile
		outDriver = ogr.GetDriverByName("ESRI Shapefile")
		if os.path.exists(outShapefile):
			outDriver.DeleteDataSource(outShapefile)
		outDataSource = outDriver.CreateDataSource(outShapefile)
		outLayer = outDataSource.CreateLayer(str(layerName))

		## Translate dbf table (columns) to rc_<ID>/rd_<ID> for every attribute <ID> 
		idx=[]
		ind={}
		
		## Gather shapefile structure table and possible values
		vals={}

		for fd in range(inLayer_defn.GetFieldCount()):
			instr = inLayer_defn.GetFieldDefn(fd).GetName()
			## RC_XX (_rc_XX)
			if "rc" in instr:				
				parts=instr.split('_')
				id_name = parts[2]	
				obj=self.search_object(eatt, 'id', int(id_name)) # str to int			
				if not obj:
					print "WARNING: FIELD"+id_name+" not found"			
				else:					
					# Add a new valid field	
					print "OK: Found FIELD=%s with ID=%s" % (obj['name'], obj['id'])				
					new_field1 = ogr.FieldDefn(str(obj['name']), ogr.OFTString)					
					outLayer.CreateField(new_field1)
					# Cache-Search for possible values for a given id
					arrval=self.search_array(evaluation, int(id_name), 'attribute') # search all possible attribute values
					vals[str(id_name)] = arrval
					# Exposure/Impact layer
					if layerType == 'exposure': 	
						idx.append(fd+1)	# index	_rd_XX	
						ind[fd+1] = id_name # save index
					else:							
						idx.append(fd)		# index _rc_XX [no rd values on impact layer]
						ind[fd] = id_name   # save index
			
			## INDICATORS (indicatorXX)
			elif "indicat" in instr:
				parts=re.findall(r'\d+', instr) # get integer
				if len(parts):
					id_name = parts[0]
					obj=self.search_object(indicators, 'id', int(id_name))
					if not obj:
						print "WARNING: "+id_name+" not found"
					else:					
						# Add a new valid field	
						print "OK: Found IND=%s with ID=%s" % (obj['name'], obj['id'])				
						new_field1 = ogr.FieldDefn(str(obj['name']), ogr.OFTString)					
						outLayer.CreateField(new_field1)
						idx.append(fd)	# index indicator_XX							
						ind[fd] = id_name # Save index					

		## Add features to the ouput Layer
		outLayerDefn = outLayer.GetLayerDefn()
		for f in range(inLayer.GetFeatureCount()):			
			inFeature = inLayer.GetFeature(f)
			outFeature = ogr.Feature(outLayerDefn)
			# Add field values from input Layer
			z=0
			for i in idx:
				# RC or RD depending on layer type
				idval = inFeature.GetField(i)
				idcol = ind[i]
				if idval != None:					
					trueval = idval # default case is _rd_YY										
					if str(idcol) in vals:
						obj=self.search_inside_array(vals[str(idcol)], idval, 'id')
						if obj: trueval=obj['name']
					# avoid NULL situation
					outFeature.SetField(outLayerDefn.GetFieldDefn(z).GetNameRef(), str(trueval)) 
				z+=1

			# Add geometry
			geom = inFeature.GetGeometryRef()		
			outFeature.SetGeometry(geom)
			
			# Add new feature to output Layer
			outLayer.CreateFeature(outFeature)

		# Close DataSources
		inDataSource.Destroy()
		outDataSource.Destroy()
		
		return {'shp':outShapefile, 'values':vals }

	#### Translate a created file -> FOR UPLOAD
	def translate_file(self, iface, progress, fileName, idcatexp, eatt, eval, tmpdir):		
		progress.setValue(2)
		## Read the input layer
		layerName = os.path.splitext(os.path.basename(fileName))[0]
		inDataSource = ogr.Open(fileName, 1)
		inLayer = inDataSource.GetLayer()
		inLayer_defn = inLayer.GetLayerDefn()
		
		## Create the output Layer	
		outShapefile = tmpdir+'/'+layerName+'.tmp'
		print "Temporary file: "+outShapefile
		outDriver = ogr.GetDriverByName("ESRI Shapefile")
		if os.path.exists(outShapefile):
			outDriver.DeleteDataSource(outShapefile)
		outDataSource = outDriver.CreateDataSource(outShapefile)
		outLayer = outDataSource.CreateLayer(str(layerName))

		## Translate dbf table (columns) to rc_<ID> and rd_<ID> for every attribute <ID> 
		enum=[]
		for i in range(inLayer_defn.GetFieldCount()):
			field_name = inLayer_defn.GetFieldDefn(i).GetName()
			if "#" in field_name:				
				parts=field_name.split('#') # OPT/MAN tooltip
				field_name = parts[0]				
			
			obj=self.search_object_dual(eatt, 'name', field_name, 'category', idcatexp)			
			if obj:
				print "OK: Found VAL=%s with ID=%s" % (obj['name'], obj['id'])
				# Add a new field
				new_field1 = ogr.FieldDefn('_rc_'+str(obj['id']), ogr.OFTString)
				new_field2 = ogr.FieldDefn('_rd_'+str(obj['id']), ogr.OFTString)
				outLayer.CreateField(new_field1)
				outLayer.CreateField(new_field2)
				# Detect enumerate
				arr=self.search_array(eval, int(obj['id']), 'attribute')
				if len(arr):	enum.append(1)
				else:			enum.append(0)
			else:
				print "WARNING: "+field_name+" not found."
				
		## Add features to the ouput Layer
		outLayerDefn = outLayer.GetLayerDefn()
		for f in range(0, inLayer.GetFeatureCount()):
			inFeature = inLayer.GetFeature(f)
			outFeature = ogr.Feature(outLayerDefn)
			# Add field values from input Layer
			for i in range(0, outLayerDefn.GetFieldCount()):
				if ((i % 2) == 0):	# RC
					val = inFeature.GetField(i/2)			
				else:				# RD
					val = inFeature.GetField((i-1)/2)
					if enum[(i-1)/2] and val != None:
						# If value is int search for ID translation
						if val.isdigit():
							obj=self.search_object(eval, 'id', int(inFeature.GetField((i-1)/2)))
							if obj != '': 	val = obj['name']
						
				# Add value to dbf column
				if val != None: outFeature.SetField(outLayerDefn.GetFieldDefn(i).GetNameRef(), str(val))
			# Add geometry
			geom = inFeature.GetGeometryRef()		
			outFeature.SetGeometry(geom)
			# Add new feature to output Layer
			outLayer.CreateFeature(outFeature)

		# Close DataSources
		inDataSource.Destroy()
		outDataSource.Destroy()
		
		return outShapefile

	#### Upload a file
	def upload_file(self, iface, progress, fileName, dirNameTmp, exposureCatId, user, password):
		progress.setValue(5)
		print 'LOGIN IN ...'

		## Layer name
		layerName = os.path.splitext(os.path.basename(fileName))[0]
		dirName = os.path.dirname(fileName)
		
		## Login		
		url_login = self.rasor_api+'/rasorapi/user/login/' 
		loginResponse = requests.post(
			url_login, 
			headers = {'content-type': 'application/json'},                             
			data = json.dumps({'username': user, 'password': password})
		)
		#print loginResponse.reason, loginResponse.text
		if loginResponse.status_code == 200:
			## Upload
			url_upload = self.rasor_api+'/rasorapi/exposure/uploadandimport/'+layerName+'/'+str(exposureCatId)+'/'
			print 'UPLOADING ...'	
			progress.setValue(8)
			uploadResponse = requests.post(
				url_upload,
				files = {
					   layerName+'.shp': open(dirNameTmp+'/'+layerName+'.shp', 'rb'),					   
					   layerName+'.shx': open(dirNameTmp+'/'+layerName+'.shx', 'rb'),
					   layerName+'.dbf': open(dirNameTmp+'/'+layerName+'.dbf', 'rb'),
					   layerName+'.prj': open(dirName+'/'+layerName+'.prj', 'rb') # prj is taken from the original shp
				},
				# The cookies received is the login response
				cookies = loginResponse.cookies 
			)	
			print uploadResponse.reason, uploadResponse.text			
			iface.messageBar().clearWidgets()
			if uploadResponse.status_code != 200: 
				## Upload Failed				
				iface.messageBar().pushMessage("Upload layer", "There was an error uploading the layer", level=QgsMessageBar.CRITICAL, duration=5)
				return -1
		else:
			## Login failed
			iface.messageBar().clearWidgets()
			iface.messageBar().pushMessage("Upload layer", "You are not authorized to upload this layer" + loginResponse.reason, level=QgsMessageBar.CRITICAL, duration=5)	
			return -1
			
		return 0 ## ok
		
	#### Main query function (get JSON from server)
	def query_api(self, rasor_api, path):
		try:
			socket.setdefaulttimeout(10)
			response = urllib.urlopen(self.rasor_api+path)
			data=response.read()
			obj = json.loads(data)
			return obj
		except:
			return -1 # ERROR timeout
		
	#### Main query function (get JSON from file)
	def query_file(self, filename):
		with open(filename, 'r') as content_file:
			content = content_file.read()		
		obj = json.loads(content)
		return obj	
	
	#### Download main function () - Write to disk cache
	def download_json(self, filename, path, force):
		if (os.path.isfile(filename)) and (os.stat(filename).st_size > 0) and (force == False):
			## Query file cache
			return self.query_file(filename)
		else:
			## Query server (return file if timeout)
			obj = self.query_api(self.rasor_api, path)
			if obj == -1:
				return self.query_file(filename) # offline mode
			else:
				with open(filename, 'w') as output_file:
					json.dump(obj, output_file)
				return obj
	
	#### Get layer information (do not write on disk)
	def layer_info(self, layerID):
		path = '/rasorapi/layers/'+str(layerID)
		obj = self.query_api(self.rasor_api, path)
		return obj

	#### Search one-object in JSON by NAME
	def search_id(self, json, tag, value):
		for elem in json['objects']:
			if elem[tag]==value:
				return elem['id']
		return ''

	#### Search one-object in JSON by 1 tag
	def search_object(self, json, tag, value):
		for elem in json['objects']:
			if elem[tag]==value:
				return elem
		return ''

	#### Search one-object in JSON by 2 tags
	def search_object_dual(self, json, tag, value, tag2, value2):
		for elem in json['objects']:
			if elem[tag]==value and elem[tag2]==value2:
				return elem
		return ''
		
	#### Search multi-object in JSON by ID=[category/attribute]
	def search_array(self, json, id, tag):
		arr=[]
		for elem in json['objects']:
			if elem[tag]==id:
				arr.append(elem)
		return arr
		
	#### Search in array of dictionaries
	def search_inside_array(self, arr, value, field):
		for elem in arr:
			if str(elem[field])==str(value):
				return elem				
		return ''

	#### Load/Save server from file
	def load_file(self, filename):
		if os.path.exists(filename):
			myfile = open(filename, "r") 
			return myfile.read().replace('\n', '')
		else:
			return ""
	def save_file(self, filename, text):
		myfile = open(filename, "w") 
		myfile.write(str(text))
		myfile.close()
	def set_server(self, server):
		self.rasor_api = server	

	#### MAIN
	def __init__(self):
		# Global variable (RASOR-API-SERVER)
		# test-env: self.rasor_api = 'http://130.251.104.35/'
		# prod-env: self.rasor_api = 'http://130.251.104.198/'
		ok = 0
