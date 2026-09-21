#Author: NSA Cloud
#DD2 tops_* PFB v17 -> v18 batch converter.
#
#Built from real v17/v18 pairs for four prefab kinds: chain, mesh, skin (mdf2) and clsp.
#Each of those prefabs has 4 RSZ instances: [null, GameObject, Transform, <one resource component>]
#The last component's type differs per kind, but in all four kinds it changed the same way
#(8 extra bytes before the resource path). Files with any other component type, or with
#non-default values in that component, are skipped with a message and never written, so
#nothing gets silently mangled.
#
#This file does not import bpy, so it can be tested outside of Blender.

import os
import struct

from ..gen_functions import textColors

#Instance type id -> (old layout CRC, new layout CRC)
CRC_MAP = {
	0xC902A417:(0xF24C1EE2,0xF24C1EE2),#GameObject, unchanged
	0xDFAC3046:(0x239D8ECD,0x4FEDEDA7),#Transform
	0x5FC2551F:(0xABDCD1B3,0x8D57CB41),#chain component (.chain)
	0xA1B205C7:(0xF264CF5B,0x01C7A385),#mesh component (.mesh)
	0x6609C5D7:(0xB1392BED,0x533FB4E5),#skin component (.mdf2)
	0xDB0922D4:(0xA465E71A,0xC1A2A07E),#clsp component (.clsp)
	}
FIXED_TYPES = [0x0,0xC902A417,0xDFAC3046]#The first three instances

SRC_SUFFIX = ".pfb.17"
DST_SUFFIX = ".pfb.18"

#The 12 bytes in front of the resource path string, before and after.
OLD_PREFIX = bytes.fromhex("01000000" "00000000" "00000100")
NEW_PREFIX = bytes.fromhex("01000000" "00000000" "00000000" "00000000" "01000000")


def convertPFBData(data):
	"""Converts a DD2 tops_* .pfb.17 file's bytes to .pfb.18. Raises ValueError, with a message describing
	why, if the file isn't one of the four known chain/mesh/skin/clsp prefab kinds or has unexpected data."""
	if data[:4] != b"PFB\x00":
		raise ValueError("not a PFB file")
	rsz_off = struct.unpack_from("<Q",data,0x30)[0]
	magic,ver,obj_cnt,inst_cnt,ud_cnt,_res,inst_off,data_off,ud_off = \
		struct.unpack_from("<4sIIIIIQQQ",data,rsz_off)
	if magic != b"RSZ\x00":
		raise ValueError("RSZ header not found at PFB data offset")
	if ud_cnt != 0 or inst_cnt != 4:
		raise ValueError(f"unsupported layout ({inst_cnt} instances, {ud_cnt} userdata)")
	
	inst_pos = rsz_off + inst_off
	types = [struct.unpack_from("<II",data,inst_pos + 8 * i) for i in range(inst_cnt)]
	ids = [t for t,_ in types]
	if ids[:3] != FIXED_TYPES:
		raise ValueError("first three instances are not the usual null/GameObject/Transform")
	if ids[3] not in CRC_MAP:
		raise ValueError(
			f"unknown component type {ids[3]:#x} (layout CRC {types[3][1]:#x}); "
			"no v17/v18 pair is known for it")
	
	out = bytearray(data)
	for i,(tid,crc) in enumerate(types):
		if tid == 0:
			continue
		old,new = CRC_MAP[tid]
		if crc != old:
			raise ValueError(f"instance {i} has unexpected CRC {crc:#x}")
		struct.pack_into("<I",out,inst_pos + 8 * i + 4,new)
	
	#Locate the trailing resource path string: u32 char count + UTF-16LE chars.
	data_start = rsz_off + data_off
	end = len(data)
	p = None
	for cand in range(end - 6,data_start + 12,-1):
		if (cand - data_start) % 4:
			continue#String fields are 4-byte aligned within the RSZ data
		n = struct.unpack_from("<I",data,cand)[0]
		if 0 < n < 512 and cand + 4 + n * 2 == end and data[end - 2:end] == b"\0\0":
			p = cand
			break
	if p is None:
		raise ValueError("could not locate resource path string at end of file")
	
	block = p - 12
	if (block - data_start) % 16 != 0:
		raise ValueError("component block is not 16-byte aligned")
	if data[block:p] != OLD_PREFIX:
		raise ValueError(f"component has non-default values: {data[block:p].hex(' ')}")
	
	out[block:p] = NEW_PREFIX
	return bytes(out)


def findDD2PFB17Files(directory,searchSubdirectories = True):
	suffix = SRC_SUFFIX
	foundList = []
	if searchSubdirectories:
		for root,dirs,files in os.walk(directory):
			for fileName in files:
				if fileName.lower().endswith(suffix):
					foundList.append(os.path.join(root,fileName))
	else:
		for fileName in os.listdir(directory):
			path = os.path.join(directory,fileName)
			if os.path.isfile(path) and fileName.lower().endswith(suffix):
				foundList.append(path)
	return sorted(foundList)


def batchConvertDD2PFBFiles(directory,searchSubdirectories = True,keepBackup = False):
	"""Converts every DD2 tops_* .pfb.17 file in the directory to .pfb.18, next to the original.
	The .pfb.18 file always overwrites one that's already there.
	When keepBackup is False (the default) the original .pfb.17 file is deleted once the new file has been written.
	When keepBackup is True the .pfb.17 file is instead renamed to .pfb.17.bak (overwriting an existing .bak file), so it's kept as a backup.
	Returns a dict with lists of (path,message) for "converted" and "failed"."""
	results = {"converted":[],"failed":[]}
	fileList = findDD2PFB17Files(directory,searchSubdirectories)
	print(f"{textColors.OKCYAN}Converting {len(fileList)} .pfb.17 files to .pfb.18...{textColors.ENDC}")
	for srcPath in fileList:
		dstPath = srcPath[:-len("17")] + "18"#Swaps only the version number, keeping the casing of the rest of the name
		try:
			with open(srcPath,"rb") as file:
				data = file.read()
			newData = convertPFBData(data)
			tempPath = dstPath + ".tmp"
			try:
				with open(tempPath,"wb") as file:
					file.write(newData)
				os.replace(tempPath,dstPath)
			except Exception as err:
				try:
					if os.path.exists(tempPath):
						os.remove(tempPath)
				except Exception:
					pass
				raise Exception(f"couldn't write file: {err}")
			status,message = "converted",""
		except Exception as err:
			status,message = "failed",str(err)
		
		if status == "converted":
			if keepBackup:
				backupPath = srcPath + ".bak"
				try:
					os.replace(srcPath,backupPath)#Renames, overwriting an existing .bak file
				except Exception as err:
					message = f"converted, but couldn't rename the old .pfb.17 file to .bak: {err}"
			else:
				try:
					os.remove(srcPath)
				except Exception as err:
					message = f"converted, but couldn't remove the old .pfb.17 file: {err}"
		
		results[status].append((srcPath,message))
		if status == "converted":
			print(f"{textColors.OKGREEN}Converted{textColors.ENDC} {srcPath}")
		else:
			print(f"{textColors.FAIL}Failed{textColors.ENDC} {srcPath}: {message}")
	print(f"Done. {len(results['converted'])} converted, {len(results['failed'])} failed.")
	return results
