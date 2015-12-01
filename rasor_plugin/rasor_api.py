import urllib, urllib2, httplib2, json, os, requests, ogr, socket, sys, zipfile, base64
from qgis.gui import QgsMessageBar
from osgeo import gdal
from urllib2 import HTTPError

class rasor_api:
	#### Internet available (2 seconds timeout)
	def check_connection(self):
		try:
			response=urllib2.urlopen(self.rasor_api, timeout=2)
			return True
		except: pass
		return False

	#### Download a file
	def download_file_WFS(self, progress, layerName, tempDir):
		try:
			progress.setValue(4)
			socket.setdefaulttimeout(10)
			url=self.rasor_api+'/geoserver/wfs?format_options=charset%3AUTF-8&typename=geonode%3A'+layerName+'&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature'
			print url
			response = urllib.urlopen(url)
			fname=tempDir+'/'+layerName+'.zip'
			print fname
			with open(fname, 'wb') as f:
			   while True:
			      chunk = response.read(1024)
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
			fh = open(zipName, 'rb')
			z = zipfile.ZipFile(fh)
			flist = z.namelist()
			res = -1
			## Unzip contents
			for name in flist:
				if name.endswith('.shp'): res=name
				z.extract(name, tempDir)
			## Close and send file list
			fh.close()
			return res
		except:
			progress.setValue(0)
			return -1 ## Bad zip file

	#### Inverse Translate a file
	def inverse_translate_file(self, iface, progress, fileName, eatt, tmpdir):		
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
		for fd in range(inLayer_defn.GetFieldCount()):
			rcid = inLayer_defn.GetFieldDefn(fd).GetName()
			if "rc" in rcid:				
				parts=rcid.split('_') # _rc_XX
				id_name = parts[2]	
				obj=self.search_object(eatt, 'id', int(id_name))				
				if not obj:
					print "WARNING: "+id_name+" not found"			
				else:					
					# Add a new valid field					
					new_field1 = ogr.FieldDefn(str(obj['name']), ogr.OFTString)					
					outLayer.CreateField(new_field1)
					idx.append(fd+1)	# index	_rd_XX	

		## Add features to the ouput Layer
		outLayerDefn = outLayer.GetLayerDefn()
		for f in range(inLayer.GetFeatureCount()):			
			inFeature = inLayer.GetFeature(f)
			outFeature = ogr.Feature(outLayerDefn)
			# Add field values from input Layer
			z=0
			for i in idx:
				idval = inFeature.GetField(i) # _rd_YY
				if idval != None: 	outFeature.SetField(outLayerDefn.GetFieldDefn(z).GetNameRef(), str(idval)) # avoid NULL situation
				z+=1

			# Add geometry
			geom = inFeature.GetGeometryRef()		
			outFeature.SetGeometry(geom)
			# Add new feature to output Layer
			outLayer.CreateFeature(outFeature)

		# Close DataSources
		inDataSource.Destroy()
		outDataSource.Destroy()
		
		return outShapefile

	#### Translate a file
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
				arr=self.search_attributes(eval, int(obj['id']))
				if len(arr):	enum.append(1)
				else:			enum.append(0)
			else:
				print "ERR: "+field_name+" not found."
				
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
	
	#### Download main function
	def download_json(self, filename, path, force):
		if (os.path.isfile(filename)) and (os.stat(filename).st_size > 0) and (force == False):
			## Query file cache
			return self.query_file(filename)
		else:
			## Query server (return file if timeout)
			obj = self.query_api(self.rasor_api, path)
			if obj == -1:
				return self.query_file(filename)
			else:
				with open(filename, 'w') as output_file:
					json.dump(obj, output_file)
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
		
	#### Search multi-object in JSON by ID
	def search_category(self, json, id):
		arr=[]
		for elem in json['objects']:
			if elem['category']==id:
				arr.append(elem)
		return arr
	
	#### Search multi-object in JSON by ID
	def search_attributes(self, json, id):
		arr=[]
		for elem in json['objects']:
			if elem['attribute']==id:
				arr.append(elem)
		return arr
		
	#### Load/Save username/password from file
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
		# test-env: self.rasor_api = 'http://130.251.104.35/rasorapi'
		# prod-env: self.rasor_api = 'http://130.251.104.198/'
		ok = 0
