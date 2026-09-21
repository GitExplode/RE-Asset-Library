"""PAK layout regression; no game assets are distributed with these tests."""
import importlib
import io
from pathlib import Path
import struct
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('asset_tests')
package.__path__ = [str(ROOT)]
sys.modules['asset_tests'] = package
pak = importlib.import_module('asset_tests.modules.pak.file_re_pak')

class PakLayoutTests(unittest.TestCase):
    def test_dd2_extra_table_moves_key_and_chunk_table(self):
        # Empty TOC permits using the real decryptor without embedding game data.
        data = struct.pack('<IBBHII', 0x414b504b, 4, 2, 0x68, 0, 0)
        data += struct.pack('<Q4I', 1, 10, 20, 30, 40)
        data += bytes(128)
        data += struct.pack('<HHIII', 0, 8, 1, 123456, 0)
        result = pak.PakFile()
        result.readTOC(io.BytesIO(data))
        self.assertEqual(result.remapTable.entryList[0].fileOffset, 123456)

    def test_existing_unencrypted_v4(self):
        data = struct.pack('<IBBHII', 0x414b504b, 4, 1, 0, 1, 0)
        data += struct.pack('<IIQQQQQ', 123, 456, 64, 8, 8, 0, 0)
        result = pak.PakFile()
        result.readTOC(io.BytesIO(data))
        self.assertEqual(result.toc.entryList[0].offset, 64)

    def test_truncated_dd2_extra_table(self):
        data = struct.pack('<IBBHII', 0x414b504b, 4, 2, 0x68, 0, 0)
        data += struct.pack('<Q', 1)
        with self.assertRaises((EOFError, ValueError, struct.error)):
            pak.PakFile().readTOC(io.BytesIO(data))

if __name__ == '__main__':
    unittest.main()
