import urllib, httplib2, json, os, requests, ogr
from qgis.gui import QgsMessageBar
from osgeo import gdal

class rasor_api:
	#### Translate a file
	def translate_file(self, iface, progress, fileName, eatt, eval, tmpdir):		
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
			parts=field_name.split('-') # OPT/MAN tooltip
			obj=self.search_object(eatt, 'name', parts[0])
			if obj != '':
				# Add a new field
				new_field1 = ogr.FieldDefn('_rc_'+str(obj['id']), ogr.OFTInteger)
				new_field2 = ogr.FieldDefn('_rd_'+str(obj['id']), ogr.OFTString)
				outLayer.CreateField(new_field1)
				outLayer.CreateField(new_field2)
				# Detect enumerate
				arr=self.search_attributes(eval, int(obj['id']))
				if len(arr):	enum.append(1)
				else:			enum.append(0)

		## Add features to the ouput Layer
		outLayerDefn = outLayer.GetLayerDefn()
		for i in range(0, inLayer.GetFeatureCount()):
			inFeature = inLayer.GetFeature(i)
			outFeature = ogr.Feature(outLayerDefn)
			# Add field values from input Layer
			for i in range(0, outLayerDefn.GetFieldCount()):
				if ((i % 2) == 0):	# RC
					val = str(inFeature.GetField(i/2))
				else:				# RD
					val = inFeature.GetField((i-1)/2)
					if enum[(i-1)/2] and val != None:
						obj=self.search_object(eval, 'id', int(inFeature.GetField((i-1)/2)))
						if obj != '': 	val = str(obj['name'])

				# Add value to dbf column
				if val != None: outFeature.SetField(outLayerDefn.GetFieldDefn(i).GetNameRef(), val)
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
		progress.setValue(4)
		
		## Layer name
		layerName = os.path.splitext(os.path.basename(fileName))[0]
		dirName = os.path.dirname(fileName)
		
		## Login		
		url_login = self.rasor_api+'/user/login/' 
		loginResponse = requests.post(
			url_login, 
			headers = {'content-type': 'application/json'},                             
			data = json.dumps({'username': user, 'password': password})
		)
		print loginResponse.reason, loginResponse.text
		if loginResponse.status_code == 200:
			## Upload
			url_upload = self.rasor_api+'/exposure/uploadandimport/'+layerName+'/'+str(exposureCatId)+'/'			
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
				iface.messageBar().pushMessage("Upload layer", "There was an error uploading the files: " + uploadResponse.reason, level=QgsMessageBar.CRITICAL, duration=5)
				return -1
		else:
			## Login failed
			iface.messageBar().clearWidgets()
			iface.messageBar().pushMessage("Upload layer", "There was an error in the authentication process:" + loginResponse.reason, level=QgsMessageBar.CRITICAL, duration=5)	
			return -1
			
		return 0 ## ok
		
	#### Main query function (get JSON from server)
	def query_api(self, rasor_api, path):
		response = urllib.urlopen(self.rasor_api+path).read()
		obj = json.loads(response)
		return obj
		
	#### Main query function (get JSON from file)
	def query_file(self, filename):
		with open(filename, 'r') as content_file:
			content = content_file.read()		
		obj = json.loads(content)
		return obj	
	
	#### Download main function
	def download_json(self, filename, path):
		if os.path.isfile(filename) and os.stat(filename).st_size > 0:
			return self.query_file(filename)
		else:
			obj = self.query_api(self.rasor_api, path)
			with open(filename, 'w') as output_file:
				json.dump(obj, output_file)
			return obj
		
	#### Search one-object in JSON by NAME
	def search_id(self, json, tag, value):
		for elem in json['objects']:
			if elem[tag]==value:
				return elem['id']
		return ''

	#### Search one-object in JSON by NAME
	def search_object(self, json, tag, value):
		for elem in json['objects']:
			if elem[tag]==value:
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
		myfile = open(filename, "r") 
		return myfile.read().replace('\n', '')

	def save_file(self, filename, text):
		myfile = open(filename, "w") 
		myfile.write(str(text))
		myfile.close()
		
	#### MAIN
	def __init__(self):
		# Global variable (RASOR-API-SERVER)
		self.rasor_api = 'http://130.251.104.35/rasorapi'

# Stub function (just to test connection to the RASOR API, not used)
if __name__ == '__main__':
	
	# Rasor API object
	rapi=rasor_api()
