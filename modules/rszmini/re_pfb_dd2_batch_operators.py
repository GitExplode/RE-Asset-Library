#Author: NSA Cloud
import bpy
import os

from bpy.types import Operator

from ..blender_utils import showMessageBox
from .re_pfb_dd2_batch_convert import batchConvertDD2PFBFiles


class WM_OT_BatchConvertDD2PFBVersion(Operator):
	bl_label = "Batch Convert DD2 PFB Version (17 to 18)"
	bl_idname = "re_asset.batch_convert_dd2_pfb_version"
	bl_description = "Converts DD2 tops_* .pfb.17 files in the chosen folder to .pfb.18.\nOnly supports the chain, mesh, skin (mdf2) and clsp prefab component kinds. Files with any other component, or unexpected values, are skipped and left untouched.\nBy default the original .pfb.17 file is deleted after conversion"
	bl_options = {'REGISTER'}
	
	dirPath : bpy.props.StringProperty(
		name = "Mod Directory",
		description = "Folder containing the .pfb.17 files to convert",
		default = "",
		subtype = "DIR_PATH",)
	
	searchSubdirectories : bpy.props.BoolProperty(
		name = "Search Subdirectories",
		description = "Also convert .pfb.17 files inside folders within the chosen directory",
		default = True,
		)
	
	createBackups : bpy.props.BoolProperty(
		name = "Create PFB 17 Backups",
		description = "Rename the original .pfb.17 file to .pfb.17.bak to keep it as a backup after conversion. If unchecked, the .pfb.17 file is deleted once the .pfb.18 file has been written",
		default = False,
		)
	
	def execute(self,context):
		directory = bpy.path.abspath(self.dirPath)
		if not os.path.isdir(directory):
			showMessageBox("Choose a valid directory.",title = "DD2 PFB Version Converter",icon = "ERROR")
			return {'CANCELLED'}
		
		results = batchConvertDD2PFBFiles(directory,searchSubdirectories = self.searchSubdirectories,keepBackup = self.createBackups)
		convertedCount = len(results["converted"])
		failedCount = len(results["failed"])
		totalCount = convertedCount + failedCount
		
		if totalCount == 0:
			message = "No .pfb.17 files found."
			showMessageBox(message,title = "DD2 PFB Version Converter",icon = "INFO")
			self.report({"INFO"},message)
			return {'FINISHED'}
		
		message = f"Converted {convertedCount} of {totalCount} PFB files."
		message += " .pfb.17 files renamed to .bak." if self.createBackups else " .pfb.17 files deleted."
		if failedCount:
			message += f" {failedCount} skipped, see Window > Toggle System Console."
		showMessageBox(message,title = "DD2 PFB Version Converter",icon = "ERROR" if failedCount else "INFO")
		self.report({"WARNING"} if failedCount else {"INFO"},message)
		return {'FINISHED'}
	
	def invoke(self,context,event):
		if self.dirPath == "":
			if "modWorkspace_directory" in context.scene:#Mod directory set by the RE Asset Library / RE Mesh Editor workspace, if it's there
				self.dirPath = context.scene["modWorkspace_directory"]
			elif bpy.data.filepath != "":
				self.dirPath = os.path.dirname(bpy.data.filepath)
		try:
			return context.window_manager.invoke_props_dialog(self,width = 500,confirm_text = "Convert PFB Files")
		except TypeError:#confirm_text isn't available on older Blender versions
			return context.window_manager.invoke_props_dialog(self,width = 500)
	
	def draw(self,context):
		layout = self.layout
		layout.label(text = "Converts DD2 tops_* .pfb.17 files to .pfb.18.")
		layout.label(text = "Only chain, mesh, skin (mdf2) and clsp prefabs are supported.")
		layout.label(text = "Other files are skipped and left untouched.")
		layout.prop(self,"dirPath")
		layout.prop(self,"searchSubdirectories")
		layout.prop(self,"createBackups")
