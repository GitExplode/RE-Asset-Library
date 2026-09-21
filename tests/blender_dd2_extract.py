import sys,importlib,json,os
from pathlib import Path
import addon_utils,bpy
import argparse
import tempfile
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('game',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sys.path.insert(0,str(root.parent))
addon=addon_utils.enable(root.name,default_set=True)
assert addon is not None
assert bpy.ops.re_asset.update_dd2_formats.get_rna_type().identifier
utils=importlib.import_module(root.name+'.modules.pak.re_pak_utils')
assets=importlib.import_module(root.name+'.modules.asset.re_asset_utils')
out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
out=Path(tempfile.mkdtemp(prefix='dd2-extract-',dir=out))
print('TEST_OUTPUT',out)
game=args.game.resolve()
exe=game/'DD2.exe'
info=out/'GameInfo_DD2.json'
info.write_text(json.dumps({'GameName':'DD2','GameInfoVersion':1,'fileVersionDict':{
    'MESH_VERSION':'240423143','MDF2_VERSION':'40','TEX_VERSION':'760230703'}}),encoding='utf-8')
assets.setDD2September2026Versions(info)
extract=out/'ExtractInfo_DD2.json'
extract.write_text(json.dumps({'exePath':str(exe),'exeDate':exe.stat().st_mtime,'extractPath':str(out/'extracted'),'platform':'stm'}),encoding='utf-8')
mesh_path='natives/stm/character/_kit/_equipment/mantle/012/mantle_012_f.mesh.260421070'
asset=bpy.data.objects.new('DD2 test asset',None)
asset['assetType']='MESH'
asset['assetPath']='character/_kit/_equipment/mantle/012/mantle_012_f.mesh'
utils.extractFilesFromPakCache(str(info),[],str(extract),str(out/'PakCache_DD2.pakcache'),extractDependencies=True,blenderAssetObj=asset)
files=list((out/'extracted').rglob('*'))
assert (out/'extracted'/mesh_path).is_file()
assert any(p.name.endswith('.mdf2.51') for p in files)
assert any(p.name.endswith('.tex.251211553') for p in files)
print('ASSET_LIBRARY_PATH_PASS',len([p for p in files if p.is_file()]))
