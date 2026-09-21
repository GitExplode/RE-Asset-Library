#Author: NSA Cloud
import os
import json

from ..hashing.mmh3.pymmh3 import hashUTF8
from ..pak.re_pak_utils import loadGameInfo,extractFilesFromPakCache,PakCacheStream
from ..asset.re_asset_utils import loadREAssetCatalogFile
from io import BytesIO
from shutil import copyfile
from .file_re_mdf import readMDF,writeMDF,Property,TextureBinding,GPBFEntry,MDFFile
def makeMDFBackup(mdfPath):
	bakIndex = 0
	bakPath = f"{mdfPath}.bak{bakIndex}"
	if os.path.isfile(mdfPath):
		while(os.path.isfile(bakPath)):
			bakIndex += 1
			bakPath = f"{mdfPath}.bak{bakIndex}"
		try:
			copyfile(mdfPath,bakPath)
		except Exception as err:
			print(f"Failed to create backup of {mdfPath} - {str(err)}")
def getMaterialByHash(mdfData,matNameHash,version):
	material = None
	
	try:
		with BytesIO(mdfData) as tempStream:
			mdfFile = MDFFile()
			mdfFile.read(tempStream,version)
			for mat in mdfFile.materialList:
				if mat.matNameHash == matNameHash:
					material = mat
					#print("Found sample mat")
					break
	except Exception as err:
		print(f"Failed to retrieve material from sample MDF {matNameHash} {str(err)}")
	if material == None:
		print(f"Failed to retrieve sample material {matNameHash}")
	return material
	
def batchUpdateMDFFiles(modDirectory,compendiumPath,searchSubdirectories,createBackups):
	print(f"Checking for outdated MDF files in: {modDirectory}")
	mdfList = []
	for root, dirs, files in os.walk(modDirectory):
		for fileName in files:
			if ".mdf2." in fileName and ".bak" not in fileName:#not fileName.endswith(".bak"):
				mdfList.append(os.path.join(root,fileName))
		
		if not searchSubdirectories:
			break
	
	if not os.path.isfile(compendiumPath):
		raise Exception("Compendium path is invalid")
	try:
		with open(compendiumPath,"r", encoding ="utf-8") as file:
			materialCompendium = json.load(file)
			
	except:
		raise Exception(f"Failed to load {compendiumPath}")
	assetLibDir = os.path.split(compendiumPath)[0]
	gameName = os.path.split(compendiumPath)[1].split("MaterialCompendium_")[1].split(".json")[0]
	gameInfoPath = os.path.join(assetLibDir,f"GameInfo_{gameName}.json")
	gameInfo = loadGameInfo(gameInfoPath)
	mdfVersion = gameInfo["fileVersionDict"]["MDF2_VERSION"]
	
	extractInfoPath = os.path.join(assetLibDir,f"ExtractInfo_{gameName}.json")	
	
	if not os.path.isfile(extractInfoPath):
		raise Exception("Extract info path is invalid")
	try:
		with open(extractInfoPath,"r", encoding ="utf-8") as file:
			extractInfo = json.load(file)
			chunkPath = os.path.join("natives",extractInfo["platform"])#Changed to pull from pak directly
			platform = extractInfo["platform"]
			print(f"Extract Path: {chunkPath}")
	except:
		raise Exception(f"Failed to load {extractInfoPath}")
	
	pakCachePath = os.path.join(assetLibDir,f"PakCache_{gameName}.pakcache")	
	
	if not os.path.isfile(pakCachePath):
		raise Exception("Pak cache path is invalid")
	#print("Extracting newest shader files...")
	#mdfExtractList = [f"natives/{platform}/"+entry["mdfPath"] + f".{mdfVersion}" for entry in materialCompendium.values()]
	#print(mdfExtractList)
	#extractFilesFromPakCache(gameInfoPath, mdfExtractList, extractInfoPath, pakCachePath,extractDependencies=False)
	#print(f"Extracted {len(mdfExtractList)} files.")
	pakStream = PakCacheStream(assetLibDir,gameName)
	print("Started pak stream.")
	
	mmtrMaterialCache = dict()
	
	updatedFileCount = 0
	
	for mdfPath in mdfList:
		print(f"Checking {mdfPath}")
		requiresUpdate = False
		try:
			currentVersion = int(os.path.splitext(mdfPath)[1].replace(".",""))
			if currentVersion != int(mdfVersion):
				print(f"MDF is version {currentVersion}, updating to {mdfVersion}...")
				requiresUpdate = True
			mdfFile = readMDF(mdfPath)
			if gameName == "MHWILDS":
				if mdfFile.Header.materialFlags == 0:
					mdfFile.Header.materialFlags = 1
					requiresUpdate = True
					print("Detected MDF written with older tool version, updating...")
			
			#TODO maybe check for non vanilla string buffer
			
			for material in mdfFile.materialList:
				mmtrHash = str(hashUTF8(material.mmtrPath.lower()))
				#print(material.materialName)
				#print(mmtrHash)
				if mmtrHash not in mmtrMaterialCache:
					
					if mmtrHash in materialCompendium:
						compendiumEntry = materialCompendium[mmtrHash]
						#print(materialCompendium[mmtrHash])
						samplePath = os.path.join(chunkPath,compendiumEntry["mdfPath"].replace("/",os.sep)+f".{mdfVersion}")
						mdfData = pakStream.retrieveFileData(samplePath)
						if mdfData != None:
							print(f"Retrieved {samplePath}")
							sampleMaterial = getMaterialByHash(mdfData, compendiumEntry["matNameHash"],int(mdfVersion))
						else:
							sampleMaterial = None
							print(f"MDF not found in pak, cannot retrieve sample material: {samplePath}")
						mmtrMaterialCache[mmtrHash] = sampleMaterial
					else:
						print(f"MMTR path {material.mmtrPath} not in compendium, can't update {material.materialName} material.")
						sampleMaterial = None
				else:
					sampleMaterial = mmtrMaterialCache[mmtrHash]
				if sampleMaterial != None:
					
					#Shader-defined metadata (shaderType, shaderLODNum, bakeTextureArraySize)
					#These are dictated by the mmtr/shader definition, not something mods customize
					#(unlike the flags/flagsB bitfields, which hold mod-editable render toggles and are left alone),
					#so they should always be kept in sync with the current game version's sample material.
					for fieldName in ("shaderType","shaderLODNum","bakeTextureArraySize"):
						oldValue = getattr(material,fieldName)
						newValue = getattr(sampleMaterial,fieldName)
						if oldValue != newValue:
							print(f"Changed {fieldName} from {oldValue} to {newValue} on {material.materialName}")
							setattr(material,fieldName,newValue)
							requiresUpdate = True
					
					#GPU Buffer (GPBF) bindings
					#Like shaderType, these are dictated by the shader/mmtr definition rather than being mod-editable data,
					#so missing/stale entries are fully replaced with the sample's list rather than value-merged like textures.
					newGPBFNameSet = set(entry.name for entry in sampleMaterial.gpbfBufferNameList)
					oldGPBFNameSet = set(entry.name for entry in material.gpbfBufferNameList)
					if newGPBFNameSet != oldGPBFNameSet:
						requiresUpdate = True
						addedGPBFDifference = newGPBFNameSet.difference(oldGPBFNameSet)
						removedGPBFDifference = oldGPBFNameSet.difference(newGPBFNameSet)
						if len(addedGPBFDifference) != 0:
							print(f"Added GPU buffer bindings in {material.materialName} material:")
							print(addedGPBFDifference)
						if len(removedGPBFDifference) != 0:
							print(f"Removed GPU buffer bindings in {material.materialName} material:")
							print(removedGPBFDifference)
						newGPBFNameList = []
						newGPBFPathList = []
						for index, nameEntry in enumerate(sampleMaterial.gpbfBufferNameList):
							copiedNameEntry = GPBFEntry()
							copiedNameEntry.name = nameEntry.name
							copiedPathEntry = GPBFEntry()
							copiedPathEntry.name = sampleMaterial.gpbfBufferPathList[index].name
							newGPBFNameList.append(copiedNameEntry)
							newGPBFPathList.append(copiedPathEntry)
						material.gpbfBufferNameList = newGPBFNameList
						material.gpbfBufferPathList = newGPBFPathList
					
					#Properties
					#Fix incorrect padding
					
					#Fix front padding
					if len(material.propertyList) != 0 and len(sampleMaterial.propertyList) != 0:
						if material.propertyList[0].frontPadding != sampleMaterial.propertyList[0].frontPadding:
							print(f"Changed front padding from {material.propertyList[0].frontPadding} to {sampleMaterial.propertyList[0].frontPadding} on {material.propertyList[0].propName} ({material.materialName})")
							material.propertyList[0].frontPadding = sampleMaterial.propertyList[0].frontPadding
							requiresUpdate = True
					
					propPaddingDict = {item.propName:item.padding for item in sampleMaterial.propertyList}
					for prop in material.propertyList:
						if prop.propName in propPaddingDict and prop.padding != propPaddingDict[prop.propName]:
							print(f"Changed padding from {prop.padding} to {propPaddingDict[prop.propName]} on {prop.propName} ({material.materialName})")
							prop.padding = propPaddingDict[prop.propName]
							requiresUpdate = True
					#print(f"material.materialName")
					newPropNameSet = set([item.propName for item in sampleMaterial.propertyList])
					#print(newPropNameSet)
					
					oldPropNameSet = set([item.propName for item in material.propertyList])
					#print(oldPropNameSet)
					addedPropDifference = newPropNameSet.difference(oldPropNameSet)
					if len(addedPropDifference) != 0:
						requiresUpdate = True
						print(f"Added properties in {material.materialName} material:")
						for propName in addedPropDifference:
							for prop in sampleMaterial.propertyList:
								if prop.propName == propName:
									newProp = Property()
									newProp.propName = propName
									
									newProp.propValue = prop.propValue[:]
									newProp.padding = prop.padding
									newProp.frontPadding = prop.frontPadding
									material.propertyList.append(newProp)
						print(addedPropDifference)
					removedPropDifference = oldPropNameSet.difference(newPropNameSet)
					if len(removedPropDifference) != 0:
						requiresUpdate = True
						print(f"Removed properties in {material.materialName} material:")
						material.propertyList = [mat for mat in material.propertyList if mat.propName not in removedPropDifference]
						print(removedPropDifference)
					
					
					
					oldPropOrderDict = {prop.propName: index for index, prop in enumerate(material.propertyList)}
					newPropOrderDict = {prop.propName: index for index, prop in enumerate(sampleMaterial.propertyList)}
					
					if oldPropOrderDict != newPropOrderDict:
						#Reorder properties into order used by new file
						newPropertyList = []
						for prop in sampleMaterial.propertyList:#Remake the list in correct order
							newPropertyList.append(material.propertyList[oldPropOrderDict[prop.propName]])
						material.propertyList = newPropertyList
						requiresUpdate = True
						print(f"Reordered property list of {material.materialName}")
					
					
					
					#Texture Bindings
					
					newBindingNameSet = set([item.textureType for item in sampleMaterial.textureList])
					#print(newPropNameSet)
					
					
					oldBindingNameSet = set([item.textureType for item in material.textureList])
					#print(oldPropNameSet)
					
					addedBindingDifference = newBindingNameSet.difference(oldBindingNameSet)
					if len(addedBindingDifference) != 0:
						requiresUpdate = True
						print(f"Added texture bindings in {material.materialName} material:")
						for textureType in addedBindingDifference:
							for binding in sampleMaterial.textureList:
								if binding.textureType == textureType:
									newBinding = TextureBinding()
									newBinding.textureType = textureType
									newBinding.texturePath = binding.texturePath
									material.textureList.append(newBinding)
						print(addedBindingDifference)
					removedBindingDifference = oldBindingNameSet.difference(newBindingNameSet)
					if len(removedBindingDifference) != 0:
						requiresUpdate = True
						print(f"Removed texture bindings in {material.materialName} material:")
						material.textureList = [mat for mat in material.textureList if mat.textureType not in removedBindingDifference]
						print(removedBindingDifference)
					
				else:
					print(f"Sample material for {material.mmtrPath} missing.")
					print(mmtrHash)
			if requiresUpdate:
				if createBackups:
					makeMDFBackup(mdfPath)
				if currentVersion != int(mdfVersion):
					newMdfPath = os.path.splitext(mdfPath)[0]+f".{mdfVersion}"
					writeMDF(mdfFile,newMdfPath)
					if newMdfPath != mdfPath:
						os.remove(mdfPath)#Remove the old-version file now that its replacement has been written
					print(f"Converted to mdf2.{mdfVersion}: {newMdfPath}")
				else:
					writeMDF(mdfFile, mdfPath)
				updatedFileCount += 1
				print("\nUpdate completed.")
			else:
				print("\nNo update required.")
				
						#print(samplePath)
			#print(mdfPath)
		except Exception as err:
			print(f"Failed to read {mdfPath}: {str(err)}")
			
	pakStream.closeStreams()
	del pakStream
	print("Closed pak stream.")
	return updatedFileCount

#Runs on Blender collections
def batchUpdateMDFCollections(compendiumPath,bpy):
	print(f"Checking for outdated MDF collections...")
	
	if not os.path.isfile(compendiumPath):
		raise Exception("Compendium path is invalid")
	try:
		with open(compendiumPath,"r", encoding ="utf-8") as file:
			materialCompendium = json.load(file)
			
	except:
		raise Exception(f"Failed to load {compendiumPath}")
	mdfList = [col for col in bpy.data.collections if col.get("~TYPE") == "RE_MDF_COLLECTION"]

	assetLibDir = os.path.split(compendiumPath)[0]
	gameName = os.path.split(compendiumPath)[1].split("MaterialCompendium_")[1].split(".json")[0]
	gameInfoPath = os.path.join(assetLibDir,f"GameInfo_{gameName}.json")	
	gameInfo = loadGameInfo(gameInfoPath)
	mdfVersion = gameInfo["fileVersionDict"]["MDF2_VERSION"]
	
	extractInfoPath = os.path.join(assetLibDir,f"ExtractInfo_{gameName}.json")	
	
	if not os.path.isfile(extractInfoPath):
		raise Exception("Extract info path is invalid")
	try:
		with open(extractInfoPath,"r", encoding ="utf-8") as file:
			extractInfo = json.load(file)
			chunkPath = os.path.join("natives",extractInfo["platform"])#Changed to pull from pak directly
			platform = extractInfo["platform"]
			print(f"Extract Path: {chunkPath}")
	except:
		raise Exception(f"Failed to load {extractInfoPath}")
	
	pakCachePath = os.path.join(assetLibDir,f"PakCache_{gameName}.pakcache")
	
	if not os.path.isfile(pakCachePath):
		raise Exception("Pak cache path is invalid")
	#print("Extracting newest shader files...")
	#mdfExtractList = [f"natives/{platform}/"+entry["mdfPath"] + f".{mdfVersion}" for entry in materialCompendium.values()]
	#print(mdfExtractList)
	#extractFilesFromPakCache(gameInfoPath, mdfExtractList, extractInfoPath, pakCachePath,extractDependencies=False)
	#print(f"Extracted {len(mdfExtractList)} files.")
	pakStream = PakCacheStream(assetLibDir,gameName)
	print("Started pak stream.")
	mmtrMaterialCache = dict()
	
	updatedFileCount = 0
	
	for mdfCollection in mdfList:
		print(f"Checking {mdfCollection.name}")
		requiresUpdate = False
		materialList = [obj for obj in mdfCollection.all_objects if obj.get("~TYPE") == "RE_MDF_MATERIAL"]
		for materialObj in materialList:
			matData = materialObj.re_mdf_material
			mmtrHash = str(hashUTF8(matData.mmtrPath.lower()))
			
			if mmtrHash not in mmtrMaterialCache:
				
				if mmtrHash in materialCompendium:
					compendiumEntry = materialCompendium[mmtrHash]
					#print(materialCompendium[mmtrHash])
					samplePath = os.path.join(chunkPath,compendiumEntry["mdfPath"].replace("/",os.sep)+f".{mdfVersion}")
					mdfData = pakStream.retrieveFileData(samplePath)
					if mdfData != None:
						print(f"Retrieved {samplePath}")
						sampleMaterial = getMaterialByHash(mdfData, compendiumEntry["matNameHash"],int(mdfVersion))
					else:
						sampleMaterial = None
						print(f"MDF not found in pak, cannot retrieve sample material: {samplePath}")
					mmtrMaterialCache[mmtrHash] = sampleMaterial
				else:
					print(f"MMTR path {matData.mmtrPath} not in compendium, can't update {materialObj.name}")
					sampleMaterial = None
			else:
				sampleMaterial = mmtrMaterialCache[mmtrHash]
			if sampleMaterial != None:
				
				#Shader-defined metadata (shaderType, shaderLODNum, bakeTextureArraySize)
				#These are dictated by the mmtr/shader definition, not something mods customize
				#(unlike the flags/flagsB bitfields, which hold mod-editable render toggles and are left alone),
				#so they should always be kept in sync with the current game version's sample material.
				if matData.shaderType != str(sampleMaterial.shaderType):
					print(f"Changed shaderType from {matData.shaderType} to {sampleMaterial.shaderType} on {materialObj.name}")
					matData.shaderType = str(sampleMaterial.shaderType)
					requiresUpdate = True
				if matData.flags.shaderLODNum != sampleMaterial.shaderLODNum:
					print(f"Changed shaderLODNum from {matData.flags.shaderLODNum} to {sampleMaterial.shaderLODNum} on {materialObj.name}")
					matData.flags.shaderLODNum = sampleMaterial.shaderLODNum
					requiresUpdate = True
				if matData.flags.bakeTextureArraySize != sampleMaterial.bakeTextureArraySize:
					print(f"Changed bakeTextureArraySize from {matData.flags.bakeTextureArraySize} to {sampleMaterial.bakeTextureArraySize} on {materialObj.name}")
					matData.flags.bakeTextureArraySize = sampleMaterial.bakeTextureArraySize
					requiresUpdate = True
				
				#GPU Buffer (GPBF) bindings
				#Like shaderType, these are dictated by the shader/mmtr definition rather than being mod-editable data,
				#so missing/stale entries are fully replaced with the sample's list rather than value-merged like textures.
				newGPBFNameSet = set(entry.name for entry in sampleMaterial.gpbfBufferNameList)
				oldGPBFNameSet = set(item.gpbfDataString.split(",")[0] for item in matData.gpbfData_items)
				if newGPBFNameSet != oldGPBFNameSet:
					requiresUpdate = True
					addedGPBFDifference = newGPBFNameSet.difference(oldGPBFNameSet)
					removedGPBFDifference = oldGPBFNameSet.difference(newGPBFNameSet)
					if len(addedGPBFDifference) != 0:
						print(f"Added GPU buffer bindings in {materialObj.name}:")
						print(addedGPBFDifference)
					if len(removedGPBFDifference) != 0:
						print(f"Removed GPU buffer bindings in {materialObj.name}:")
						print(removedGPBFDifference)
					matData.gpbfData_items.clear()
					for index, nameEntry in enumerate(sampleMaterial.gpbfBufferNameList):
						pathEntry = sampleMaterial.gpbfBufferPathList[index]
						newListItem = matData.gpbfData_items.add()
						newListItem.gpbfDataString = f"{nameEntry.name},{pathEntry.name},{str(pathEntry.nameUTF16Hash)},{str(pathEntry.nameUTF8Hash)}"
				
				#Properties
				
				#Fix incorrect padding
				
				#Fix front padding
				if len(matData.propertyList_items) != 0 and len(sampleMaterial.propertyList) != 0:
					if matData.propertyList_items[0].frontPadding != sampleMaterial.propertyList[0].frontPadding:
						print(f"Changed front padding from {matData.propertyList_items[0].frontPadding} to {sampleMaterial.propertyList[0].frontPadding} on {matData.propertyList_items[0].prop_name} ({materialObj.name})")
						matData.propertyList_items[0].frontPadding = sampleMaterial.propertyList[0].frontPadding
						requiresUpdate = True
				
				propPaddingDict = {item.propName:item.padding for item in sampleMaterial.propertyList}
				for prop in matData.propertyList_items:
					if prop.prop_name in propPaddingDict and prop.padding != propPaddingDict[prop.prop_name]:
						print(f"Changed padding from {prop.padding} to {propPaddingDict[prop.prop_name]} on {prop.prop_name} ({materialObj.name})")
						prop.padding = propPaddingDict[prop.prop_name]
						requiresUpdate = True
				newPropNameSet = set([item.propName for item in sampleMaterial.propertyList])
				#print(newPropNameSet)
				
				
				oldPropNameSet = set([item.prop_name for item in matData.propertyList_items])
				#print(oldPropNameSet)
				
				addedPropDifference = newPropNameSet.difference(oldPropNameSet)
				if len(addedPropDifference) != 0:
					requiresUpdate = True
					print(f"Added properties in {materialObj.name}:")
					for propName in addedPropDifference:
						for prop in sampleMaterial.propertyList:
							if prop.propName == propName:
								newProp = matData.propertyList_items.add()
								newProp.prop_name = propName
								newProp.padding = prop.padding
								newProp.frontPadding = prop.frontPadding
								lowerPropName = prop.propName.lower()
								if (prop.paramCount == 4 and ("color" in lowerPropName or "_col_" in lowerPropName) and "rate" not in lowerPropName):
									newProp.data_type = "COLOR"
									newProp.color_value = prop.propValue
								elif prop.paramCount == 1 and ("Use" in prop.propName or "_or_" in prop.propName or prop.propName.startswith("is")):
									newProp.data_type = "BOOL"
									newProp.bool_value = bool(prop.propValue[0])
								elif prop.paramCount > 1:
									newProp.data_type = "VEC4"
									newProp.float_vector_value = tuple(prop.propValue)
								else:
									newProp.data_type = "FLOAT"
									newProp.float_value = float(prop.propValue[0])

					print(addedPropDifference)
				removedPropDifference = oldPropNameSet.difference(newPropNameSet)
				if len(removedPropDifference) != 0:
					requiresUpdate = True
					indicesRemovalList = []
					
					for index, prop in enumerate(matData.propertyList_items):
						if prop.prop_name in removedPropDifference:
							indicesRemovalList.append(index)
					
					for index in reversed(sorted(indicesRemovalList)):
						matData.propertyList_items.remove(index)
					print(f"Removed properties in {materialObj.name}")
					print(removedPropDifference)
				
				oldPropOrderDict = {prop.prop_name: index for index, prop in enumerate(matData.propertyList_items)}
				newPropOrderDict = {prop.propName: index for index, prop in enumerate(sampleMaterial.propertyList)}
				
				if oldPropOrderDict != newPropOrderDict:
					#Reorder properties into order used by new file
					
					#Reorder the list starting from the last index
					for key in sorted(newPropOrderDict, key=newPropOrderDict.get, reverse=True):
						currentIndex = oldPropOrderDict[key]
						
						#print(f"Moving {matData.propertyList_items[currentIndex].prop_name} from {currentIndex} to {newPropOrderDict[key]}")
						matData.propertyList_items.move(currentIndex,newPropOrderDict[key])
						
						#Rebuilding the dict like this every loop is super inefficient I know, but it works and the performance impact of it is negligable
						oldPropOrderDict = {prop.prop_name: index for index, prop in enumerate(matData.propertyList_items)}
					requiresUpdate = True
					print(f"Reordered property list of {materialObj.name}")
				
				#Texture Bindings
				
				newBindingNameSet = set([item.textureType for item in sampleMaterial.textureList])
				#print(newPropNameSet)
				
				
				oldBindingNameSet = set([item.textureType for item in matData.textureBindingList_items])
				#print(oldPropNameSet)
				
				addedBindingDifference = newBindingNameSet.difference(oldBindingNameSet)
				if len(addedBindingDifference) != 0:
					requiresUpdate = True
					print(f"Added texture bindings in {materialObj.name} material:")
					for textureType in addedBindingDifference:
						for binding in sampleMaterial.textureList:
							if binding.textureType == textureType:
								newBinding = matData.textureBindingList_items.add()
								newBinding.textureType = textureType
								newBinding.path = binding.texturePath
					print(addedBindingDifference)
				removedBindingDifference = oldBindingNameSet.difference(newBindingNameSet)
				if len(removedBindingDifference) != 0:
					requiresUpdate = True
					indicesRemovalList = []
					
					for index, binding in enumerate(matData.textureBindingList_items):
						if binding.textureType in removedBindingDifference:
							indicesRemovalList.append(index)
					
					for index in reversed(sorted(indicesRemovalList)):
						matData.textureBindingList_items.remove(index)
					print(f"Removed texture bindings in {materialObj.name}")
					print(removedBindingDifference)
				
			else:
				print(f"Sample material for {matData.mmtrPath} missing.")
				print(mmtrHash)
		if requiresUpdate:
			updatedFileCount += 1
			print("Update completed.")
		else:
			print("No update required.")
			
					#print(samplePath)
		#print(mdfPath)
	pakStream.closeStreams()
	del pakStream
	print("Closed pak stream.")
	
	return updatedFileCount

def generateMaterialCompendium(libraryDir,gameName):
	gameInfoPath = os.path.join(libraryDir,f"GameInfo_{gameName}.json")
	catalogPath = os.path.join(libraryDir,f"REAssetCatalog_{gameName}.tsv")
	extractInfoPath = os.path.join(libraryDir,f"ExtractInfo_{gameName}.json")
	compendiumOutPath = os.path.join(libraryDir,f"MaterialCompendium_{gameName}.json")
	if os.path.isfile(gameInfoPath):
		gameInfo = loadGameInfo(gameInfoPath)
		assetEntryList = loadREAssetCatalogFile(catalogPath)
		extractPath = None
		with open(extractInfoPath,"r", encoding ="utf-8") as file:
			extractInfo = json.load(file)
			extractPath = extractInfo["extractPath"].replace("/",os.sep)
		mdfFileList = [entry[0]+"."+gameInfo["fileVersionDict"]["MDF2_VERSION"] for entry in assetEntryList if entry[0].endswith(".mdf2")]
		print(f"Processing {len(mdfFileList)} MDF files")
		
		mmtrUsageDict = {}
		pakStream = PakCacheStream(libraryDir,gameName)
		
		for path in mdfFileList:
			
			fullPath = os.path.join("natives",extractInfo["platform"],path.replace(os.sep,"/").replace("\\","/"))
			fileData = pakStream.retrieveFileData(fullPath)
			if fileData != None:
				try:
					with BytesIO(fileData) as file:
						mdfFile = MDFFile()
						mdfFile.read(file,int(gameInfo["fileVersionDict"]["MDF2_VERSION"]))
						for material in mdfFile.materialList:
							mmtrLowerPathHash = hashUTF8(material.mmtrPath.lower())
							if mmtrLowerPathHash not in mmtrUsageDict:
								mmtrUsageDict[mmtrLowerPathHash] = {"name":os.path.splitext(os.path.split(material.mmtrPath)[1])[0],"mdfPath":os.path.splitext(path)[0],"matNameHash":material.matNameHash}
				except Exception as err:
					print(f"Failed to read ({fullPath}:{str(err)})")
		pakStream.closeStreams()
		del pakStream
		sortedDict = {k: v for k, v in sorted(mmtrUsageDict.items(), key=lambda item: item[1]["name"])}
		with open(compendiumOutPath,"w", encoding ="utf-8") as outFile:
			json.dump(sortedDict,outFile,sort_keys=False,indent=4)
			print(f"Wrote {os.path.split(compendiumOutPath)[1]}")
		print(f"{len(sortedDict)} shader entries written")	
		#print(mdfFileList)