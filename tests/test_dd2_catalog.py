import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

package = types.ModuleType('asset_catalog_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules[package.__name__] = package
utils = importlib.import_module(package.__name__ + '.modules.asset.re_asset_utils')

class DD2CatalogTests(unittest.TestCase):
    def test_explicit_migration_preserves_other_settings(self):
        original = {'GameName':'DD2','GameInfoVersion':1,'custom':'keep',
                    'fileVersionDict':{'MESH_VERSION':'240423143','MDF2_VERSION':'40',
                                       'TEX_VERSION':'760230703','CHAIN_VERSION':'unchanged'}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'GameInfo_DD2.json'
            path.write_text(json.dumps(original),encoding='utf-8')
            self.assertEqual(utils.loadGameInfo(path),original)
            utils.setDD2September2026Versions(path)
            expected = json.loads(json.dumps(original))
            expected['fileVersionDict'].update(MESH_VERSION='260421070',MDF2_VERSION='51',TEX_VERSION='251211553')
            self.assertEqual(utils.loadGameInfo(path),expected)
            asset = {'assetPath':'character/test.mesh','assetType':'MESH'}
            self.assertEqual(utils.buildNativesPathFromObj(asset,expected,'stm'),
                             'natives/stm/character/test.mesh.260421070')

    def test_other_game_is_not_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'GameInfo_RE9.json'
            data = json.dumps({'GameName':'RE9','GameInfoVersion':1,'fileVersionDict':{}})
            path.write_text(data,encoding='utf-8')
            with self.assertRaises(ValueError):
                utils.setDD2September2026Versions(path)
            self.assertEqual(path.read_text(encoding='utf-8'),data)

if __name__ == '__main__':
    unittest.main()
